from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class FavoritePlace:
    user_id: UUID
    label: str
    address: str
    latitude: float
    longitude: float
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    created_at: datetime | None = None
