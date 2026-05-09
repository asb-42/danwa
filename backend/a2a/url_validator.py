"""A2A URL validation with private IP blocking (Phase 8).

Validates A2A endpoint URLs for security:
- Only http/https schemes allowed
- Private IP ranges blocked by default (configurable)
- IPv4 and IPv6 support
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from backend.a2a.exceptions import A2AValidationError

_PRIVATE_PREFIXES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]

_private_networks = [ipaddress.ip_network(p) for p in _PRIVATE_PREFIXES]


def validate_a2a_url(url: str, allow_private_ips: bool = False) -> str:
    """Validate an A2A endpoint URL.

    Args:
        url: The URL to validate.
        allow_private_ips: If True, allow private/reserved IP ranges.

    Returns:
        The cleaned URL string.

    Raises:
        A2AValidationError: If the URL is invalid or blocked.
    """
    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        raise A2AValidationError(
            f"Invalid URL scheme '{parsed.scheme}': only http/https allowed",
            endpoint=url,
        )

    # Host check
    hostname = parsed.hostname
    if not hostname:
        raise A2AValidationError(
            f"URL has no hostname: {url}",
            endpoint=url,
        )

    # Private IP check
    if not allow_private_ips:
        try:
            addr = ipaddress.ip_address(hostname)
            for network in _private_networks:
                if addr in network:
                    raise A2AValidationError(
                        f"Private IP address '{hostname}' is blocked. "
                        f"Set DANWA_A2A_ALLOW_PRIVATE_IPS=true to allow.",
                        endpoint=url,
                    )
        except ValueError:
            # Not an IP address (e.g. a domain name) — that's fine
            pass

    return url
