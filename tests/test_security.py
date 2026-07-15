"""
Tests for app.core.security
"""

from datetime import datetime, timezone
from jose import jwt

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET,
)
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_different_string():
    """Hashing a password should not return the original password."""
    password = "my_secure_password"

    hashed = hash_password(password)

    assert hashed != password
    assert isinstance(hashed, str)


def test_hash_password_generates_bcrypt_hash():
    """Hashed password should use bcrypt."""
    password = "my_secure_password"

    hashed = hash_password(password)

    assert hashed.startswith("$2")


def test_verify_password_returns_true_for_correct_password():
    """Correct password should verify successfully."""
    password = "my_secure_password"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_returns_false_for_incorrect_password():
    """Incorrect password should not verify."""
    password = "my_secure_password"
    hashed = hash_password(password)

    assert verify_password("wrong_password", hashed) is False


def test_create_access_token_returns_jwt_string():
    """create_access_token should return a JWT string."""
    token = create_access_token("user123")

    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # JWT has 3 sections


def test_create_access_token_contains_correct_subject():
    """JWT should contain the expected user ID."""
    user_id = "user123"

    token = create_access_token(user_id)

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    assert payload["sub"] == user_id


def test_create_access_token_contains_expiration():
    """JWT should contain an expiration timestamp."""
    token = create_access_token("user123")

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    assert "exp" in payload


def test_create_access_token_expiration_is_in_future():
    """JWT expiration should be in the future."""
    token = create_access_token("user123")

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    expiration = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    assert expiration > datetime.now(timezone.utc)


def test_create_access_token_expiration_matches_config():
    """JWT expiration should approximately match the configured lifetime."""
    token = create_access_token("user123")

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    expiration = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    remaining = (expiration - datetime.now(timezone.utc)).total_seconds()

    expected = ACCESS_TOKEN_EXPIRE_MINUTES * 60

    # Allow a few seconds for test execution time.
    assert expected - 5 <= remaining <= expected
