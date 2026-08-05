from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FavoritePlaceCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class FavoritePlaceUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class FavoritePlaceResponse(BaseModel):
    id: UUID
    user_id: UUID
    label: str
    address: str
    latitude: float
    longitude: float
    created_at: datetime
