from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.ride.entities import RideTier


@dataclass
class DriverProfile:
    user_id: UUID
    is_online: bool = False
    # A driver may not have filled these in yet - unset is a normal state, not an
    # error, so these stay optional rather than defaulting to empty strings.
    vehicle_type: str | None = None
    vehicle_color: str | None = None
    license_plate: str | None = None
    # Reuses RideTier directly (not a parallel enum) - a driver's scooter
    # capability and a ride's tier are the same three-tier scale. NULL means
    # "no restriction set" (all pre-existing drivers predate this field) -
    # see GetAvailableRidesUseCase for how NULL is treated as "sees everything".
    scooter_type: RideTier | None = None
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
