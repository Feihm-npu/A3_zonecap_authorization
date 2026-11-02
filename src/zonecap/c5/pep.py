from __future__ import annotations

"""Frozen C5 reference policy enforcement point (PEP).

``ReferencePEP.decide`` is the complete timed decision path.  Its fixed,
fail-closed order is:

1. parse the envelope and check every payload schema;
2. anchor the root at a trusted issuer key and a registered compiled policy;
3. check delegation linkage, depth, and field-wise attenuation of every link;
4. verify every Ed25519 token signature, or find the token digest in the
   verification cache;
5. look up every token identifier in the revocation store;
6. look up and freshness-check the runtime-context snapshot;
7. evaluate the five-effect policy with the registered ``PolicyEngine`` order;
8. bind the effect, re-check the emitted action, and bound consecutive DEFERs;
9. construct the exact response record; and
10. enqueue that record in the bounded audit queue, or deny on failure.

Steps 1-5 deny on failure.  The verification cache stores only digests of
immutable tokens whose signature, linkage, and attenuation have already been
checked.  Revocation, root registration, context, policy, binding, and audit
are evaluated on every request.  No parsed token, decision, or response is
reused across requests.
"""

from dataclasses import dataclass
import hashlib
import json
import math
import os
import time
from typing import Any, Callable, Iterable, Mapping

from nacl.bindings import crypto_sign_open

from .wire import (
    PUBLIC_KEY_BYTES,
    REQUEST_KEYS,
    TOKEN_KEYS,
    WIRE_VERSION,
    WireError,
    canonical_json,
    split_envelope,
)


PARSE = 1 << 0
ANCHOR = 1 << 1
CHAIN = 1 << 2
SIGNATURE = 1 << 3
REVOCATION = 1 << 4
CONTEXT = 1 << 5
POLICY = 1 << 6
BINDING = 1 << 7
RESPONSE = 1 << 8
AUDIT = 1 << 9

STAGES = (
    ("parse", PARSE),
    ("anchor", ANCHOR),
    ("chain", CHAIN),
    ("signature", SIGNATURE),
    ("revocation", REVOCATION),
    ("context", CONTEXT),
    ("policy", POLICY),
    ("binding", BINDING),
    ("response", RESPONSE),
    ("audit", AUDIT),
)
STAGE_BITS = dict(STAGES)
FULL_MASK = sum(bit for _, bit in STAGES)

ALLOW = "allow"
DENY = "deny"
ATTENUATE = "attenuate"
REWRITE = "rewrite"
DEFER = "defer"

HOLD_OPERATION = "read"
PIPE_BUF = 4096
DEFAULT_MAX_DEFERRALS = 2
DEFAULT_MAX_CONTEXT_AGE_NS = 50_000_000
DEFAULT_CACHE_CAPACITY = 65_536


def _reject_constant(name: str) -> float:
    raise WireError(f"non-finite JSON constant {name}")


def _strings(value: Any) -> bool:
    return type(value) is list and all(type(item) is str for item in value)


def _interval(value: Any) -> tuple[float, float]:
    if type(value) is not list or len(value) != 2:
        raise WireError("interval must have two endpoints")
    low, high = value
    if type(low) not in (int, float) or type(high) not in (int, float):
        raise WireError("interval endpoints must be numbers")
    if not (math.isfinite(low) and math.isfinite(high)) or low > high:
        raise WireError("invalid interval")
    return (low, high)


class Token:
    __slots__ = (
        "token_id",
        "policy_id",
        "issuer",
        "subject",
        "subject_key",
        "source_zone",
        "target_zone",
        "conduits",
        "assets",
        "actions",
        "parameter",
        "ticks",
        "modes",
        "sequence",
        "depth",
        "previous",
        "digest",
        "payload",
        "signature",
    )


def parse_token(payload: bytes, signature: bytes, *, check_schema: bool = True) -> Token:
    doc = json.loads(payload, parse_constant=_reject_constant)
    if check_schema:
        if type(doc) is not dict or doc.keys() != TOKEN_KEYS or doc["v"] != WIRE_VERSION:
            raise WireError("token schema")
        for key in ("id", "pol", "iss", "sub", "zs", "zd", "spk"):
            if type(doc[key]) is not str:
                raise WireError(f"token field {key}")
        for key in ("K", "A", "O", "M", "L"):
            if not _strings(doc[key]):
                raise WireError(f"token field {key}")
        depth = doc["d"]
        if type(depth) is not int or depth < 0:
            raise WireError("token depth")
        previous = doc["prev"]
        if not (previous is None or (type(previous) is str and len(previous) == 64)):
            raise WireError("token prev")
    token = Token()
    token.token_id = doc["id"]
    token.policy_id = doc["pol"]
    token.issuer = doc["iss"]
    token.subject = doc["sub"]
    token.subject_key = bytes.fromhex(doc["spk"])
    if len(token.subject_key) != PUBLIC_KEY_BYTES:
        raise WireError("subject key length")
    token.source_zone = doc["zs"]
    token.target_zone = doc["zd"]
    token.conduits = frozenset(doc["K"])
    token.assets = frozenset(doc["A"])
    token.actions = frozenset(doc["O"])
    token.parameter = _interval(doc["Iu"])
    token.ticks = _interval(doc["It"])
    token.modes = frozenset(doc["M"])
    token.sequence = tuple(doc["L"])
    token.depth = doc["d"]
    token.previous = doc["prev"]
    token.digest = hashlib.sha256(payload + signature).hexdigest()
    token.payload = payload
    token.signature = signature
    return token


def parse_request(payload: bytes, *, check_schema: bool = True) -> dict[str, Any]:
    doc = json.loads(payload, parse_constant=_reject_constant)
    if check_schema:
        if type(doc) is not dict or doc.keys() != REQUEST_KEYS or doc["v"] != WIRE_VERSION:
            raise WireError("request schema")
        for key in ("a", "k", "o", "rid", "zd", "zs"):
            if type(doc[key]) is not str:
                raise WireError(f"request field {key}")
        value = doc["u"]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise WireError("request value")
    return doc


@dataclass(frozen=True)
class RegisteredPolicy:
    """A compiled root capability from the registered policy set."""

    policy_id: str
    issuer: str
    subject: str
    source_zone: str
    target_zone: str
    conduits: frozenset[str]
    assets: frozenset[str]
    actions: frozenset[str]
    parameter: tuple[float, float]
    ticks: tuple[float, float]
    modes: frozenset[str]
    sequence: tuple[str, ...]


def attenuates(child: Any, parent: Any) -> bool:
    """Field-wise ``child <= parent`` over issuer, zones, and eight dimensions."""

    return (
        child.issuer == parent.issuer
        and child.source_zone == parent.source_zone
        and child.target_zone == parent.target_zone
        and child.conduits <= parent.conduits
        and child.assets <= parent.assets
        and child.actions <= parent.actions
        and parent.parameter[0] <= child.parameter[0]
        and child.parameter[1] <= parent.parameter[1]
        and parent.ticks[0] <= child.ticks[0]
        and child.ticks[1] <= parent.ticks[1]
        and child.modes <= parent.modes
        and child.sequence[: len(parent.sequence)] == parent.sequence
    )


def _subsequence(required: tuple[str, ...], history: tuple[str, ...]) -> bool:
    if not required:
        return True
    cursor = 0
    for event in history:
        if event == required[cursor]:
            cursor += 1
            if cursor == len(required):
                return True
    return False


@dataclass(frozen=True)
class ContextSnapshot:
    """Trusted runtime context published by the context-ingest component."""

    tick: float
    mode: str
    history: tuple[str, ...]
    complete: bool = True
    high_risk: bool = False
    envelope: tuple[float, float] | None = None


class ContextStore:
    """In-process, versioned context snapshots keyed by (target zone, asset).

    Ingest publishes; the decision path performs one dictionary lookup and a
    freshness check.  Reading PLC or plant state over a network belongs to the
    ingest path, not to the decision path.
    """

    def __init__(self, *, clock: Callable[[], int] = time.monotonic_ns) -> None:
        self._entries: dict[tuple[str, str], tuple[int, int, ContextSnapshot]] = {}
        self._version = 0
        self._clock = clock

    def publish(
        self,
        key: tuple[str, str],
        snapshot: ContextSnapshot,
        *,
        published_ns: int | None = None,
    ) -> int:
        self._version += 1
        stamp = self._clock() if published_ns is None else published_ns
        self._entries[key] = (self._version, stamp, snapshot)
        return self._version

    def withdraw(self, key: tuple[str, str]) -> None:
        self._entries.pop(key, None)

    def get(self, key: tuple[str, str]) -> tuple[int, int, ContextSnapshot] | None:
        return self._entries.get(key)


class LocalRevocationStore:
    """Revoked token identifiers held in process memory."""

    def __init__(self, revoked: Iterable[str] = ()) -> None:
        self.revoked: set[str] = set(revoked)
        self.epoch = 0

    def revoke(self, token_id: str) -> None:
        self.revoked.add(token_id)
        self.epoch += 1

    def any_revoked(self, token_ids: list[str]) -> bool:
        revoked = self.revoked
        for token_id in token_ids:
            if token_id in revoked:
                return True
        return False

    def size(self) -> int:
        return len(self.revoked)


class PipeAuditSink:
    """Bounded audit queue: a non-blocking pipe drained by another process.

    Each record plus newline is at most ``PIPE_BUF`` bytes, so a write is
    atomic: it either enqueues the whole record or fails with ``EAGAIN`` when
    the pipe is full.  A full or closed queue makes the PEP deny.
    """

    def __init__(self, write_fd: int) -> None:
        os.set_blocking(write_fd, False)
        self.fd = write_fd

    def enqueue(self, record: bytes) -> bool:
        line = record + b"\n"
        if len(line) > PIPE_BUF:
            return False
        try:
            return os.write(self.fd, line) == len(line)
        except OSError:
            # EAGAIN (queue full), EPIPE (drain gone), or EBADF (queue closed).
            return False


@dataclass
class PEPOptions:
    verify_signatures: bool = True
    verification_cache: bool = True
    cache_capacity: int = DEFAULT_CACHE_CAPACITY
    audit_enabled: bool = True
    max_deferrals: int = DEFAULT_MAX_DEFERRALS
    max_context_age_ns: int = DEFAULT_MAX_CONTEXT_AGE_NS
    disabled_stages: frozenset[str] = frozenset()
    forced_delay_ns: int = 0

    def diagnostic_disabled_mask(self) -> int:
        mask = 0
        for name in self.disabled_stages:
            mask |= STAGE_BITS[name]
        if not self.verify_signatures:
            mask |= SIGNATURE
        if not self.audit_enabled:
            mask |= AUDIT
        return mask


class ReferencePEP:
    def __init__(
        self,
        *,
        anchors: Mapping[str, bytes],
        registry: Mapping[str, RegisteredPolicy],
        revocation: Any,
        context: ContextStore,
        audit: Any,
        options: PEPOptions | None = None,
        clock: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.options = options or PEPOptions()
        unknown = set(self.options.disabled_stages) - set(STAGE_BITS)
        if unknown:
            raise ValueError(f"unknown disabled stages: {sorted(unknown)}")
        for issuer, key in anchors.items():
            if len(key) != PUBLIC_KEY_BYTES:
                raise ValueError(f"anchor key for {issuer} is not 32 bytes")
        self.anchors = dict(anchors)
        self.registry = dict(registry)
        self.revocation = revocation
        self.context = context
        self.audit = audit
        self.clock = clock
        self.verified: dict[str, None] = {}
        self.deferrals: dict[str, int] = {}
        disabled = self.options.disabled_stages
        self._schema = "parse" not in disabled
        self._anchor = "anchor" not in disabled
        self._chain = "chain" not in disabled
        self._signature = self.options.verify_signatures and "signature" not in disabled
        self._revocation = "revocation" not in disabled
        self._context = "context" not in disabled
        self._policy = "policy" not in disabled
        self._binding = "binding" not in disabled
        self._response = "response" not in disabled
        self._audit = self.options.audit_enabled and "audit" not in disabled
        self._cache = self.options.verification_cache

    def clear_verification_cache(self) -> None:
        self.verified.clear()

    def _record(
        self,
        request_id: Any,
        effect: str,
        operation: Any,
        value: Any,
        child: Any,
        reason: str,
        chain_ids: list[str],
        context_version: Any,
    ) -> bytes:
        return canonical_json(
            {
                "ch": chain_ids,
                "cv": context_version,
                "e": effect,
                "hi": None if child is None else child[1],
                "lo": None if child is None else child[0],
                "o": operation,
                "r": reason,
                "rid": request_id,
                "rv": getattr(self.revocation, "epoch", None),
                "u": value,
            }
        )

    def _finish(
        self,
        mask: int,
        request_id: Any,
        effect: str,
        operation: Any,
        value: Any,
        child: Any,
        reason: str,
        chain_ids: list[str],
        context_version: Any,
        verified: int,
        hits: int,
    ) -> tuple:
        response = b""
        if self._response:
            response = self._record(
                request_id, effect, operation, value, child, reason, chain_ids, context_version
            )
            mask |= RESPONSE
        if self._audit:
            if self.audit.enqueue(response):
                mask |= AUDIT
            else:
                effect, operation, value, child, reason = DENY, None, None, None, "audit_unavailable"
                if self._response:
                    response = self._record(
                        request_id, effect, None, None, None, reason, chain_ids, context_version
                    )
        if self.options.forced_delay_ns:
            time.sleep(self.options.forced_delay_ns / 1_000_000_000)
        return (
            effect,
            operation,
            value,
            None if child is None else child[0],
            None if child is None else child[1],
            reason,
            mask,
            verified,
            hits,
            response,
        )

    def decide(self, subject: str, envelope: bytes) -> tuple:
        """Decide one serialized request from an authenticated ``subject``.

        Returns ``(effect, operation, value, child_low, child_high, reason,
        stage_mask, signatures_verified, cache_hits, response_bytes)``.
        """

        mask = 0
        verified = 0
        hits = 0
        request_id = None
        chain_ids: list[str] = []

        # 1. Parse and schema checks.
        try:
            raw_tokens, raw_request = split_envelope(envelope)
            chain = [
                parse_token(payload, signature, check_schema=self._schema)
                for payload, signature in raw_tokens
            ]
            request = parse_request(raw_request, check_schema=self._schema)
            request_id = request["rid"]
        except (WireError, ValueError, KeyError, TypeError):
            return self._finish(
                mask, None, DENY, None, None, None, "malformed", chain_ids, None, 0, 0
            )
        if self._schema:
            mask |= PARSE
        chain_ids = [token.token_id for token in chain]
        root = chain[0]
        leaf = chain[-1]

        # 2. Trust anchor and registered compiled policy for the root.
        if self._anchor:
            policy = self.registry.get(root.policy_id)
            if (
                root.issuer not in self.anchors
                or policy is None
                or root.depth != 0
                or root.previous is not None
                or root.subject != policy.subject
                or not attenuates(root, policy)
            ):
                return self._finish(
                    mask, request_id, DENY, None, None, None, "unregistered_root",
                    chain_ids, None, 0, 0,
                )
            mask |= ANCHOR

        # 3. Delegation linkage, depth, and attenuation of every link.
        if self._chain:
            for index in range(1, len(chain)):
                child = chain[index]
                parent = chain[index - 1]
                if (
                    child.depth != index
                    or child.previous != parent.digest
                    or child.policy_id != parent.policy_id
                    or not attenuates(child, parent)
                ):
                    return self._finish(
                        mask, request_id, DENY, None, None, None, "invalid_delegation",
                        chain_ids, None, 0, 0,
                    )
            mask |= CHAIN

        # 4. Ed25519 signatures, or digests of already-verified immutable tokens.
        if self._signature:
            cache = self.verified if self._cache else None
            for index, token in enumerate(chain):
                if cache is not None and token.digest in cache:
                    hits += 1
                    continue
                key = self.anchors.get(token.issuer) if index == 0 else chain[index - 1].subject_key
                try:
                    if key is None:
                        raise WireError("no verification key")
                    crypto_sign_open(token.signature + token.payload, key)
                except Exception:
                    return self._finish(
                        mask, request_id, DENY, None, None, None, "bad_signature",
                        chain_ids, None, verified, hits,
                    )
                verified += 1
                if cache is not None:
                    if len(cache) >= self.options.cache_capacity:
                        del cache[next(iter(cache))]
                    cache[token.digest] = None
            mask |= SIGNATURE

        # 5. Revocation of any token in the chain.
        if self._revocation:
            try:
                revoked = self.revocation.any_revoked(chain_ids)
            except Exception:
                return self._finish(
                    mask, request_id, DENY, None, None, None, "revocation_unavailable",
                    chain_ids, None, verified, hits,
                )
            if revoked:
                return self._finish(
                    mask, request_id, DENY, None, None, None, "revoked",
                    chain_ids, None, verified, hits,
                )
            mask |= REVOCATION

        # 6. Runtime context: lookup plus freshness.
        entry = self.context.get((request["zd"], request["a"]))
        context_version = None
        snapshot = None
        context_ok = False
        if entry is not None:
            context_version, published_ns, snapshot = entry
            context_ok = snapshot.complete
        if self._context:
            if entry is not None and self.clock() - published_ns > self.options.max_context_age_ns:
                context_ok = False
            mask |= CONTEXT

        # 7. Five-effect policy in the registered PolicyEngine order.
        effect = ALLOW
        reason = "authorized"
        child = None
        value = request["u"]
        operation = request["o"]
        if self._policy:
            low, high = leaf.parameter
            if not context_ok:
                effect, reason = DEFER, "context_unavailable"
            elif snapshot.high_risk:
                effect, reason = DEFER, "high_risk"
            elif subject != leaf.subject:
                effect, reason = DENY, "subject"
            elif request["zs"] != leaf.source_zone:
                effect, reason = DENY, "source_zone"
            elif request["zd"] != leaf.target_zone:
                effect, reason = DENY, "target_zone"
            elif request["k"] not in leaf.conduits:
                effect, reason = DENY, "conduit"
            elif request["a"] not in leaf.assets:
                effect, reason = DENY, "asset"
            elif operation not in leaf.actions:
                effect, reason = DENY, "action"
            elif not leaf.ticks[0] <= snapshot.tick <= leaf.ticks[1]:
                effect, reason = DENY, "time"
            elif snapshot.mode not in leaf.modes:
                effect, reason = DENY, "mode"
            elif not _subsequence(leaf.sequence, snapshot.history):
                effect, reason = DENY, "sequence"
            else:
                if snapshot.envelope is not None:
                    effective_low = max(low, snapshot.envelope[0])
                    effective_high = min(high, snapshot.envelope[1])
                    if effective_low > effective_high:
                        effect, reason = DENY, "envelope_disjoint"
                    elif (effective_low, effective_high) != (low, high):
                        effect, reason = ATTENUATE, "runtime_envelope"
                        child = (effective_low, effective_high)
                if effect is ALLOW and not low <= value <= high:
                    effect, reason = REWRITE, "parameter_boundary"
                    value = min(max(value, low), high)
            mask |= POLICY
        elif not context_ok:
            effect, reason = DEFER, "context_unavailable"

        # 8. Effect binding, pre-emission recheck, and bounded deferral.
        if effect is ALLOW or effect is REWRITE:
            emitted = (operation, value)
        elif effect is DEFER:
            emitted = (HOLD_OPERATION, leaf.parameter[0])
        else:
            emitted = None
        if self._binding:
            if effect is DEFER:
                count = self.deferrals.get(leaf.subject, 0)
                if count >= self.options.max_deferrals:
                    effect, reason, emitted = DENY, "defer_timeout", None
                else:
                    self.deferrals[leaf.subject] = count + 1
            else:
                self.deferrals.pop(leaf.subject, None)
            if emitted is not None and not (
                emitted[0] in leaf.actions
                and leaf.parameter[0] <= emitted[1] <= leaf.parameter[1]
            ):
                effect, reason, emitted = DENY, "binding_rejected", None
            mask |= BINDING
        if emitted is None:
            operation = value = None
        else:
            operation, value = emitted

        # 9-10. Exact response record and bounded audit enqueue.
        return self._finish(
            mask, request_id, effect, operation, value, child, reason,
            chain_ids, context_version, verified, hits,
        )
