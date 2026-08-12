"""
Unit tests for Google OAuth/OIDC authentication endpoint and service logic.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.models import UserInDB
from app.dependencies.repositories import (
    get_user_repository,
    get_refresh_token_repository,
)
from app.core.security import hash_password


class FakeUserRepository:
    """In-memory UserRepository for unit testing"""

    def __init__(self):
        self.users = {}

    def get_by_id(self, user_id: str):
        """Get user by id"""
        return self.users.get(user_id)

    def get_by_email(self, email: str):
        """Get user by email"""
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    def get_by_google_id(self, google_id: str):
        """Get user by Google sub ID"""
        for user in self.users.values():
            if user.google_id == google_id:
                return user
        return None

    def create_user(self, user: UserInDB):
        """Create a new user"""
        self.users[user.id] = user

    def link_google_account(self, user_id: str, google_id: str, email_verified_at=None):
        """Link Google sub ID to an existing user and update email_verified_at if provided"""
        if user_id in self.users:
            user = self.users[user_id]
            updated_user = user.model_copy(
                update={
                    "google_id": google_id,
                    "email_verified_at": email_verified_at or user.email_verified_at,
                }
            )
            self.users[user_id] = updated_user
            return True
        return False


class FakeRefreshTokenRepository:
    """In-memory RefreshTokenRepository for unit testing"""

    def __init__(self):
        self.tokens = {}

    def create_token(self, token_record):
        """Create a new token"""
        self.tokens[token_record.id] = token_record

    def get_by_hash(self, token_hash):
        """Get token by hash"""
        for token in self.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None


client = TestClient(app)
fake_user_repo = FakeUserRepository()
fake_token_repo = FakeRefreshTokenRepository()


@pytest.fixture(autouse=True)
def setup_dependencies():
    """Reset fake repositories and override FastAPI dependencies for each test"""
    fake_user_repo.users.clear()
    fake_token_repo.tokens.clear()
    app.dependency_overrides[get_user_repository] = lambda: fake_user_repo
    app.dependency_overrides[get_refresh_token_repository] = lambda: fake_token_repo
    yield
    app.dependency_overrides.clear()
    fake_user_repo.users.clear()
    fake_token_repo.tokens.clear()


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_new_user(mock_verify):
    """
    Test signing in with Google for a brand new user
    creates account with password=None and barangay_city=''
    """
    mock_verify.return_value = {
        "sub": "google-sub-12345",
        "email": "newuser@example.com",
        "email_verified": True,
        "given_name": "Juan",
        "family_name": "Dela Cruz",
    }

    response = client.post(
        "/auth/google",
        json={"credential": "mock_google_id_token_123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["first_name"] == "Juan"
    assert data["last_name"] == "Dela Cruz"
    assert data["barangay_city"] == ""

    # Verify cookies set
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    # Verify repository storage
    user_db = fake_user_repo.get_by_google_id("google-sub-12345")
    assert user_db is not None
    assert user_db.password is None
    assert user_db.email == "newuser@example.com"
    assert user_db.email_verified_at is not None


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_existing_user_linking(mock_verify):
    """Test signing in with Google links google_id to existing email user without altering password or location"""
    existing_user = UserInDB(
        id="existing-user-id-999",
        email="existing@example.com",
        password=hash_password("ExistingPassword123!"),
        first_name="Maria",
        last_name="Clara",
        barangay_city="Quezon City",
        is_active=True,
    )
    fake_user_repo.create_user(existing_user)

    mock_verify.return_value = {
        "sub": "google-sub-67890",
        "email": "existing@example.com",
        "email_verified": True,
        "given_name": "Maria",
        "family_name": "Clara",
    }

    response = client.post(
        "/auth/google",
        json={"credential": "mock_google_id_token_456"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "existing-user-id-999"
    assert data["barangay_city"] == "Quezon City"

    # Verify document updated in repo
    user_db = fake_user_repo.get_by_id("existing-user-id-999")
    assert user_db.google_id == "google-sub-67890"
    assert user_db.password is not None  # Password preserved
    assert user_db.barangay_city == "Quezon City"  # Barangay preserved
    assert user_db.email_verified_at is not None


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_unverified_email(mock_verify):
    """Test Google login rejects tokens where email_verified is False"""
    mock_verify.return_value = {
        "sub": "google-sub-unverified",
        "email": "unverified@example.com",
        "email_verified": False,
        "given_name": "Unverified",
        "family_name": "User",
    }

    response = client.post(
        "/auth/google",
        json={"credential": "mock_unverified_token"},
    )

    assert response.status_code == 400
    assert "Google email is not verified" in response.json()["detail"]


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_invalid_credential(mock_verify):
    """Test Google login rejects invalid ID tokens"""
    mock_verify.side_effect = ValueError("Token expired")

    response = client.post(
        "/auth/google",
        json={"credential": "expired_token"},
    )

    assert response.status_code == 401
    assert "Invalid Google credential" in response.json()["detail"]


def test_password_login_rejects_google_only_user():
    """Test local password login rejects Google-only users (password=None) safely"""
    google_user = UserInDB(
        id="google-only-user-id",
        email="sso@example.com",
        password=None,
        first_name="SSO",
        last_name="User",
        barangay_city="Pasig",
        google_id="google-sub-999",
        is_active=True,
    )
    fake_user_repo.create_user(google_user)

    response = client.post(
        "/auth/login",
        json={"email": "sso@example.com", "password": "AnyPassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
