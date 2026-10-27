"""Telephony service containing business logic and compliance checks."""

import uuid
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from backend.app.modules.providers.telephony import TwilioSIPProvider
from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.schemas import (
    PhoneNumberAssign,
    PhoneNumberCreate,
    PhoneNumberResponse,
)


def is_within_calling_window(
    now: datetime | None = None, tz_name: str = "America/New_York"
) -> bool:
    """Enforce TCPA calling window: strictly 8:00 AM to 8:00 PM local recipient time."""
    current = now or datetime.now(UTC)
    try:
        local_time = current.astimezone(ZoneInfo(tz_name))
    except Exception:
        local_time = current.astimezone(ZoneInfo("UTC"))

    start = time(8, 0, 0)
    end = time(20, 0, 0)
    return start <= local_time.time() <= end


class TelephonyService:
    """Business logic for telephony numbers, carrier provisioning, and agent routing."""

    def __init__(
        self,
        repository: TelephonyRepository | None = None,
        provider: TwilioSIPProvider | None = None,
    ) -> None:
        self.repository = repository if repository is not None else TelephonyRepository()
        self.provider = provider or TwilioSIPProvider()

    def normalize_number(self, raw_number: str) -> str:
        """Normalize raw string to verified E.164 format."""
        return self.provider.format_e164(raw_number)

    async def list_phone_numbers(
        self, organization_id: uuid.UUID | str
    ) -> list[PhoneNumberResponse]:
        """List all phone numbers configured for an organization."""
        numbers = await self.repository.list_by_org(organization_id)
        return [PhoneNumberResponse.model_validate(n) for n in numbers]

    async def get_phone_number(
        self, organization_id: uuid.UUID | str, phone_number_id: uuid.UUID | str
    ) -> PhoneNumberResponse | None:
        """Fetch details for a specific phone number."""
        number = await self.repository.get_by_id(organization_id, phone_number_id)
        if not number:
            return None
        return PhoneNumberResponse.model_validate(number)

    async def get_by_e164(self, e164: str) -> PhoneNumberResponse | None:
        """Look up phone number routing entity by normalized E.164 string."""
        try:
            normalized = self.normalize_number(e164)
        except Exception:
            normalized = e164
        number = await self.repository.get_by_e164(normalized)
        if not number:
            return None
        return PhoneNumberResponse.model_validate(number)

    async def create_phone_number(
        self, organization_id: uuid.UUID | str, payload: PhoneNumberCreate
    ) -> PhoneNumberResponse:
        """Register a new telephone number for an organization."""
        normalized = self.normalize_number(payload.e164)
        trunk_ref = payload.trunk_ref
        if not trunk_ref:
            binding = self.provider.create_sip_trunk_binding(
                normalized, livekit_sip_uri="sip:inbound.livekit.cloud;transport=tls"
            )
            trunk_ref = binding.get("trunk_ref")

        number = await self.repository.create_phone_number(
            organization_id=organization_id,
            e164=normalized,
            carrier=payload.carrier,
            agent_id=payload.agent_id,
            trunk_ref=trunk_ref,
        )
        return PhoneNumberResponse.model_validate(number)

    async def assign_agent(
        self,
        organization_id: uuid.UUID | str,
        phone_number_id: uuid.UUID | str,
        agent_id: uuid.UUID | str | None = None,
        data: PhoneNumberAssign | None = None,
    ) -> PhoneNumberResponse | None:
        """Assign or unassign an agent to a phone number."""
        target_agent_id = data.agent_id if data is not None else agent_id
        updated = await self.repository.assign_agent(
            organization_id, phone_number_id, target_agent_id
        )
        if not updated:
            return None
        return PhoneNumberResponse.model_validate(updated)

    async def delete_phone_number(
        self, organization_id: uuid.UUID | str, phone_number_id: uuid.UUID | str
    ) -> bool:
        """Remove a phone number registration."""
        return await self.repository.delete_phone_number(organization_id, phone_number_id)
