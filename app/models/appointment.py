import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    CANCELLED = "cancelled"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "end_at = start_at + INTERVAL '30 minutes'",
            name="ck_appointments_duration",
        ),
        CheckConstraint(
            "(status = 'booked' AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL "
            "AND cancellation_reason IS NOT NULL)",
            name="ck_appointments_cancel_consistency",
        ),
        Index(
            "uq_appointments_doctor_slot_booked",
            "doctor_id",
            "start_at",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
        Index("ix_appointments_patient_start", "patient_id", "start_at"),
        Index("ix_appointments_doctor_start", "doctor_id", "start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=AppointmentStatus.BOOKED,
        server_default=text("'booked'::appointment_status"),
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")  # noqa: F821
    patient: Mapped["Patient"] = relationship(back_populates="appointments")  # noqa: F821
