from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    RIDER = "rider"
    DRIVER = "driver"


@dataclass
class User:
    email: str
    hashed_password: str
    full_name: str
    is_active: bool
    role: UserRole = UserRole.RIDER
    # Only meaningful for drivers; riders simply never toggle it. Defaults False so a
    # newly-registered driver isn't surfaced in availability results until they opt in.
    is_online: bool = False
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    phone_number: str | None = None
