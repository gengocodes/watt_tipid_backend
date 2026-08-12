"""
Auth service layer containing authentication business logic.
"""

import uuid
import logging
import json
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from fastapi import HTTPException, status, BackgroundTasks
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

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
from app.core.config import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    EMAIL_VERIFICATION_EXPIRE_MINUTES,
    EMAIL_VERIFICATION_RESEND_SECONDS,
    EMAIL_VERIFICATION_MAX_ATTEMPTS,
    GOOGLE_CLIENT_ID,
)
from app.core.logging_config import bind_user_context
from app.database.redis import redis_client
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    """Handles registrations, logins, token rotation, and logs"""

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        email_service: EmailService,
    ):
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo
        self.email_service = email_service

    async def register(
        self, data: RegisterRequest, background_tasks: BackgroundTasks
    ) -> str:
        """Stash registration info in Redis and send verification code"""
        normalized_email = data.email.strip().lower()
        existing_user = self.user_repo.get_by_email(normalized_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        data_key = f"register:data:{normalized_email}"
        code_key = f"register:code:{normalized_email}"
        cooldown_key = f"register:cooldown:{normalized_email}"

        # Hash password and prepare user details payload
        pending_data = {
            "email": normalized_email,
            "password_hash": hash_password(data.password),
            "first_name": data.first_name,
            "last_name": data.last_name,
            "barangay_city": data.barangay_city,
        }
        pending_data_json = json.dumps(pending_data)

        # Atomic SETNX with expiration (5 minutes)
        ttl_seconds = EMAIL_VERIFICATION_EXPIRE_MINUTES * 60
        success = await redis_client.set(
            data_key, pending_data_json, ex=ttl_seconds, nx=True
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification already pending.",
            )

        # Generate, hash, and store verification code
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        code_hash = hash_token(code)
        pending_code = {
            "code_hash": code_hash,
            "attempts": 0,
        }
        await redis_client.set(code_key, json.dumps(pending_code), ex=ttl_seconds)

        # Set resend cooldown (60 seconds)
        await redis_client.set(cooldown_key, "1", ex=EMAIL_VERIFICATION_RESEND_SECONDS)

        # Schedule async email delivery
        background_tasks.add_task(
            self.email_service.send_verification_email,
            normalized_email,
            code,
            "register",
        )

        logger.info("Initiated registration verification flow for %s", normalized_email)
        return normalized_email

    async def verify_register(self, email: str, code: str) -> str:
        """Verify the registration code, commit the user to DB, and delete Redis keys"""
        normalized_email = email.strip().lower()
        code_key = f"register:code:{normalized_email}"
        data_key = f"register:data:{normalized_email}"
        cooldown_key = f"register:cooldown:{normalized_email}"

        code_data_json = await redis_client.get(code_key)
        if not code_data_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired or not found. Please register again.",
            )

        code_data = json.loads(code_data_json)
        if code_data["attempts"] >= EMAIL_VERIFICATION_MAX_ATTEMPTS:
            await redis_client.delete(code_key, data_key, cooldown_key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Please register again.",
            )

        hashed_input = hash_token(code.strip())
        if code_data["code_hash"] != hashed_input:
            code_data["attempts"] += 1
            remaining = EMAIL_VERIFICATION_MAX_ATTEMPTS - code_data["attempts"]
            if remaining <= 0:
                await redis_client.delete(code_key, data_key, cooldown_key)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Too many failed attempts. Please register again.",
                )
            ttl = await redis_client.ttl(code_key)
            if ttl > 0:
                await redis_client.set(code_key, json.dumps(code_data), ex=ttl)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification code. {remaining} attempt(s) remaining.",
            )

        # Code is correct, retrieve user registration payload
        data_json = await redis_client.get(data_key)
        if not data_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration session expired. Please register again.",
            )

        reg_data = json.loads(data_json)
        user_id = str(uuid.uuid4())
        user_db = UserInDB(
            id=user_id,
            email=reg_data["email"],
            password=reg_data["password_hash"],
            first_name=reg_data["first_name"],
            last_name=reg_data["last_name"],
            is_active=True,
            barangay_city=reg_data["barangay_city"],
            email_verified_at=datetime.now(timezone.utc),
        )

        self.user_repo.create_user(user_db)
        await redis_client.delete(code_key, data_key, cooldown_key)

        bind_user_context(user_id)
        logger.info("User %s verified and created successfully", normalized_email)
        return user_id

    async def resend_register_code(
        self, email: str, background_tasks: BackgroundTasks
    ) -> None:
        """Resend registration code if cooldown timer has elapsed"""
        normalized_email = email.strip().lower()
        cooldown_key = f"register:cooldown:{normalized_email}"
        cooldown_exists = await redis_client.get(cooldown_key)
        if cooldown_exists:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another code.",
            )

        data_key = f"register:data:{normalized_email}"
        data_exists = await redis_client.exists(data_key)
        if not data_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration session expired. Please register again.",
            )

        code = "".join(secrets.choice("0123456789") for _ in range(6))
        code_hash = hash_token(code)
        pending_code = {
            "code_hash": code_hash,
            "attempts": 0,
        }

        ttl_seconds = EMAIL_VERIFICATION_EXPIRE_MINUTES * 60
        code_key = f"register:code:{normalized_email}"
        await redis_client.set(code_key, json.dumps(pending_code), ex=ttl_seconds)
        await redis_client.set(cooldown_key, "1", ex=EMAIL_VERIFICATION_RESEND_SECONDS)

        background_tasks.add_task(
            self.email_service.send_verification_email,
            normalized_email,
            code,
            "register",
        )
        logger.info("Resent registration verification code to %s", normalized_email)

    def login(self, data: LoginRequest) -> Tuple[UserResponse, str, str]:
        """Authenticate user credentials and generate access/refresh tokens"""
        user_db = self.user_repo.get_by_email(data.email)
        if (
            not user_db
            or user_db.password is None
            or not verify_password(data.password, user_db.password)
        ):
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
            created_at=user_db.created_at,
        )

        return response_user, access_token, raw_refresh_token

    async def google_login(self, credential: str) -> Tuple[UserResponse, str, str]:
        """Authenticate user via Google OIDC credential ID token and return access/refresh tokens"""
        try:
            payload = id_token.verify_oauth2_token(
                credential, google_requests.Request(), GOOGLE_CLIENT_ID
            )
        except Exception as e:
            logger.warning("Failed Google ID token verification: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google credential: {e}",
            ) from e

        if not payload.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email is not verified",
            )

        google_sub = payload.get("sub")
        email = payload.get("email", "").strip().lower()
        given_name = payload.get("given_name", "")
        family_name = payload.get("family_name", "")

        if not google_sub or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Google profile data",
            )

        # 1. Lookup by google_id (Google sub)
        user_db = self.user_repo.get_by_google_id(google_sub)

        # 2. Lookup by email if not matched by google_id
        if not user_db:
            user_db = self.user_repo.get_by_email(email)
            if user_db:
                # Link existing user account
                verified_at = user_db.email_verified_at or datetime.now(timezone.utc)
                self.user_repo.link_google_account(
                    user_db.id,
                    google_sub,
                    email_verified_at=verified_at,
                )
                user_db.google_id = google_sub
                if not user_db.email_verified_at:
                    user_db.email_verified_at = verified_at
                # Clean up any pending Redis verification keys
                code_key = f"register:code:{email}"
                data_key = f"register:data:{email}"
                cooldown_key = f"register:cooldown:{email}"
                await redis_client.delete(code_key, data_key, cooldown_key)

        # 3. Create new user if no match found
        if not user_db:
            user_id = str(uuid.uuid4())
            user_db = UserInDB(
                id=user_id,
                email=email,
                password=None,
                first_name=given_name if given_name else email.split("@")[0],
                last_name=family_name,
                is_active=True,
                barangay_city="",
                google_id=google_sub,
                email_verified_at=datetime.now(timezone.utc),
            )
            self.user_repo.create_user(user_db)

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
        logger.info("User %s authenticated via Google successfully", email)

        response_user = UserResponse(
            id=user_id,
            email=user_db.email,
            first_name=user_db.first_name,
            last_name=user_db.last_name,
            barangay_city=user_db.barangay_city,
            created_at=user_db.created_at,
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
