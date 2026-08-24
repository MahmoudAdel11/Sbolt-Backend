from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RatingCreateRequest(BaseModel):
    score: int = Field(ge=1, le=5)


class RatingResponse(BaseModel):
    id: UUID
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID
    score: int
    created_at: datetime
