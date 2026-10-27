"""Tests for PhoneNumber SQLAlchemy ORM model."""

import uuid

from backend.app.modules.telephony.models import PhoneNumber


def test_phone_number_model_instantiation() -> None:
    """Verify PhoneNumber model fields, organization ownership, and agent routing."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    number = PhoneNumber(
        organization_id=org_id,
        e164="+15551234567",
        carrier="twilio",
        agent_id=agent_id,
        trunk_ref="trunk-tw-test-01",
    )
    assert number.organization_id == org_id
    assert number.e164 == "+15551234567"
    assert number.carrier == "twilio"
    assert number.agent_id == agent_id
    assert number.trunk_ref == "trunk-tw-test-01"
    assert isinstance(number.id, uuid.UUID)


def test_phone_number_optional_routing() -> None:
    """Verify PhoneNumber can exist unassigned without an agent."""
    org_id = uuid.uuid4()
    number = PhoneNumber(
        organization_id=org_id,
        e164="+15559876543",
        carrier="telnyx",
    )
    assert number.organization_id == org_id
    assert number.agent_id is None
    assert number.trunk_ref is None
    assert isinstance(number.id, uuid.UUID)
