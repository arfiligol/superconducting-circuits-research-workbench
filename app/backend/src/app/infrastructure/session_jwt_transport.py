from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

VerificationStatus = Literal["valid", "expired", "invalid"]

SESSION_COOKIE_NAME = "sc_session_access"
REFRESH_COOKIE_NAME = "sc_session_refresh"
APP_CONTEXT_COOKIE_NAME = "sc_app_context"
DEFAULT_SESSION_TOKEN_LIFETIME_SECONDS = 900


@dataclass(frozen=True)
class VerifiedSessionToken:
    status: VerificationStatus
    session_id: str | None = None


class SessionJwtTransport:
    def __init__(
        self,
        *,
        secret: str,
        token_lifetime_seconds: int = DEFAULT_SESSION_TOKEN_LIFETIME_SECONDS,
    ) -> None:
        self._secret = secret.encode("utf-8")
        self._token_lifetime_seconds = token_lifetime_seconds

    def issue_token(self, session_id: str) -> str:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=self._token_lifetime_seconds)
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sid": session_id,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        encoded_header = _encode_segment(header)
        encoded_payload = _encode_segment(payload)
        signing_input = f"{encoded_header}.{encoded_payload}"
        signature = _sign(signing_input, self._secret)
        return f"{signing_input}.{signature}"

    def verify_token(self, token: str) -> VerifiedSessionToken:
        parts = token.split(".")
        if len(parts) != 3:
            return VerifiedSessionToken(status="invalid")

        encoded_header, encoded_payload, signature = parts
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = _sign(signing_input, self._secret)
        if not hmac.compare_digest(signature, expected_signature):
            return VerifiedSessionToken(status="invalid")

        try:
            payload = _decode_segment(encoded_payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return VerifiedSessionToken(status="invalid")

        session_id = payload.get("sid")
        expires_at = payload.get("exp")
        if not isinstance(session_id, str) or not isinstance(expires_at, int):
            return VerifiedSessionToken(status="invalid")

        if datetime.now(UTC).timestamp() >= expires_at:
            return VerifiedSessionToken(status="expired", session_id=session_id)

        return VerifiedSessionToken(status="valid", session_id=session_id)

    @property
    def token_lifetime_seconds(self) -> int:
        return self._token_lifetime_seconds


def _encode_segment(payload: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")


def _decode_segment(segment: str) -> dict[str, object]:
    padding = "=" * (-len(segment) % 4)
    raw = base64.urlsafe_b64decode(f"{segment}{padding}")
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("JWT payload must be an object.")
    return decoded


def _sign(signing_input: str, secret: bytes) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(secret, signing_input.encode("utf-8"), hashlib.sha256).digest()
    ).rstrip(b"=").decode("ascii")
