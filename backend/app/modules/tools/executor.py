"""Outbound tool execution engine with SSRF guard and size limits."""

import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_RESPONSE_BYTES = 64 * 1024  # 64 KB limit
DEFAULT_TIMEOUT_SECONDS = 8.0

BLOCKED_NETWORKS = [
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:0:0/96"),
]


def _is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[bool, str | None]:
    """Check if an IP address belongs to loopback, private, or reserved ranges."""
    if ip.is_loopback:
        return True, f"Loopback IP {ip} is blocked"
    if ip.is_private:
        return True, f"Private IP {ip} is blocked"
    if ip.is_link_local:
        return True, f"Link-local IP {ip} is blocked"
    if ip.is_multicast:
        return True, f"Multicast IP {ip} is blocked"
    if ip.is_reserved:
        return True, f"Reserved IP {ip} is blocked"
    if ip.is_unspecified:
        return True, f"Unspecified IP {ip} is blocked"

    # Check IPv4-mapped IPv6
    ipv4_mapped = getattr(ip, "ipv4_mapped", None)
    if ipv4_mapped is not None:
        blocked, reason = _is_ip_blocked(ipv4_mapped)
        if blocked:
            return True, f"IPv4-mapped IP {ip} blocked: {reason}"

    # Explicit check against CIDR list
    for net in BLOCKED_NETWORKS:
        if ip in net:
            return True, f"IP {ip} resides in blocked network {net}"
        if ipv4_mapped is not None and ipv4_mapped in net:
            return True, f"IPv4-mapped IP {ip} resides in blocked network {net}"

    return False, None


def _parse_custom_ipv4(hostname: str) -> ipaddress.IPv4Address | None:
    """Parse custom IPv4 notations (hex octets, octal integers, decimal integers)."""
    if ":" in hostname:
        return None
    parts = hostname.split(".")
    if not (1 <= len(parts) <= 4):
        return None
    values: list[int] = []
    for p in parts:
        if not p:
            return None
        try:
            if p.lower().startswith("0x"):
                values.append(int(p, 16))
            elif p.startswith("0") and len(p) > 1 and p.isdigit():
                values.append(int(p, 8))
            elif p.isdigit():
                values.append(int(p, 10))
            else:
                return None
        except ValueError:
            return None

    if len(values) == 4:
        if any(v > 255 for v in values):
            return None
        int_val = (values[0] << 24) | (values[1] << 16) | (values[2] << 8) | values[3]
    elif len(values) == 3:
        if values[0] > 255 or values[1] > 255 or values[2] > 65535:
            return None
        int_val = (values[0] << 24) | (values[1] << 16) | values[2]
    elif len(values) == 2:
        if values[0] > 255 or values[1] > 16777215:
            return None
        int_val = (values[0] << 24) | values[1]
    elif len(values) == 1:
        if values[0] > 4294967295:
            return None
        int_val = values[0]
    else:
        return None

    return ipaddress.IPv4Address(int_val)


def is_safe_url(url: str) -> tuple[bool, str | None]:
    """Inspect URL hostname and verify resolved IP addresses are public."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported URL scheme: '{parsed.scheme}'. Only http and https allowed."

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in tool URL"

    # Reject IPv4 address literals with leading zeros (ambiguous octal notation)
    if ":" not in hostname:
        parts = hostname.split(".")
        if 1 <= len(parts) <= 4:
            is_numeric_ip = all(
                p.isdigit() or (p.lower().startswith("0x") and len(p) > 2) for p in parts if p
            )
            if is_numeric_ip and any(
                p.isdigit() and len(p) > 1 and p.startswith("0") for p in parts
            ):
                return (
                    False,
                    f"SSRF blocked: Hostname '{hostname}' contains ambiguous "
                    "octal IP octets with leading zeros",
                )

    # Evaluate custom IPv4 representations (hex, octal, integer notation)
    custom_ip = _parse_custom_ipv4(hostname)
    if custom_ip is not None:
        blocked, reason = _is_ip_blocked(custom_ip)
        if blocked:
            return False, f"SSRF blocked: {reason}"
        return True, None

    try:
        # Check direct IP literal (IPv4 or IPv6)
        ip_obj = ipaddress.ip_address(hostname)
        blocked, reason = _is_ip_blocked(ip_obj)
        if blocked:
            return False, f"SSRF blocked: {reason}"
        return True, None
    except ValueError:
        pass

    try:
        # Resolve hostname DNS and verify all addresses
        addr_info = socket.getaddrinfo(hostname, None)
        if not addr_info:
            return False, f"DNS resolution returned no addresses for '{hostname}'"
        for entry in addr_info:
            ip_str = entry[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            blocked, reason = _is_ip_blocked(ip_obj)
            if blocked:
                msg = (
                    f"SSRF blocked: Hostname '{hostname}' resolved to blocked IP {ip_str} "
                    f"({reason})"
                )
                return False, msg
        return True, None
    except Exception as exc:
        return False, f"DNS resolution failed for '{hostname}': {exc}"


async def execute_http_tool(
    config: dict[str, Any],
    arguments: dict[str, Any],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Execute an outbound HTTP webhook tool safely within timeout and response bounds."""
    url = str(config.get("url", ""))
    if not url:
        return {
            "status": "failed",
            "result": None,
            "error": "Tool configuration missing required 'url'",
        }

    safe, reason = is_safe_url(url)
    if not safe:
        return {
            "status": "failed",
            "result": None,
            "error": reason or "SSRF verification failure",
        }

    method = str(config.get("method", "POST")).upper()
    headers = config.get("headers")
    headers_dict = headers if isinstance(headers, dict) else {}

    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,  # Disallow redirects to prevent SSRF bypass
        ) as client:
            if method in ("GET", "DELETE"):
                response = await client.request(
                    method=method,
                    url=url,
                    params=arguments,
                    headers=headers_dict,
                )
            else:
                response = await client.request(
                    method=method,
                    url=url,
                    json=arguments,
                    headers=headers_dict,
                )

            content_bytes = response.content
            is_truncated = len(content_bytes) > MAX_RESPONSE_BYTES
            if is_truncated:
                content_bytes = content_bytes[:MAX_RESPONSE_BYTES]

            try:
                if is_truncated:
                    data = json.loads(content_bytes.decode("utf-8", errors="replace"))
                else:
                    data = response.json()
            except Exception:
                data = {
                    "raw_text": content_bytes.decode("utf-8", errors="replace"),
                    "truncated": is_truncated,
                }

            return {
                "status": "success" if response.is_success else "failed",
                "status_code": response.status_code,
                "result": data,
                "error": None if response.is_success else f"HTTP error {response.status_code}",
            }
    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "result": None,
            "error": f"Tool execution timed out after {timeout_seconds} seconds",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "result": None,
            "error": f"Tool execution network error: {exc}",
        }


def validate_json_schema(
    schema: dict[str, Any] | None,
    data: Any,
    path: str = "root",
) -> tuple[bool, str | None]:
    """Validate data against a JSON schema using standard Python.

    Validates type, required fields, properties, array items, enums,
    and additionalProperties.
    """
    if not schema or not isinstance(schema, dict):
        return True, None

    expected_type = schema.get("type")
    if expected_type:
        type_valid = False
        allowed_types: list[str] = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )
        for t in allowed_types:
            if t == "string" and isinstance(data, str):
                type_valid = True
                break
            elif t == "integer" and isinstance(data, int) and not isinstance(data, bool):
                type_valid = True
                break
            elif t == "number" and isinstance(data, (int, float)) and not isinstance(data, bool):
                type_valid = True
                break
            elif t == "boolean" and isinstance(data, bool):
                type_valid = True
                break
            elif t == "array" and isinstance(data, list):
                type_valid = True
                break
            elif t == "object" and isinstance(data, dict):
                type_valid = True
                break
            elif t == "null" and data is None:
                type_valid = True
                break

        if not type_valid:
            actual_type = "null" if data is None else type(data).__name__
            return False, f"Expected type '{expected_type}' at '{path}', got '{actual_type}'"

    if isinstance(data, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for field in required:
                if field not in data:
                    prop_path = f"{path}.{field}" if path != "root" else field
                    return False, f"Missing required property: '{prop_path}'"

        additional_props = schema.get("additionalProperties")
        properties = schema.get("properties", {})
        if additional_props is False:
            for key in data:
                if key not in properties:
                    prop_path = f"{path}.{key}" if path != "root" else key
                    return False, f"Unexpected additional property '{prop_path}'"

        if isinstance(properties, dict):
            for key, val in data.items():
                if key in properties:
                    prop_path = f"{path}.{key}" if path != "root" else key
                    valid, err = validate_json_schema(properties[key], val, path=prop_path)
                    if not valid:
                        return False, err
                elif isinstance(additional_props, dict):
                    prop_path = f"{path}.{key}" if path != "root" else key
                    valid, err = validate_json_schema(additional_props, val, path=prop_path)
                    if not valid:
                        return False, err

    elif ("properties" in schema or "required" in schema) and not isinstance(data, dict):
        return False, f"Expected object at '{path}', got '{type(data).__name__}'"

    if isinstance(data, list):
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for idx, item in enumerate(data):
                item_path = f"{path}[{idx}]"
                valid, err = validate_json_schema(items_schema, item, path=item_path)
                if not valid:
                    return False, err

    enum_vals = schema.get("enum")
    if isinstance(enum_vals, list) and data not in enum_vals:
        return False, f"Value at '{path}' is not in allowed enum {enum_vals}"

    return True, None
