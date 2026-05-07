from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .contracts import UserOut
from .models import User

CHINA_TZ = ZoneInfo("Asia/Shanghai")
GENERATION_PROGRESS: dict[int, dict[str, object]] = {}


def _china_timestamp() -> str:
    return datetime.now(CHINA_TZ).isoformat(timespec="seconds")


def _username_to_internal_email(username: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    suffix = abs(hash((username, timestamp))) % 100000
    return f"user-{timestamp}-{suffix}@local.invalid"


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.display_name, email=user.email)
