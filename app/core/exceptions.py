from fastapi import status


class AppError(Exception):
    """Base error for expected business and lookup failures."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(code, message, status.HTTP_404_NOT_FOUND, details)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(code, message, status.HTTP_409_CONFLICT, details)


class ValidationAppError(AppError):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(code, message, 422, details)


class DoctorNotFound(NotFoundError):
    def __init__(self) -> None:
        super().__init__("DOCTOR_NOT_FOUND", "Doctor not found.")


class PatientNotFound(NotFoundError):
    def __init__(self) -> None:
        super().__init__("PATIENT_NOT_FOUND", "Patient not found.")


class AppointmentNotFound(NotFoundError):
    def __init__(self) -> None:
        super().__init__("APPOINTMENT_NOT_FOUND", "Appointment not found.")


class SlotUnavailable(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "APPOINTMENT_SLOT_UNAVAILABLE",
            "The selected appointment slot is no longer available.",
        )


class AppointmentAlreadyCancelled(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "APPOINTMENT_ALREADY_CANCELLED",
            "This appointment has already been cancelled.",
        )


class AppointmentIsCancelled(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "APPOINTMENT_CANCELLED",
            "A cancelled appointment cannot be rescheduled.",
        )


class AppointmentInPast(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "APPOINTMENT_IN_PAST",
            "Appointments cannot be booked, cancelled, or rescheduled in the past.",
        )


class BookingTooSoon(ValidationAppError):
    def __init__(self, notice_minutes: int) -> None:
        super().__init__(
            "BOOKING_TOO_SOON",
            f"Appointments must be booked at least {notice_minutes} minutes in advance.",
            {"min_booking_notice_minutes": notice_minutes},
        )


class BookingTooFarAhead(ValidationAppError):
    def __init__(self, max_days: int) -> None:
        super().__init__(
            "BOOKING_TOO_FAR_AHEAD",
            f"Appointments cannot be booked more than {max_days} days in advance.",
            {"max_booking_ahead_days": max_days},
        )


class SlotNotAligned(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "SLOT_NOT_ALIGNED",
            "Appointment start time must align to a 30-minute slot "
            "(minutes must be 00 or 30, with seconds at 00).",
        )


class SlotOutsideWorkingHours(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "SLOT_OUTSIDE_WORKING_HOURS",
            "The selected slot is outside the doctor's working hours.",
        )


class DoctorNotWorking(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "DOCTOR_NOT_WORKING",
            "This doctor does not work on the selected date.",
        )


class NaiveDateTimeRejected(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "NAIVE_DATETIME_REJECTED",
            "Datetime values must include a timezone offset "
            "(for example 2026-08-20T09:00:00+03:00).",
        )


class InvalidDate(ValidationAppError):
    def __init__(self) -> None:
        super().__init__("INVALID_DATE", "The supplied date is invalid.")
