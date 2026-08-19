from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class DriverProfile:
    user_id: UUID
    is_online: bool = False
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
