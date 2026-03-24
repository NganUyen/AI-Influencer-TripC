"""
Authenticated token sealing for customer-owned OAuth credentials.

This avoids plain-text storage without introducing a new runtime dependency.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any, Dict

from config.settings import settings


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class CustomerTokenVault:
    @staticmethod
    def _key() -> bytes:
        secret = (
            settings.CUSTOMER_TOKEN_ENCRYPTION_KEY
            or settings.JWT_SECRET_KEY
            or settings.SUPABASE_SERVICE_ROLE_KEY
        )
        return hashlib.sha256(secret.encode("utf-8")).digest()

    @classmethod
    def _keystream(cls, nonce: bytes, length: int) -> bytes:
        key = cls._key()
        output = bytearray()
        counter = 0
        while len(output) < length:
            block = hmac.new(
                key,
                nonce + counter.to_bytes(4, "big"),
                hashlib.sha256,
            ).digest()
            output.extend(block)
            counter += 1
        return bytes(output[:length])

    @classmethod
    def seal(cls, payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        nonce = os.urandom(16)
        keystream = cls._keystream(nonce, len(raw))
        ciphertext = bytes(left ^ right for left, right in zip(raw, keystream))
        tag = hmac.new(cls._key(), nonce + ciphertext, hashlib.sha256).digest()
        return ".".join(
            [
                _b64url_encode(nonce),
                _b64url_encode(tag),
                _b64url_encode(ciphertext),
            ]
        )

    @classmethod
    def open(cls, token: str) -> Dict[str, Any]:
        nonce_part, tag_part, ciphertext_part = token.split(".", 2)
        nonce = _b64url_decode(nonce_part)
        tag = _b64url_decode(tag_part)
        ciphertext = _b64url_decode(ciphertext_part)

        expected_tag = hmac.new(cls._key(), nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Invalid encrypted token payload")

        keystream = cls._keystream(nonce, len(ciphertext))
        raw = bytes(left ^ right for left, right in zip(ciphertext, keystream))
        return json.loads(raw.decode("utf-8"))
