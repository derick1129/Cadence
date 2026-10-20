"""Alias test file for test_agents_cross_tenant.py."""

from backend.tests.test_agents_cross_tenant import (  # noqa: F401
    client,
    test_agent_immutable_version_bumping,
    test_cross_tenant_agent_isolation,
    test_member_role_cannot_modify_agent,
)
