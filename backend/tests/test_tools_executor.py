"""Tests for SSRF guard and outbound tool execution engine."""

import socket
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.app.modules.tools.executor import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    execute_http_tool,
    is_safe_url,
)


@pytest.fixture(autouse=True)
def mock_dns_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture resolving example.com domains to public IP in tests."""
    original_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any) -> Any:
        if host in ("api.example.com", "example.com"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def test_ssrf_guard_blocks_private_and_loopback_ips() -> None:
    """Verify SSRF guard blocks internal, loopback, cloud metadata, and link-local ranges."""
    blocked_urls = [
        "http://localhost:8000/internal/data",
        "http://127.0.0.1:5432",
        "http://127.0.0.5:80",
        "http://10.0.0.1/admin",
        "http://172.16.0.5/api",
        "http://172.31.255.255/internal",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data",  # AWS metadata
        "http://[::1]/secret",
        "http://[fc00::1]/db",
        "http://[fe80::1]/link",
        "http://100.64.0.1/carrier-nat",
        "http://192.0.2.1/test-net",
        "http://198.51.100.1/test-net-2",
        "http://203.0.113.1/test-net-3",
        "http://224.0.0.1/multicast",
        "http://240.0.0.1/reserved",
    ]
    for url in blocked_urls:
        safe, reason = is_safe_url(url)
        assert safe is False, f"Expected {url} to be blocked by SSRF guard"
        assert reason is not None


def test_ssrf_guard_blocks_ipv4_mapped_ipv6() -> None:
    """Verify IPv4-mapped IPv6 representations of blocked addresses are caught."""
    mapped_urls = [
        "http://[::ffff:127.0.0.1]/secret",
        "http://[::ffff:169.254.169.254]/metadata",
        "http://[::ffff:10.0.0.1]/admin",
    ]
    for url in mapped_urls:
        safe, reason = is_safe_url(url)
        assert safe is False, f"Expected {url} to be blocked"
        assert reason is not None


def test_ssrf_guard_blocks_unsupported_schemes() -> None:
    """Verify non-HTTP schemes are rejected."""
    bad_schemes = [
        "ftp://example.com/file.txt",
        "file:///etc/passwd",
        "gopher://127.0.0.1:70",
        "javascript:alert(1)",
    ]
    for url in bad_schemes:
        safe, reason = is_safe_url(url)
        assert safe is False
        assert reason is not None
        assert "Unsupported URL scheme" in reason


def test_ssrf_guard_allows_public_https_domains() -> None:
    """Verify SSRF guard allows legitimate public webhooks."""
    safe, reason = is_safe_url("https://api.github.com/events")
    assert safe is True
    assert reason is None

    safe_ip, _ = is_safe_url("http://8.8.8.8/test")
    assert safe_ip is True


def test_ssrf_guard_dns_failure_handling() -> None:
    """Verify non-resolvable hostnames are safely rejected."""
    safe, reason = is_safe_url("https://non-existent-domain-xyz-987654321.com/test")
    assert safe is False
    assert reason is not None
    assert "DNS resolution failed" in reason


@pytest.mark.asyncio
async def test_execute_http_tool_ssrf_rejection() -> None:
    """Verify tool execution fails safely when target URL is private."""
    config = {"url": "http://127.0.0.1:8000/keys", "method": "GET"}
    result = await execute_http_tool(config=config, arguments={})
    assert result["status"] == "failed"
    assert "SSRF" in result["error"]
    assert result["result"] is None


@pytest.mark.asyncio
async def test_execute_http_tool_success_post() -> None:
    """Verify outbound POST execution and JSON parsing using mocked HTTP transport."""
    config = {
        "url": "https://api.example.com/webhook",
        "method": "POST",
        "headers": {"X-Custom-Auth": "secret-token"},
    }
    arguments = {"customer_id": "cust-123", "action": "verify"}

    mock_response = httpx.Response(
        status_code=200,
        json={"confirmed": True, "token": "tok-999"},
        request=httpx.Request("POST", "https://api.example.com/webhook"),
    )

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await execute_http_tool(config=config, arguments=arguments)

        assert result["status"] == "success"
        assert result["status_code"] == 200
        assert result["result"]["confirmed"] is True
        assert result["error"] is None
        mock_req.assert_called_once_with(
            method="POST",
            url="https://api.example.com/webhook",
            json=arguments,
            headers={"X-Custom-Auth": "secret-token"},
        )


@pytest.mark.asyncio
async def test_execute_http_tool_get_with_params() -> None:
    """Verify GET requests pass arguments as query parameters."""
    config = {"url": "https://api.example.com/query", "method": "GET"}
    arguments = {"search": "test"}

    mock_response = httpx.Response(
        status_code=200,
        json={"items": []},
        request=httpx.Request("GET", "https://api.example.com/query"),
    )

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await execute_http_tool(config=config, arguments=arguments)

        assert result["status"] == "success"
        mock_req.assert_called_once_with(
            method="GET",
            url="https://api.example.com/query",
            params=arguments,
            headers={},
        )


@pytest.mark.asyncio
async def test_execute_http_tool_timeout() -> None:
    """Verify timeout triggers clean status='timeout' response."""
    config = {"url": "https://api.example.com/slow", "method": "POST"}

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = httpx.TimeoutException("Connection timed out")
        result = await execute_http_tool(config=config, arguments={}, timeout_seconds=5.0)

        assert result["status"] == "timeout"
        assert "timed out after 5.0 seconds" in result["error"]
        assert result["result"] is None


@pytest.mark.asyncio
async def test_execute_http_tool_body_truncation() -> None:
    """Verify responses exceeding 64 KB are safely truncated."""
    config = {"url": "https://api.example.com/large", "method": "GET"}
    large_payload = "A" * (MAX_RESPONSE_BYTES + 1024)

    mock_response = httpx.Response(
        status_code=200,
        text=large_payload,
        request=httpx.Request("GET", "https://api.example.com/large"),
    )

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await execute_http_tool(config=config, arguments={})

        assert result["status"] == "success"
        raw_text = result["result"]["raw_text"]
        assert len(raw_text.encode("utf-8")) == MAX_RESPONSE_BYTES
        assert result["result"]["truncated"] is True


@pytest.mark.asyncio
async def test_execute_http_tool_redirect_prohibition() -> None:
    """Verify client is instantiated with follow_redirects=False."""
    config = {"url": "https://api.example.com/redirect", "method": "GET"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.request.return_value = httpx.Response(
            status_code=302,
            headers={"Location": "http://127.0.0.1/admin"},
            request=httpx.Request("GET", "https://api.example.com/redirect"),
        )
        mock_client_cls.return_value = mock_instance

        result = await execute_http_tool(config=config, arguments={})
        mock_client_cls.assert_called_once_with(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        assert result["status"] == "failed"
        assert result["status_code"] == 302
