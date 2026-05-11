from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import load_settings
from .db import get_db
from .models import User


security = HTTPBearer(auto_error=False)
CAPTCHA_TTL_SECONDS = 300


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_password(password: str) -> tuple[bytes, bytes]:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return digest, salt


def _sign_text(text: str) -> bytes:
    settings = load_settings()
    return hmac.new(
        settings.auth_secret.encode("utf-8"),
        text.encode("ascii"),
        hashlib.sha256,
    ).digest()


def create_captcha() -> dict[str, str | int]:
    left = secrets.randbelow(8) + 1
    right = secrets.randbelow(8) + 1
    if secrets.randbelow(2) == 0:
        challenge = f"{left} + {right} = ?"
        answer = str(left + right)
    else:
        larger = max(left, right)
        smaller = min(left, right)
        challenge = f"{larger} - {smaller} = ?"
        answer = str(larger - smaller)

    payload = {
        "answer_hash": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "exp": int(time.time()) + CAPTCHA_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(8),
    }
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    token = f"{payload_b64}.{_b64encode(_sign_text(payload_b64))}"
    return {
        "challenge": challenge,
        "token": token,
        "expires_in": CAPTCHA_TTL_SECONDS,
    }


def verify_captcha(answer: str, token: str) -> bool:
    normalized_answer = answer.strip()
    if not normalized_answer or not token.strip():
        return False

    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
    except ValueError:
        return False

    expected = _sign_text(payload_b64)
    try:
        signature = _b64decode(signature_b64)
    except Exception:
        return False
    if not hmac.compare_digest(expected, signature):
        return False

    try:
        payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return False

    if int(payload.get("exp", 0)) < int(time.time()):
        return False

    answer_hash = hashlib.sha256(normalized_answer.encode("utf-8")).hexdigest()
    return hmac.compare_digest(answer_hash, str(payload.get("answer_hash", "")))


def verify_password(password: str, expected_hash: bytes, salt: bytes) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(digest, expected_hash)


def issue_token(user_id: int) -> str:
    settings = load_settings()
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + settings.auth_exp_hours * 3600,
    }
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_b64}.{_b64encode(signature)}"


def decode_token(token: str) -> dict:
    settings = load_settings()
    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="登录令牌格式无效。") from exc

    expected = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    signature = _b64decode(signature_b64)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="登录令牌签名无效。")

    payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="登录令牌已过期。")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="需要先登录。")
    payload = decode_token(credentials.credentials)
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在或已失效。")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        return None
    user = db.get(User, int(payload["sub"]))
    return user
