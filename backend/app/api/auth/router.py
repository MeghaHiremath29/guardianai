"""
Authentication endpoints.
Real implementation: bcrypt password hashing, JWT access + refresh tokens.
No fake/mocked auth — every call touches the database.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("guardianai.auth")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("auth.register user_id=%s role=%s", user.id, user.role)
    log_action(db, AuditAction.USER_REGISTERED, actor_id=user.id, actor_email=user.email,
               entity_type="User", entity_id=user.id, detail=f"Registered as {user.role.value}")
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()

    # Deliberately generic error so we don't leak which part was wrong.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
    )

    if not user or not verify_password(payload.password, user.hashed_password):
        logger.info("auth.login_failed email=%s", payload.email)
        log_action(db, AuditAction.USER_LOGIN_FAILED, actor_email=payload.email,
                   detail="Invalid email or password")
        raise invalid_credentials

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token = create_refresh_token(subject=user.id)

    logger.info("auth.login_success user_id=%s", user.id)
    log_action(db, AuditAction.USER_LOGIN, actor_id=user.id, actor_email=user.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token_data = decode_token(payload.refresh_token)
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if token_data is None or token_data.token_type != "refresh" or token_data.sub is None:
        raise invalid

    user = db.query(User).filter(User.id == token_data.sub).first()
    if not user or not user.is_active:
        raise invalid

    access_token = create_access_token(subject=user.id, role=user.role.value)
    new_refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)
