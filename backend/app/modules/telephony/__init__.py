"""Telephony module public interface."""

from backend.app.modules.telephony.models import PhoneNumber
from backend.app.modules.telephony.router import router
from backend.app.modules.telephony.schemas import (
    PhoneNumberAssign,
    PhoneNumberResponse,
)
from backend.app.modules.telephony.service import TelephonyService

__all__ = [
    "PhoneNumber",
    "PhoneNumberAssign",
    "PhoneNumberResponse",
    "TelephonyService",
    "router",
]
