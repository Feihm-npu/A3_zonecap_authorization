import os

import pytest

from zonecap.c5.corpus import sign, test_keypair as derive_keypair
from zonecap.c5.pep import (
    ALLOW,
    ATTENUATE,
    AUDIT,
    DEFER,
    DENY,
    FULL_MASK,
    REWRITE,
    SIGNATURE,
    ContextSnapshot,
    ContextStore,
    LocalRevocationStore,
    PEPOptions,
    PipeAuditSink,
    ReferencePEP,
    RegisteredPolicy,
)
from zonecap.c5.wire import (
    WireError,
    canonical_json,
    encode_envelope,
    request_payload,
    split_envelope,
    token_digest,
    token_payload,
)
from zonecap.c5.audit import open_queue


ISSUER = "issuer:test"
ROOT_SUBJECT = "subject:root"
CHILD_SUBJECT = "subject:child"
KEY = ("zone_b", "valve")


def _fields(**overrides):
    fields = {
        "source_zone": "zone_a",
        "target_zone": "zone_b",
        "conduits": ["c_ab"],
        "assets": ["valve"],
        "actions": ["read", "write"],
        "parameter": (0, 100),
        "ticks": (100, 200),
        "modes": ["normal", "maintenance"],
        "required_sequence": ["authenticate"],
    }
    fields.update(overrides)
    return fields


def _token(token_id, subject, depth, previous, signer_secret, **overrides):
    public_key, _ = derive_keypair("subject", subject)
    fields = _fields(**overrides)
    payload = token_payload(
        token_id=token_id,
        policy_id="test:g000",
        issuer=ISSUER,
        subject=subject,
        subject_public_key=public_key,
        depth=depth,
        previous_digest=previous,
        **fields,
    )
    return payload, sign(payload, signer_secret)


def _chain(**child_overrides):
    issuer_public, issuer_secret = derive_keypair("issuer", ISSUER)
    root = _token("root", ROOT_SUBJECT, 0, None, issuer_secret)
    _, root_subject_secret = derive_keypair("subject", ROOT_SUBJECT)
    child_fields = {"actions": ["read"], "parameter": (10, 90), "modes": ["normal"],
                    "required_sequence": ["authenticate", "authorize"]}
    child_fields.update(child_overrides)
    child = _token("child", CHILD_SUBJECT, 1, token_digest(*root), root_subject_secret, **child_fields)
    return issuer_public, [root, child]


def _request(value=50, action="read", conduit="c_ab"):
    return request_payload(
        request_id="r1", source_zone="zone_a", target_zone="zone_b", conduit=conduit,
        asset="valve", action=action, value=value,
    )


class _Sink:
    def __init__(self, accept=True):
        self.accept = accept
        self.records = []

    def enqueue(self, record):
        self.records.append(record)
        return self.accept


def _pep(anchor, *, sink=None, revoked=(), **options):
    registry = {
        "test:g000": RegisteredPolicy(
            policy_id="test:g000", issuer=ISSUER, subject=ROOT_SUBJECT, source_zone="zone_a",
            target_zone="zone_b", conduits=frozenset({"c_ab"}), assets=frozenset({"valve"}),
            actions=frozenset({"read", "write"}), parameter=(0, 100), ticks=(100, 200),
            modes=frozenset({"normal", "maintenance"}), sequence=("authenticate",),
        )
    }
    store = ContextStore()
    store.publish(KEY, ContextSnapshot(tick=150, mode="normal", history=("authenticate", "authorize")))
    pep = ReferencePEP(
        anchors={ISSUER: anchor}, registry=registry, revocation=LocalRevocationStore(revoked),
        context=store, audit=sink or _Sink(), options=PEPOptions(**options),
    )
    return pep, store


def test_envelope_round_trip_and_rejects_trailing_bytes():
    _, chain = _chain()
    envelope = encode_envelope(chain, _request())
    tokens, request = split_envelope(envelope)
    assert tokens == chain and request == _request()
    with pytest.raises(WireError):
        split_envelope(envelope + b"x")


def test_valid_child_allows_with_full_stage_mask_and_counts_signatures():
    anchor, chain = _chain()
    pep, _ = _pep(anchor)
    result = pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request(50)))
    assert result[:5] == (ALLOW, "read", 50, None, None)
    assert result[6] == FULL_MASK
    assert (result[7], result[8]) == (2, 0)
    again = pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request(50)))
    assert (again[7], again[8]) == (0, 2)
    pep.clear_verification_cache()
    cold = pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request(50)))
    assert (cold[7], cold[8]) == (2, 0)


def test_rewrite_deny_attenuate_and_defer_follow_engine_order():
    anchor, chain = _chain()
    pep, store = _pep(anchor)
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request(95)))[:3] == (REWRITE, "read", 90)
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request(action="write")))[0] == DENY
    assert pep.decide("subject:other", encode_envelope(chain, _request()))[5] == "subject"
    store.publish(KEY, ContextSnapshot(tick=150, mode="normal", history=("authenticate", "authorize"),
                                       envelope=(10, 50)))
    attenuated = pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request(30)))
    assert attenuated[:5] == (ATTENUATE, None, None, 10, 50)
    store.publish(KEY, ContextSnapshot(tick=150, mode="normal", history=(), complete=False))
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[:3] == (DEFER, "read", 10)


def test_consecutive_deferrals_time_out_fail_closed():
    anchor, chain = _chain()
    pep, store = _pep(anchor, max_deferrals=2)
    store.publish(KEY, ContextSnapshot(tick=150, mode="normal", history=(), complete=False))
    effects = [pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[0] for _ in range(3)]
    assert effects == [DEFER, DEFER, DENY]
    store.publish(KEY, ContextSnapshot(tick=150, mode="normal", history=("authenticate", "authorize")))
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[0] == ALLOW


def test_stale_and_missing_context_defer():
    anchor, chain = _chain()
    pep, store = _pep(anchor, max_context_age_ns=1_000)
    store.publish(KEY, ContextSnapshot(tick=150, mode="normal", history=("authenticate", "authorize")),
                  published_ns=0)
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[5] == "context_unavailable"
    store.withdraw(KEY)
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[0] == DEFER


@pytest.mark.parametrize(
    "override",
    [
        {"conduits": ["c_ab", "c_other"]},
        {"assets": ["valve", "pump"]},
        {"actions": ["read", "write", "admin"]},
        {"parameter": (-1, 90)},
        {"ticks": (100, 201)},
        {"modes": ["normal", "emergency"]},
        {"required_sequence": ["inspect"]},
        {"target_zone": "zone_c"},
    ],
)
def test_widened_child_is_rejected_before_policy(override):
    anchor, chain = _chain(**override)
    pep, _ = _pep(anchor)
    result = pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))
    assert result[0] == DENY and result[5] == "invalid_delegation" and result[1] is None


def test_bad_signature_unregistered_root_and_revocation_deny():
    anchor, chain = _chain()
    payload, signature = chain[1]
    tampered = [chain[0], (payload, bytes([signature[0] ^ 1]) + signature[1:])]
    pep, _ = _pep(anchor)
    assert pep.decide(CHILD_SUBJECT, encode_envelope(tampered, _request()))[5] == "bad_signature"
    other_public, _ = derive_keypair("issuer", "issuer:other")
    pep, _ = _pep(other_public)
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[5] == "bad_signature"
    pep, _ = _pep(anchor, revoked=("root",))
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[5] == "revoked"


def test_unsigned_diagnostic_skips_signatures_and_reports_missing_bit():
    anchor, chain = _chain()
    payload, signature = chain[1]
    tampered = [chain[0], (payload, bytes(64))]
    pep, _ = _pep(anchor, verify_signatures=False)
    result = pep.decide(CHILD_SUBJECT, encode_envelope(tampered, _request()))
    assert result[0] == ALLOW
    assert result[6] == FULL_MASK & ~SIGNATURE


def test_malformed_payloads_fail_closed():
    anchor, chain = _chain()
    pep, _ = _pep(anchor)
    assert pep.decide(CHILD_SUBJECT, b"ZCE1\x01")[5] == "malformed"
    bad_request = canonical_json({"a": "valve"})
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, bad_request))[5] == "malformed"
    nan_request = _request().replace(b'"u":50', b'"u":NaN')
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, nan_request))[5] == "malformed"


def test_audit_queue_full_or_closed_denies_without_emission():
    anchor, chain = _chain()
    pep, _ = _pep(anchor, sink=_Sink(accept=False))
    result = pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))
    assert result[0] == DENY and result[5] == "audit_unavailable" and not result[6] & AUDIT
    read_fd, write_fd, _ = open_queue(65536)
    os.set_blocking(write_fd, False)
    try:
        while True:
            os.write(write_fd, b"x" * 4095 + b"\n")
    except BlockingIOError:
        pass
    pep, _ = _pep(anchor, sink=PipeAuditSink(write_fd))
    assert pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[5] == "audit_unavailable"
    os.close(read_fd)
    os.close(write_fd)


def test_each_disabled_stage_is_visible_in_the_mask():
    anchor, chain = _chain()
    from zonecap.c5.pep import STAGES

    for name, bit in STAGES:
        pep, _ = _pep(anchor, disabled_stages=frozenset({name}))
        mask = pep.decide(CHILD_SUBJECT, encode_envelope(chain, _request()))[6]
        assert mask == FULL_MASK & ~bit, name
