from __future__ import annotations

"""Envelope and token encoding for the C5 reference PEP.

Envelope layout (all integers big-endian):

    "ZCE1" | u8 n | n x (u16 len | token payload | 64-byte Ed25519 signature)
           | u16 len | request payload

Payloads are canonical JSON: UTF-8/ASCII, sorted keys, no insignificant
whitespace, no NaN or infinity.  A signature covers exactly the payload bytes
that follow its length prefix, so the verifier never re-serializes a payload.
The request payload is not signed: request origin is authenticated by the
transport session, which hands the authenticated subject to the PEP.
"""

import hashlib
import json
import struct
from typing import Any, Iterable


MAGIC = b"ZCE1"
SIGNATURE_BYTES = 64
PUBLIC_KEY_BYTES = 32
MAX_CHAIN = 8
MAX_PAYLOAD = 4096
MAX_ENVELOPE = 65536
WIRE_VERSION = 1

TOKEN_KEYS = frozenset(
    {"A", "Iu", "It", "K", "L", "M", "O", "d", "id", "iss", "pol", "prev", "spk", "sub", "v", "zd", "zs"}
)
REQUEST_KEYS = frozenset({"a", "k", "o", "rid", "u", "v", "zd", "zs"})

_U16 = struct.Struct(">H")


class WireError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def token_digest(payload: bytes, signature: bytes) -> str:
    """Hex SHA-256 of the signed token bytes; a child's ``prev`` field."""

    return hashlib.sha256(payload + signature).hexdigest()


def token_payload(
    *,
    token_id: str,
    policy_id: str,
    issuer: str,
    subject: str,
    subject_public_key: bytes,
    source_zone: str,
    target_zone: str,
    conduits: Iterable[str],
    assets: Iterable[str],
    actions: Iterable[str],
    parameter: tuple[float, float],
    ticks: tuple[float, float],
    modes: Iterable[str],
    required_sequence: Iterable[str],
    depth: int,
    previous_digest: str | None,
) -> bytes:
    if len(subject_public_key) != PUBLIC_KEY_BYTES:
        raise WireError("subject public key must be 32 bytes")
    return canonical_json(
        {
            "A": sorted(assets),
            "Iu": [parameter[0], parameter[1]],
            "It": [ticks[0], ticks[1]],
            "K": sorted(conduits),
            "L": list(required_sequence),
            "M": sorted(modes),
            "O": sorted(actions),
            "d": depth,
            "id": token_id,
            "iss": issuer,
            "pol": policy_id,
            "prev": previous_digest,
            "spk": subject_public_key.hex(),
            "sub": subject,
            "v": WIRE_VERSION,
            "zd": target_zone,
            "zs": source_zone,
        }
    )


def request_payload(
    *,
    request_id: str,
    source_zone: str,
    target_zone: str,
    conduit: str,
    asset: str,
    action: str,
    value: float,
) -> bytes:
    return canonical_json(
        {
            "a": asset,
            "k": conduit,
            "o": action,
            "rid": request_id,
            "u": value,
            "v": WIRE_VERSION,
            "zd": target_zone,
            "zs": source_zone,
        }
    )


def encode_envelope(tokens: list[tuple[bytes, bytes]], request: bytes) -> bytes:
    if not 1 <= len(tokens) <= MAX_CHAIN:
        raise WireError("chain length outside 1..8")
    parts = [MAGIC, bytes([len(tokens)])]
    for payload, signature in tokens:
        if len(payload) > MAX_PAYLOAD or len(signature) != SIGNATURE_BYTES:
            raise WireError("token payload too large or signature malformed")
        parts.extend((_U16.pack(len(payload)), payload, signature))
    if len(request) > MAX_PAYLOAD:
        raise WireError("request payload too large")
    parts.extend((_U16.pack(len(request)), request))
    envelope = b"".join(parts)
    if len(envelope) > MAX_ENVELOPE:
        raise WireError("envelope too large")
    return envelope


def split_envelope(data: bytes) -> tuple[list[tuple[bytes, bytes]], bytes]:
    """Return ``[(payload, signature), ...]`` and the request payload."""

    if len(data) > MAX_ENVELOPE or len(data) < 5 or data[:4] != MAGIC:
        raise WireError("bad envelope header")
    count = data[4]
    if not 1 <= count <= MAX_CHAIN:
        raise WireError("chain length outside 1..8")
    position = 5
    tokens = []
    for _ in range(count):
        if position + 2 > len(data):
            raise WireError("truncated token length")
        (length,) = _U16.unpack_from(data, position)
        position += 2
        end = position + length
        if length > MAX_PAYLOAD or end + SIGNATURE_BYTES > len(data):
            raise WireError("truncated token")
        tokens.append((data[position:end], data[end : end + SIGNATURE_BYTES]))
        position = end + SIGNATURE_BYTES
    if position + 2 > len(data):
        raise WireError("truncated request length")
    (length,) = _U16.unpack_from(data, position)
    position += 2
    if length > MAX_PAYLOAD or position + length != len(data):
        raise WireError("request length does not match envelope")
    return tokens, data[position:]
