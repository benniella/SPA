"""GeoIP lookup behind a provider abstraction.

The application asks a provider to resolve a country for an address; no business
logic calls a vendor SDK directly, and provider credentials remain deployment
secrets. The only implementation shipped here is a deterministic test fake —
there is no pretend live GeoIP until a real provider is configured.
"""

from __future__ import annotations

import ipaddress
from typing import Protocol, runtime_checkable


@runtime_checkable
class GeoIPProvider(Protocol):
    """Resolves an address to an ISO 3166-1 alpha-2 country code."""

    @property
    def available(self) -> bool:
        """Whether the provider can actually answer lookups."""

    def lookup(self, address: str) -> str | None:
        """The country for an address, or None when it cannot be resolved."""


class UnavailableGeoIPProvider:
    """The default provider before any integration is configured.

    Reports itself unavailable and resolves nothing. A caller must treat a
    'None' as 'unknown', never as 'allowed everywhere', so country enforcement
    cannot accidentally pass because the provider was absent.
    """

    @property
    def available(self) -> bool:
        return False

    def lookup(self, address: str) -> str | None:
        return None


class StaticGeoIPProvider:
    """A deterministic provider for tests and local development.

    Maps address networks to country codes explicitly. It is not a GeoIP
    database and does not claim to be: it exists so the policy layer can be
    exercised without a vendor.
    """

    def __init__(self, mappings: dict[str, str], *, default: str | None = None) -> None:
        self._networks: list[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, str]] = []
        for network, country in mappings.items():
            code = country.strip().upper()
            if len(code) != 2 or not code.isalpha():
                raise ValueError(f"Invalid country code in test provider: {country!r}.")
            self._networks.append((ipaddress.ip_network(network, strict=False), code))
        self._default = default.strip().upper() if default else None

    @property
    def available(self) -> bool:
        return True

    def lookup(self, address: str) -> str | None:
        try:
            candidate = ipaddress.ip_address(address.strip())
        except ValueError:
            return None
        for network, country in self._networks:
            if candidate.version == network.version and candidate in network:
                return country
        return self._default


def resolve_country(provider: GeoIPProvider, address: str | None) -> str | None:
    """Resolve a country, treating an unavailable provider as 'unknown'."""
    if address is None or not provider.available:
        return None
    return provider.lookup(address)
