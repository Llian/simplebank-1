from uuid import uuid4

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

_DEFAULT_SECRET = "test-secret-1234567890-abcdefghij"  # noqa: S105  # nosec B105 -- test fixture
_OTHER_SECRET = "different-secret-0987654-klmnopqrst"  # noqa: S105  # nosec B105 -- test fixture


def _settings(**overrides: object) -> Settings:
    overrides.setdefault("jwt_secret_key", _DEFAULT_SECRET)
    return Settings(**overrides)  # type: ignore[arg-type]


@pytest.mark.unit
def test_hash_and_verify_password_roundtrip() -> None:
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed) is True


@pytest.mark.unit
def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery")
    assert verify_password("wrong-password", hashed) is False


@pytest.mark.unit
def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


@pytest.mark.unit
def test_access_token_roundtrip() -> None:
    settings = _settings()
    session_id = uuid4()
    token, _ = create_access_token(username="alice", session_id=session_id, settings=settings)
    payload = decode_access_token(token, settings=settings)
    assert payload.username == "alice"
    assert payload.session_id == session_id


@pytest.mark.unit
def test_access_token_expired() -> None:
    settings = _settings(access_token_ttl_minutes=-1)
    token, _ = create_access_token(username="alice", session_id=uuid4(), settings=settings)
    with pytest.raises(TokenError):
        decode_access_token(token, settings=settings)


@pytest.mark.unit
def test_access_token_tampered_signature() -> None:
    settings = _settings()
    token, _ = create_access_token(username="alice", session_id=uuid4(), settings=settings)
    other_settings = _settings(jwt_secret_key=_OTHER_SECRET)
    with pytest.raises(TokenError):
        decode_access_token(token, settings=other_settings)


@pytest.mark.unit
def test_decode_access_token_rejects_malformed_token() -> None:
    settings = _settings()
    with pytest.raises(TokenError):
        decode_access_token("not-a-jwt", settings=settings)


@pytest.mark.unit
def test_refresh_token_roundtrip() -> None:
    settings = _settings()
    session_id = uuid4()
    token, _ = create_refresh_token(session_id=session_id, settings=settings)
    assert decode_refresh_token(token, settings=settings) == session_id


@pytest.mark.unit
def test_refresh_token_rejects_access_token() -> None:
    settings = _settings()
    access_token, _ = create_access_token(username="alice", session_id=uuid4(), settings=settings)
    with pytest.raises(TokenError):
        decode_refresh_token(access_token, settings=settings)


@pytest.mark.unit
def test_access_token_rejects_refresh_token() -> None:
    settings = _settings()
    refresh_token, _ = create_refresh_token(session_id=uuid4(), settings=settings)
    with pytest.raises(TokenError):
        decode_access_token(refresh_token, settings=settings)


@pytest.mark.unit
def test_decode_refresh_token_expired() -> None:
    settings = _settings(refresh_token_ttl_hours=-1)
    token, _ = create_refresh_token(session_id=uuid4(), settings=settings)
    with pytest.raises(TokenError):
        decode_refresh_token(token, settings=settings)


@pytest.mark.unit
def test_decode_access_token_raw_jwt_expiry_matches_settings_ttl() -> None:
    settings = _settings()
    session_id = uuid4()
    token, expires_at = create_access_token(
        username="alice", session_id=session_id, settings=settings
    )
    raw_payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    assert raw_payload["exp"] == int(expires_at.timestamp())
