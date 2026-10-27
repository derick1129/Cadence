"""Tests for TelephonyProvider interface and TwilioSIPProvider implementation."""

import pytest

from backend.app.modules.providers.telephony import TwilioSIPProvider, validate_e164_format


def test_validate_e164_format() -> None:
    """Verify strict E.164 regex and international formatting validation."""
    assert validate_e164_format("+15551234567") is True
    assert validate_e164_format("+442071838750") is True
    assert validate_e164_format("+919876543210") is True

    # Invalid patterns
    assert validate_e164_format("15551234567") is False  # missing plus
    assert validate_e164_format("+1(555)123-4567") is False  # special chars
    assert validate_e164_format("+0123456") is False  # invalid country code
    assert validate_e164_format("not-a-number") is False


def test_twilio_sip_provider_formatting() -> None:
    """Verify Twilio provider strips whitespaces and normalizes valid numbers."""
    provider = TwilioSIPProvider(account_sid="AC_test", auth_token="token_test")
    assert provider.format_e164(" +1 555 123 4567 ") == "+15551234567"

    with pytest.raises(ValueError, match="Invalid E.164 phone number format"):
        provider.format_e164("invalid")


def test_twilio_sip_provider_trunk_binding() -> None:
    """Verify Twilio SIP trunk URI binding synthesis for LiveKit SIP inbound routing."""
    provider = TwilioSIPProvider(account_sid="AC_test", auth_token="token_test")
    binding = provider.create_sip_trunk_binding(
        e164="+15551234567",
        livekit_sip_uri="sip:inbound.livekit.cloud;transport=tls",
    )
    assert binding["e164"] == "+15551234567"
    assert binding["carrier"] == "twilio"
    assert "trunk_ref" in binding
    assert binding["target_sip_uri"] == "sip:inbound.livekit.cloud;transport=tls"
