"""Telephony provider protocol and Twilio SIP implementation."""

import re
from typing import Protocol

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_e164_format(number: str) -> bool:
    """Validate that a string conforms to ITU-T E.164 phone number formatting."""
    return bool(E164_REGEX.match(number.strip()))


class TelephonyProvider(Protocol):
    """Protocol defining telephony carrier and SIP trunk operations."""

    def format_e164(self, raw: str) -> str:
        """Normalize raw user string into standard E.164."""
        ...

    def validate_e164(self, number: str) -> bool:
        """Return True if number is a valid E.164 string."""
        ...

    def create_sip_trunk_binding(self, e164: str, livekit_sip_uri: str) -> dict[str, str]:
        """Configure SIP forwarding on the carrier towards LiveKit SIP ingress."""
        ...


class TwilioSIPProvider:
    """Twilio programmable SIP trunking provider implementation."""

    def __init__(self, account_sid: str = "", auth_token: str = "") -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token

    def validate_e164(self, number: str) -> bool:
        """Validate E.164 formatting."""
        return validate_e164_format(number)

    def format_e164(self, raw: str) -> str:
        """Strip spaces, hyphens, parentheses and enforce leading plus."""
        cleaned = re.sub(r"[\s\-\(\)]", "", raw)
        if not self.validate_e164(cleaned):
            raise ValueError(f"Invalid E.164 phone number format: '{raw}'")
        return cleaned

    def create_sip_trunk_binding(self, e164: str, livekit_sip_uri: str) -> dict[str, str]:
        """Generate mock/active carrier trunk reference binding for inbound SIP calls."""
        normalized = self.format_e164(e164)
        trunk_ref = f"tk_tw_{normalized.replace('+', '')}"
        return {
            "e164": normalized,
            "carrier": "twilio",
            "trunk_ref": trunk_ref,
            "target_sip_uri": livekit_sip_uri,
        }
