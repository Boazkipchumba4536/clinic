import uuid
from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DoctorSchedule(Base):
    """A working-hour window for one weekday, in clinic local time.

    Weekday uses Python/ISO convention: 0 = Monday ... 6 = Sunday.
    Multiple rows per weekday are allowed so a lunch break can be modeled
    as two windows (e.g. 09:00-13:00 and 14:00-17:00).
    """

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_schedule_weekday"),
        CheckConstraint("end_time > start_time", name="ck_schedule_window_order"),
        UniqueConstraint(
            "doctor_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_schedule_window",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    doctor: Mapped["Doctor"] = relationship(back_populates="schedules")  # noqa: F821
