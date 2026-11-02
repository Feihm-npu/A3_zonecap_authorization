from __future__ import annotations

"""Deterministic C5 corpus builder and loader.

The builder reads only frozen inputs: the exp-07 policy table and the
registered exp-07 case file.  It compiles root capabilities with the ZoneCap
compiler, issues Ed25519 token chains with deterministic test keys, rebuilds
the exp-12 five-step composed traces, and writes one directory per corpus
variant.  Ed25519 signatures and canonical JSON are deterministic, so every
platform must reproduce the same file hashes.

Test keys are derived from public strings.  They are measurement fixtures and
must never be used to authorize a real plant.

Variants:

* ``main``: all 58,968 exp-07 one-request cases plus 4,536 five-step composed
  traces (81,648 policy steps, exp-12 effect mix);
* ``scale_d0``/``scale_d1``/``scale_d2``: the exp-07 cases of one registered
  grant at delegation depth 0, 1, or 2 (exp-24);
* ``sint_subset``: valid cases plus the subject, asset, action, parameter-high,
  and tick-high mutations that pinned SINT can express (exp-25).
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Iterator

from nacl.bindings import crypto_sign, crypto_sign_seed_keypair

from ..compiler import Architecture
from ..effects import EffectBinding, EffectContractError
from ..engine import PolicyEngine
from ..exp07_generator import architecture_document, expand_scopes
from ..models import ActionRequest, Capability, Interval
from . import oracle
from .wire import encode_envelope, request_payload, token_digest, token_payload


CORPUS_VERSION = 1
KEY_DOMAIN = "zonecap-c5-test-keys-v1"
SCALE_POLICY_ID = "cpwe_cip_security:g001"
SINT_MUTATIONS = frozenset({"subject", "asset", "action", "parameter_high", "tick_high"})
COMPOSED_KINDS = ("attenuate", "defer", "allow", "rewrite", "deny")
VARIANTS = ("main", "scale_d0", "scale_d1", "scale_d2", "sint_subset")
DEFAULT_POLICY_TABLE = "research/heldout/exp07/policy_tables.json"
DEFAULT_EXP07_CASES = "results/exp07_heldout_equivalence_20260901/cases.jsonl.gz"

_U32 = struct.Struct(">I")


def test_keypair(kind: str, name: str) -> tuple[bytes, bytes]:
    """Deterministic Ed25519 ``(public_key, secret_key)`` for a test principal."""

    seed = hashlib.sha256(f"{KEY_DOMAIN}|{kind}|{name}".encode("utf-8")).digest()
    return crypto_sign_seed_keypair(seed)


def sign(payload: bytes, secret_key: bytes) -> bytes:
    return crypto_sign(payload, secret_key)[:64]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strict_runtime_envelope(parameter: list[float], value: float) -> list[float]:
    """The exp-12 runtime envelope: strictly narrower and containing ``value``."""

    low, high = parameter
    if low == high:
        raise ValueError("composed traces require a non-degenerate parameter interval")
    midpoint = low + (high - low) / 2
    if value <= low:
        envelope = [low, midpoint]
    elif value >= high:
        envelope = [midpoint, high]
    else:
        envelope = [value, value]
    if envelope == [low, high] or not envelope[0] <= value <= envelope[1]:
        raise AssertionError("runtime envelope must be strict and contain the request value")
    return envelope


def synthetic_policies(count: int) -> list[dict[str, Any]]:
    """Deterministic non-matching registered policies for exp-24."""

    policies = []
    for index in range(count):
        tag = f"{index:04d}"
        policies.append(
            {
                "policy_id": f"synthetic:p{tag}",
                "issuer": "issuer:synthetic",
                "subject": f"subject:synthetic:p{tag}",
                "source_zone": f"synthetic_source_{tag}",
                "target_zone": f"synthetic_target_{tag}",
                "conduits": [f"c_synthetic_{tag}"],
                "assets": [f"synthetic_asset_{tag}"],
                "actions": ["read", "write"],
                "parameter": [0, 100],
                "ticks": [100, 200],
                "modes": ["normal", "maintenance"],
                "required_sequence": ["authenticate"],
            }
        )
    return policies


def _scope_fields(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject": scope["subject"],
        "source_zone": scope["source_zone"],
        "target_zone": scope["target_zone"],
        "conduits": list(scope["conduits"]),
        "assets": list(scope["assets"]),
        "actions": list(scope["actions"]),
        "parameter": list(scope["parameter"]),
        "ticks": list(scope["ticks"]),
        "modes": list(scope["modes"]),
        "required_sequence": list(scope["required_sequence"]),
    }


class _Builder:
    def __init__(self, table: dict[str, Any], compiled_dir: Path) -> None:
        self.table = table
        self.roots, self.delegations = expand_scopes(table)
        self.scope_by_id = {scope["scope_id"]: scope for scope in [*self.roots, *self.delegations]}
        self.capabilities: dict[str, Capability] = {}
        self.registry: dict[str, dict[str, Any]] = {}
        self.anchors: dict[str, str] = {}
        self.issuer_keys: dict[str, bytes] = {}
        self.subject_keys: dict[str, tuple[bytes, bytes]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}
        self.chains: dict[str, list[tuple[bytes, bytes]]] = {}
        self.leaf_fields: dict[str, dict[str, Any]] = {}
        self._compile(compiled_dir)
        self._issue_scope_tokens()

    def _subject_key(self, subject: str) -> tuple[bytes, bytes]:
        if subject not in self.subject_keys:
            self.subject_keys[subject] = test_keypair("subject", subject)
        return self.subject_keys[subject]

    def _compile(self, compiled_dir: Path) -> None:
        compiled_dir.mkdir(parents=True, exist_ok=False)
        for architecture in self.table["architectures"]:
            selected = [s for s in self.roots if s["architecture"] == architecture["id"]]
            document_path = compiled_dir / f"{architecture['id']}.json"
            _write_json(document_path, architecture_document(architecture, self.roots))
            compiled = Architecture.load(document_path).compile_all()
            if len(compiled) != len(selected):
                raise AssertionError("compiler did not return one root per frozen grant")
            for scope, capability in zip(selected, compiled):
                self.capabilities[scope["scope_id"]] = capability
                policy_id = f"{scope['architecture']}:{scope['grant_id']}"
                self.registry[policy_id] = {
                    "policy_id": policy_id,
                    "issuer": capability.issuer,
                    "subject": capability.subject,
                    "source_zone": capability.source_zone,
                    "target_zone": capability.target_zone,
                    "conduits": sorted(capability.conduits),
                    "assets": sorted(capability.assets),
                    "actions": sorted(capability.actions),
                    "parameter": capability.parameter.to_list(),
                    "ticks": capability.ticks.to_list(),
                    "modes": sorted(capability.modes),
                    "required_sequence": list(capability.required_sequence),
                }
        for scope in self.delegations:
            parent = self.capabilities[scope["parent_scope_id"]]
            self.capabilities[scope["scope_id"]] = parent.attenuate(
                capability_id=scope["scope_id"],
                subject=scope["subject"],
                conduits=scope["conduits"],
                assets=scope["assets"],
                actions=scope["actions"],
                parameter=Interval.from_pair(scope["parameter"]),
                ticks=Interval.from_pair(scope["ticks"]),
                modes=scope["modes"],
                required_sequence=scope["required_sequence"],
            )

    def _issue(
        self,
        *,
        token_id: str,
        policy_id: str,
        fields: dict[str, Any],
        depth: int,
        parent_id: str | None,
    ) -> None:
        public_key, _ = self._subject_key(fields["subject"])
        if parent_id is None:
            issuer = fields["issuer"]
            if issuer not in self.issuer_keys:
                issuer_public, issuer_secret = test_keypair("issuer", issuer)
                self.issuer_keys[issuer] = issuer_secret
                self.anchors[issuer] = issuer_public.hex()
            signing_key = self.issuer_keys[issuer]
            previous = None
            chain: list[tuple[bytes, bytes]] = []
        else:
            parent = self.tokens[parent_id]
            signing_key = self._subject_key(parent["subject"])[1]
            previous = parent["digest"]
            chain = list(self.chains[parent_id])
        payload = token_payload(
            token_id=token_id,
            policy_id=policy_id,
            issuer=fields["issuer"],
            subject=fields["subject"],
            subject_public_key=public_key,
            source_zone=fields["source_zone"],
            target_zone=fields["target_zone"],
            conduits=fields["conduits"],
            assets=fields["assets"],
            actions=fields["actions"],
            parameter=tuple(fields["parameter"]),
            ticks=tuple(fields["ticks"]),
            modes=fields["modes"],
            required_sequence=fields["required_sequence"],
            depth=depth,
            previous_digest=previous,
        )
        signature = sign(payload, signing_key)
        self.tokens[token_id] = {
            "subject": fields["subject"],
            "digest": token_digest(payload, signature),
            "depth": depth,
            "bytes": len(payload) + len(signature),
        }
        self.chains[token_id] = [*chain, (payload, signature)]
        self.leaf_fields[token_id] = _scope_fields(fields)

    def _issue_scope_tokens(self) -> None:
        for scope in [*self.roots, *self.delegations]:
            policy_id = f"{scope['architecture']}:{scope['grant_id']}"
            if scope["depth"] == 0:
                registered = self.registry[policy_id]
                fields = {**registered, "subject": scope["subject"]}
            else:
                fields = {**scope}
            self._issue(
                token_id=scope["scope_id"],
                policy_id=policy_id,
                fields=fields,
                depth=scope["depth"],
                parent_id=scope["parent_scope_id"],
            )

    def runtime_child(self, scope_id: str, envelope: list[float], ordinal: int) -> str:
        scope = self.scope_by_id[scope_id]
        token_id = f"{scope_id}:rt{ordinal:04d}"
        fields = {**self.leaf_fields[scope_id], "issuer": scope["issuer"]}
        low, high = fields["parameter"]
        fields["parameter"] = [max(low, envelope[0]), min(high, envelope[1])]
        self._issue(
            token_id=token_id,
            policy_id=f"{scope['architecture']}:{scope['grant_id']}",
            fields=fields,
            depth=scope["depth"] + 1,
            parent_id=scope_id,
        )
        return token_id


def _request_fields(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "zs": request["source_zone"],
        "zd": request["target_zone"],
        "k": request["conduit"],
        "a": request["asset"],
        "o": request["action"],
        "u": request["value"],
    }


def _context(request: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    context = {
        "tick": request["tick"],
        "mode": request["mode"],
        "history": list(request["history"]),
        "complete": True,
        "high_risk": False,
        "envelope": None,
    }
    context.update(overrides)
    return context


def _reference_engine_decision(
    capability: Capability, subject: str, request: dict[str, Any], context: dict[str, Any]
) -> tuple[list[Any], Capability | None]:
    """Pre-serialization reference path: ``PolicyEngine`` plus ``EffectBinding``."""

    action_request = ActionRequest(
        subject=subject,
        source_zone=request["zs"],
        target_zone=request["zd"],
        conduit=request["k"],
        asset=request["a"],
        action=request["o"],
        value=request["u"],
        tick=context["tick"],
        mode=context["mode"],
        history=tuple(context["history"]),
        context_complete=context["complete"],
        high_risk=context["high_risk"],
        runtime_parameter=(
            None if context["envelope"] is None else Interval.from_pair(context["envelope"])
        ),
    )
    decision = PolicyEngine().evaluate(capability, action_request)
    derived = decision.derived_capability
    try:
        emitted = EffectBinding("read", capability.parameter.low).emitted_action(
            capability, action_request, decision
        )
    except EffectContractError:
        return ["deny", None, None, None, None], None
    if decision.effect.value == "attenuate":
        return [
            "attenuate",
            None,
            None,
            derived.parameter.low,
            derived.parameter.high,
        ], derived
    if emitted is None:
        return [decision.effect.value, None, None, None, None], derived
    return [decision.effect.value, emitted.operation, emitted.value, None, None], derived


def _iter_cases(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def build(
    root: Path,
    output_dir: Path,
    *,
    policy_table: str = DEFAULT_POLICY_TABLE,
    exp07_cases: str = DEFAULT_EXP07_CASES,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite corpus directory: {output_dir}")
    table_path = root / policy_table
    cases_path = root / exp07_cases
    table = json.loads(table_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True)
    builder = _Builder(table, output_dir / "compiled_inputs")

    variants: dict[str, list[dict[str, Any]]] = {name: [] for name in VARIANTS}
    reference_mismatches: list[dict[str, Any]] = []
    unit_counter = {name: 0 for name in VARIANTS}

    def add_step(
        variant: str,
        *,
        unit: int,
        case_id: str,
        kind: str,
        leaf: str,
        subject: str,
        request: dict[str, Any],
        context: dict[str, Any],
        capability: Capability,
    ) -> Capability | None:
        scope = builder.leaf_fields[leaf]
        expected = oracle.expected_decision(scope, subject, request, context)
        reference, derived = _reference_engine_decision(capability, subject, request, context)
        if reference != expected:
            reference_mismatches.append(
                {"variant": variant, "case": case_id, "kind": kind,
                 "oracle": expected, "reference_engine": reference}
            )
        step = {
            "step": len(variants[variant]),
            "unit": unit,
            "case": case_id,
            "kind": kind,
            "leaf": leaf,
            "depth": builder.tokens[leaf]["depth"],
            "chain": builder.tokens[leaf]["depth"] + 1,
            "subject": subject,
            "request": request,
            "context": context,
            "expected": expected,
        }
        if variant == "sint_subset":
            step["sint_expected"] = oracle.sint_expected_decision(scope, subject, request, context)
        variants[variant].append(step)
        return derived

    valid_records: list[dict[str, Any]] = []
    case_count = 0
    for record in _iter_cases(cases_path):
        case_count += 1
        request = _request_fields(record["request"])
        context = _context(record["request"])
        subject = record["request"]["subject"]
        scope_id = record["scope_id"]
        capability = builder.capabilities[scope_id]
        selected = ["main"]
        if scope_id.startswith(SCALE_POLICY_ID + ":d"):
            selected.append(f"scale_d{record['depth']}")
        if record["mutation"] is None or record["mutation"] in SINT_MUTATIONS:
            selected.append("sint_subset")
        for variant in selected:
            add_step(
                variant,
                unit=unit_counter[variant],
                case_id=record["case_id"],
                kind="single",
                leaf=scope_id,
                subject=subject,
                request=request,
                context=context,
                capability=capability,
            )
            unit_counter[variant] += 1
        if record["kind"] == "valid":
            valid_records.append(record)

    for ordinal, record in enumerate(valid_records):
        scope_id = record["scope_id"]
        scope = builder.leaf_fields[scope_id]
        subject = record["request"]["subject"]
        base = _request_fields(record["request"])
        envelope = strict_runtime_envelope(scope["parameter"], base["u"])
        child_id = builder.runtime_child(scope_id, envelope, ordinal)
        child_high = builder.leaf_fields[child_id]["parameter"][1]
        unit = unit_counter["main"]
        unit_counter["main"] += 1
        trace_id = f"{record['case_id']}:composed"
        derived = add_step(
            "main", unit=unit, case_id=trace_id, kind="attenuate", leaf=scope_id,
            subject=subject, request=base,
            context=_context(record["request"], envelope=envelope),
            capability=builder.capabilities[scope_id],
        )
        if derived is None:
            raise AssertionError(f"reference engine did not attenuate {trace_id}")
        composed = (
            ("defer", base, _context(record["request"], complete=False)),
            ("allow", base, _context(record["request"])),
            ("rewrite", {**base, "u": child_high + 1.0}, _context(record["request"])),
            ("deny", {**base, "o": "outside_action"}, _context(record["request"])),
        )
        for kind, request, context in composed:
            add_step(
                "main", unit=unit, case_id=trace_id, kind=kind, leaf=child_id,
                subject=subject, request=request, context=context, capability=derived,
            )

    files: dict[str, str] = {}
    variant_summary: dict[str, Any] = {}
    for variant, steps in variants.items():
        directory = output_dir / variant
        directory.mkdir()
        with (directory / "envelopes.bin").open("wb") as envelopes, (
            directory / "steps.jsonl"
        ).open("w", encoding="utf-8") as step_file:
            for index, step in enumerate(steps):
                request_bytes = request_payload(
                    request_id=f"{variant}:{index:06d}",
                    source_zone=step["request"]["zs"],
                    target_zone=step["request"]["zd"],
                    conduit=step["request"]["k"],
                    asset=step["request"]["a"],
                    action=step["request"]["o"],
                    value=step["request"]["u"],
                )
                envelope = encode_envelope(builder.chains[step["leaf"]], request_bytes)
                envelopes.write(_U32.pack(len(envelope)))
                envelopes.write(envelope)
                step_file.write(json.dumps(step, sort_keys=True, separators=(",", ":")) + "\n")
        effects: dict[str, int] = {}
        depths: dict[str, int] = {}
        kinds: dict[str, int] = {}
        for step in steps:
            effects[step["expected"][0]] = effects.get(step["expected"][0], 0) + 1
            depths[str(step["depth"])] = depths.get(str(step["depth"]), 0) + 1
            kinds[step["kind"]] = kinds.get(step["kind"], 0) + 1
        variant_summary[variant] = {
            "steps": len(steps),
            "units": unit_counter[variant],
            "expected_effects": dict(sorted(effects.items())),
            "chain_depths": dict(sorted(depths.items())),
            "step_kinds": dict(sorted(kinds.items())),
        }
        if variant == "sint_subset":
            sint: dict[str, int] = {}
            for step in steps:
                sint[step["sint_expected"]] = sint.get(step["sint_expected"], 0) + 1
            variant_summary[variant]["sint_expected"] = dict(sorted(sint.items()))

    _write_json(output_dir / "scopes.json", builder.leaf_fields)
    _write_json(output_dir / "registry.json", builder.registry)
    _write_json(output_dir / "anchors.json", builder.anchors)
    token_bytes: dict[str, list[int]] = {}
    for token in builder.tokens.values():
        token_bytes.setdefault(str(token["depth"]), []).append(token["bytes"])
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(output_dir))] = _sha256(path)
    manifest = {
        "corpus_version": CORPUS_VERSION,
        "key_domain": KEY_DOMAIN,
        "inputs": {policy_table: _sha256(table_path), exp07_cases: _sha256(cases_path)},
        "exp07_cases": case_count,
        "scale_policy_id": SCALE_POLICY_ID,
        "registered_policies": len(builder.registry),
        "issued_tokens": len(builder.tokens),
        "token_bytes_by_depth": {
            depth: {"count": len(sizes), "minimum": min(sizes), "maximum": max(sizes)}
            for depth, sizes in sorted(token_bytes.items())
        },
        "variants": variant_summary,
        "reference_engine_mismatches": len(reference_mismatches),
        "reference_engine_mismatch_examples": reference_mismatches[:20],
        "files": files,
    }
    manifest["fingerprint"] = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    _write_json(output_dir / "manifest.json", manifest)
    if reference_mismatches:
        raise AssertionError(f"reference engine disagrees with oracle: {reference_mismatches[:3]}")
    return manifest


def verify(corpus_dir: Path) -> dict[str, Any]:
    """Recompute every corpus file hash against ``manifest.json``."""

    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    mismatches = {
        relative: expected
        for relative, expected in manifest["files"].items()
        if _sha256(corpus_dir / relative) != expected
    }
    if mismatches:
        raise RuntimeError(f"corpus file hash mismatch: {sorted(mismatches)}")
    return manifest


def load_variant(corpus_dir: Path, variant: str) -> tuple[list[bytes], list[dict[str, Any]]]:
    directory = corpus_dir / variant
    data = (directory / "envelopes.bin").read_bytes()
    envelopes: list[bytes] = []
    position = 0
    while position < len(data):
        (length,) = _U32.unpack_from(data, position)
        position += 4
        envelopes.append(data[position : position + length])
        position += length
    with (directory / "steps.jsonl").open("r", encoding="utf-8") as handle:
        steps = [json.loads(line) for line in handle]
    if len(steps) != len(envelopes):
        raise RuntimeError(f"{variant}: step and envelope counts differ")
    return envelopes, steps


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify the C5 corpus.")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output-dir", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--corpus-dir", type=Path, required=True)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    if arguments.command == "build":
        manifest = build(root, arguments.output_dir)
    else:
        manifest = verify(arguments.corpus_dir)
    summary = {key: manifest[key] for key in ("fingerprint", "variants", "reference_engine_mismatches")}
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
