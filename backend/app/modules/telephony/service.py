"""Telephony service."""

from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.schemas import (
    PhoneNumberAssign,
    PhoneNumberResponse,
)


class TelephonyService:
    """Business logic for telephony numbers, provisioning, and agent routing."""

    def __init__(self, repository: TelephonyRepository | None = None) -> None:
        self.repository = repository or TelephonyRepository()

    async def list_phone_numbers(self, organization_id: str) -> list[PhoneNumberResponse]:
        """List all phone numbers configured for an organization."""
        numbers = await self.repository.list_by_org(organization_id)
        return [PhoneNumberResponse.model_validate(n) for n in numbers]

    async def get_phone_number(
        self, organization_id: str, phone_number_id: str
    ) -> PhoneNumberResponse | None:
        """Fetch details for a specific phone number."""
        number = await self.repository.get_by_id(organization_id, phone_number_id)
        if not number:
            return None
        return PhoneNumberResponse.model_validate(number)

    async def assign_agent(
        self,
        organization_id: str,
        phone_number_id: str,
        data: PhoneNumberAssign,
    ) -> PhoneNumberResponse | None:
        """Assign or unassign an agent to a phone number."""
        updated = await self.repository.assign_agent(
            organization_id, phone_number_id, data.agent_id
        )
        if not updated:
            return None
        return PhoneNumberResponse.model_validate(updated)

    async def get_by_e164(self, e164: str) -> PhoneNumberResponse | None:
        """Look up phone number routing by E.164 string."""
        number = await self.repository.get_by_e164(e164)
        if not number:
            return None
        return PhoneNumberResponse.model_validate(number)
