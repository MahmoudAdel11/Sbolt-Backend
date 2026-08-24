import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class RatingModel(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        # Enforces "one rating per ride" at the DB level, not just in application
        # logic - mirrors uq_favorite_places_user_id_label's role for its own
        # uniqueness rule.
        UniqueConstraint("ride_id", name="uq_ratings_ride_id"),
        CheckConstraint("score >= 1 AND score <= 5", name="ck_ratings_score_range"),
        Index("ix_ratings_driver_id", "driver_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ride_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rides.id"), nullable=False
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Denormalized directly onto the row (not derived via a ride_id join) - it's
    # what the average-rating aggregate query filters on, and it can never
    # actually diverge from rides.driver_id since both are set once, off the
    # same ride.
    driver_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
