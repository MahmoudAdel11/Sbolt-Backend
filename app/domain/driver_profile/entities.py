from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class DriverProfile:
    user_id: UUID
    is_online: bool = False
    # A driver may not have filled these in yet - unset is a normal state, not an
    # error, so these stay optional rather than defaulting to empty strings.
    vehicle_type: str | None = None
    vehicle_color: str | None = None
    license_plate: str | None = None
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
