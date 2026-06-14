"""A2A URL validation with private IP blocking (Phase 8).

Validates A2A endpoint URLs for security:
- Only http/https schemes allowed
- Private IP ranges blocked by default (configurable)
- IPv4 and IPv6 support
- **DNS-resolution SSRF defence (P3.1):** when the URL hostname is a
  domain name, it is resolved to all A/AAAA records and each IP is
  checked against the private-range blocklist. This prevents attackers
  from registering ``evil.example.com`` → ``127.0.0.1`` to bypass
  string-based URL checks.

Defence-in-depth notes:
- Pinning the resolved IP into the URL is intentionally NOT done here.
  Instead we *reject* the URL if any resolved address is private. The
  caller can choose to bypass private-IP checks via
  ``allow_private_ips=True`` for explicit development setups.
- DNS responses can change between resolve-time and connect-time
  (DNS rebinding). Callers should perform the HTTP call to the
  *same* hostname and the underlying client (httpx) should be
  configured to refuse connections to private IPs when the policy
  is in effect. The validator here closes the easy bypass.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

from backend.a2a.exceptions import A2AValidationError

logger = logging.getLogger(__name__)

_PRIVATE_PREFIXES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "0.0.0.0/8",
    "169.254.0.0/16",  # link-local
    "100.64.0.0/10",  # CGNAT
    "::1/128",
    "fc00::/7",
    "fe80::/10",
    "::ffff:0:0/96",  # IPv4-mapped IPv6 (catch-all for ::ffff:127.0.0.1 etc.)
]

_private_networks = [ipaddress.ip_network(p) for p in _PRIVATE_PREFIXES]


def _is_private_ip(addr_str: str) -> bool:
    """Return True if ``addr_str`` falls in any blocked private range."""
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        return True  # Be conservative: unparseable → treat as blocked
    # IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) → check the underlying v4
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return any(addr in net for net in _private_networks)


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

    if allow_private_ips:
        return url

    # --- Private-IP / DNS-rebinding defence --------------------------------
    # Step 1: literal IP in the hostname?
    try:
        ipaddress.ip_address(hostname)
        if _is_private_ip(hostname):
            raise A2AValidationError(
                f"Private IP address '{hostname}' is blocked. Set DANWA_A2A_ALLOW_PRIVATE_IPS=true to allow.",
                endpoint=url,
            )
        # Public IP literal — accept.
        return url
    except ValueError:
        pass  # Not an IP — must be a hostname; resolve it.

    # Step 2: hostname → resolve all A/AAAA records and check each.
    try:
        addrinfo = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise A2AValidationError(
            f"DNS resolution failed for '{hostname}': {exc}",
            endpoint=url,
        )

    resolved: list[str] = []
    for family, _type, _proto, _canon, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if ip_str in resolved:
            continue
        resolved.append(ip_str)
        if _is_private_ip(ip_str):
            logger.warning(
                "A2A URL '%s' resolves to private IP %s — blocking",
                url,
                ip_str,
            )
            raise A2AValidationError(
                f"Hostname '{hostname}' resolves to a private IP ({ip_str}). Set DANWA_A2A_ALLOW_PRIVATE_IPS=true to allow.",
                endpoint=url,
            )

    if not resolved:
        # getaddrinfo returned nothing usable — treat as failure.
        raise A2AValidationError(
            f"DNS resolution for '{hostname}' returned no addresses",
            endpoint=url,
        )

    return url
