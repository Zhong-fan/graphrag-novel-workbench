from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .api_support import _user_out, _username_to_internal_email
from .auth import (
    create_captcha,
    get_current_user,
    hash_password,
    issue_token,
    verify_captcha,
    verify_password,
)
from .config import Settings
from .contracts import (
    AuthResponse,
    BootstrapResponse,
    CaptchaChallenge,
    LoginRequest,
    RegisterRequest,
    UserOut,
    UserProfileOut,
    UserProfileUpdateRequest,
)
from .db import get_db
from .models import User, UserProfile


def register_auth_routes(router: APIRouter, *, settings: Settings) -> None:
    @router.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/bootstrap", response_model=BootstrapResponse)
    def bootstrap() -> BootstrapResponse:
        return BootstrapResponse(
            service_name="ChenFlow Workbench",
            graph_engine="GraphRAG + Neo4j",
            auth_enabled=True,
            writer_model=settings.writer_model,
            utility_model=settings.utility_model,
            embedding_model=settings.embedding_model,
            embedding_provider=settings.embedding_provider_label,
            embedding_base_url=settings.embedding_base_url,
            punctuation_rule="普通对话使用「」，嵌套引号使用『』。",
            query_methods=["local", "global", "drift", "basic"],
        )

    @router.get("/api/auth/captcha", response_model=CaptchaChallenge)
    def auth_captcha() -> CaptchaChallenge:
        return CaptchaChallenge(**create_captcha())

    @router.post("/api/auth/register", response_model=AuthResponse)
    def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
        if not verify_captcha(payload.captcha_answer, payload.captcha_token):
            raise HTTPException(status_code=400, detail="验证码错误或已过期。")

        username = payload.username.strip()
        exists = db.scalar(select(User).where(User.display_name == username))
        if exists is not None:
            raise HTTPException(status_code=409, detail="用户名已存在。")

        password_hash, password_salt = hash_password(payload.password)
        user = User(
            email=_username_to_internal_email(username),
            display_name=username,
            password_hash=password_hash,
            password_salt=password_salt,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return AuthResponse(token=issue_token(user.id), user=_user_out(user))

    @router.post("/api/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
        username = payload.username.strip()
        user = db.scalar(select(User).where(User.display_name == username))
        if user is None or not verify_password(payload.password, user.password_hash, user.password_salt):
            raise HTTPException(status_code=401, detail="用户名或密码错误。")
        return AuthResponse(token=issue_token(user.id), user=_user_out(user))

    @router.get("/api/auth/me", response_model=UserOut)
    def me(current_user: User = Depends(get_current_user)) -> UserOut:
        return _user_out(current_user)

    @router.get("/api/me/profile", response_model=UserProfileOut)
    def my_profile(current_user: User = Depends(get_current_user)) -> UserProfileOut:
        profile = current_user.profile
        if profile is None:
            return UserProfileOut(bio="", email=None, phone=None)
        return UserProfileOut(bio=profile.bio, email=profile.email, phone=profile.phone)

    @router.put("/api/me/profile", response_model=UserProfileOut)
    def update_my_profile(
        payload: UserProfileUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> UserProfileOut:
        profile = current_user.profile
        if profile is None:
            profile = UserProfile(user=current_user, bio="", email=None, phone=None)
            db.add(profile)

        profile.bio = payload.bio.strip()
        profile.email = payload.email.strip() if payload.email and payload.email.strip() else None
        profile.phone = payload.phone.strip() if payload.phone and payload.phone.strip() else None
        db.commit()
        db.refresh(profile)
        return UserProfileOut(bio=profile.bio, email=profile.email, phone=profile.phone)
