import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class DriverProfileModel(Base):
    __tablename__ = "driver_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_driver_profiles_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_online: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Nullable, no default - a freshly-registered driver having none of these
    # filled in yet is a normal, expected state, not an error.
    vehicle_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    license_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
