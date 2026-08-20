"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    appointment_status = postgresql.ENUM("booked", "cancelled", name="appointment_status")
    appointment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "doctors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("specialty", sa.String(80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_patients_email"),
    )

    op.create_table(
        "doctor_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_schedule_weekday"),
        sa.CheckConstraint("end_time > start_time", name="ck_schedule_window_order"),
        sa.UniqueConstraint("doctor_id", "weekday", "start_time", "end_time", name="uq_schedule_window"),
    )
    op.create_index("ix_doctor_schedules_doctor_id", "doctor_schedules", ["doctor_id"])

    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("booked", "cancelled", name="appointment_status", create_type=False),
            nullable=False,
            server_default=sa.text("'booked'::appointment_status"),
        ),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("end_at = start_at + INTERVAL '30 minutes'", name="ck_appointments_duration"),
        sa.CheckConstraint(
            "(status = 'booked' AND cancelled_at IS NULL AND cancellation_reason IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_appointments_cancel_consistency",
        ),
    )
    op.create_index("ix_appointments_patient_start", "appointments", ["patient_id", "start_at"])
    op.create_index("ix_appointments_doctor_start", "appointments", ["doctor_id", "start_at"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_appointments_doctor_slot_booked
        ON appointments (doctor_id, start_at)
        WHERE status = 'booked'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_appointments_doctor_slot_booked")
    op.drop_index("ix_appointments_doctor_start", table_name="appointments")
    op.drop_index("ix_appointments_patient_start", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_doctor_schedules_doctor_id", table_name="doctor_schedules")
    op.drop_table("doctor_schedules")
    op.drop_table("patients")
    op.drop_table("doctors")
    postgresql.ENUM(name="appointment_status").drop(op.get_bind(), checkfirst=True)
