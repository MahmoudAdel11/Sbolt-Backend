import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.ride.entities import RideStatus
from app.infrastructure.db.base import Base


class RideModel(Base):
    __tablename__ = "rides"
    __table_args__ = (
        Index(
            "uq_rides_one_active_per_rider",
            "rider_id",
            unique=True,
            postgresql_where="status NOT IN ('completed', 'cancelled')",
        ),
        Index("ix_rides_rider_id_status", "rider_id", "status"),
        Index("ix_rides_driver_id", "driver_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[RideStatus] = mapped_column(
        Enum(
            RideStatus,
            name="ride_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=RideStatus.REQUESTED,
        server_default=RideStatus.REQUESTED.value,
    )
    pickup_latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    pickup_longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    dropoff_latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    dropoff_longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
