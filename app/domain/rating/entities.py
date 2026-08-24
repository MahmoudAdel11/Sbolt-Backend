from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Rating:
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID
    score: int
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    created_at: datetime | None = None
