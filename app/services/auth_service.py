"""
Auth service layer containing authentication business logic.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from fastapi import HTTPException, status

from app.database.models import UserInDB, RefreshTokenInDB
from app.repositories.user import UserRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.schemas.auth import RegisterRequest, LoginRequest, UserResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token,
)
from app.core.config import REFRESH_TOKEN_EXPIRE_DAYS
from app.core.logging_config import bind_user_context

logger = logging.getLogger(__name__)


class AuthService:
    """Handles registrations, logins, token rotation, and logs"""

    def __init__(
        self, user_repo: UserRepository, refresh_token_repo: RefreshTokenRepository
    ):
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo

    def register(self, data: RegisterRequest) -> str:
        """Register a new user in the database"""
        existing_user = self.user_repo.get_by_email(data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        user_id = str(uuid.uuid4())
        user_db = UserInDB(
            id=user_id,
            email=data.email,
            password=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            is_active=True,
            barangay_city=data.barangay_city,
        )

        self.user_repo.create_user(user_db)
        bind_user_context(user_id)
        logger.info("User registered successfully")
        return user_id

    def login(self, data: LoginRequest) -> Tuple[UserResponse, str, str]:
        """Authenticate user credentials and generate access/refresh tokens"""
        user_db = self.user_repo.get_by_email(data.email)
        if not user_db or not verify_password(data.password, user_db.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user_id = user_db.id

        access_token = create_access_token(user_id)
        raw_refresh_token = generate_refresh_token()
        hashed_refresh_token = hash_token(raw_refresh_token)

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )
        refresh_token_record = RefreshTokenInDB(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=hashed_refresh_token,
            expires_at=expires_at,
            revoked=False,
            created_at=datetime.now(timezone.utc),
        )

        self.refresh_token_repo.create_token(refresh_token_record)
        bind_user_context(user_id)
        logger.info("User logged in successfully")

        response_user = UserResponse(
            id=user_id,
            email=user_db.email,
            first_name=user_db.first_name,
            last_name=user_db.last_name,
            barangay_city=user_db.barangay_city,
        )

        return response_user, access_token, raw_refresh_token

    def refresh_token(self, raw_refresh_token: str) -> Tuple[str, str]:
        """Rotate a refresh token, revoking the old one and creating a new one"""
        hashed_refresh_token = hash_token(raw_refresh_token)
        token_record = self.refresh_token_repo.get_by_hash(hashed_refresh_token)

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # Convert expires_at to aware datetime if naive
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if token_record.revoked or expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Expired or revoked refresh token",
            )

        user_id = token_record.user_id

        # Revoke old token
        self.refresh_token_repo.revoke_token_by_id(token_record.id)

        # Generate new tokens (Rotation)
        new_access_token = create_access_token(user_id)
        new_raw_refresh_token = generate_refresh_token()
        new_hashed_refresh_token = hash_token(new_raw_refresh_token)

        new_expires_at = datetime.now(timezone.utc) + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )
        new_refresh_token_record = RefreshTokenInDB(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=new_hashed_refresh_token,
            expires_at=new_expires_at,
            revoked=False,
            created_at=datetime.now(timezone.utc),
        )

        self.refresh_token_repo.create_token(new_refresh_token_record)
        bind_user_context(user_id)
        logger.info("Token refreshed successfully")

        return new_access_token, new_raw_refresh_token

    def logout(self, raw_refresh_token: Optional[str]) -> None:
        """Revoke a refresh token if provided"""
        if raw_refresh_token:
            hashed_refresh_token = hash_token(raw_refresh_token)
            token_record = self.refresh_token_repo.get_by_hash(hashed_refresh_token)
            if token_record:
                bind_user_context(token_record.user_id)

            self.refresh_token_repo.revoke_token_by_hash(hashed_refresh_token)
            logger.info("User logged out successfully")
