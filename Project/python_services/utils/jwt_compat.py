"""
Minimal JWT compatibility layer for HS256 tokens.

Use PyJWT when available and fall back to this implementation otherwise.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Iterable


class PyJWTError(Exception):
    pass


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _json_dumps(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def encode(payload: dict[str, Any], key: str, algorithm: str = "HS256") -> str:
    if algorithm != "HS256":
        raise PyJWTError(f"Unsupported JWT algorithm: {algorithm}")

    header = {"alg": algorithm, "typ": "JWT"}
    encoded_header = _b64url_encode(_json_dumps(header))
    encoded_payload = _b64url_encode(_json_dumps(payload))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        str(key).encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def decode(
    token: str,
    key: str,
    algorithms: Iterable[str] | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError as exc:
        raise PyJWTError("Invalid JWT format") from exc

    header = json.loads(_b64url_decode(encoded_header))
    algorithm = header.get("alg")
    allowed_algorithms = list(algorithms or ["HS256"])
    if algorithm not in allowed_algorithms:
        raise PyJWTError(f"Unsupported JWT algorithm: {algorithm}")
    if algorithm != "HS256":
        raise PyJWTError(f"Unsupported JWT algorithm: {algorithm}")

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(
        str(key).encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(encoded_signature)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise PyJWTError("JWT signature verification failed")

    payload = json.loads(_b64url_decode(encoded_payload))
    exp = payload.get("exp")
    if exp is not None and int(exp) <= int(time.time()):
        raise PyJWTError("JWT has expired")

    if audience is not None:
        token_audience = payload.get("aud")
        if isinstance(token_audience, list):
            valid_audience = audience in token_audience
        else:
            valid_audience = token_audience == audience
        if not valid_audience:
            raise PyJWTError("JWT audience is invalid")

    return payload
