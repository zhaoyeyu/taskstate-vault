from __future__ import annotations

import ipaddress


def is_loopback_host(host: str) -> bool:
    """Return whether a UI bind host is restricted to the local machine."""

    normalized = host.strip().lower().strip("[]")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False
