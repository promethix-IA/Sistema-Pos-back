from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: int | None
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    owner_id: int | None = None
    role: str = "owner"
    plan: str = ""
    plan_expires_at: datetime | None = None
    desktop_download: bool = False
    desktop_channel: str = "windows10-11"
    desktop_updates_until: str = ""
