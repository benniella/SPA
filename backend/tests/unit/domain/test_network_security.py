"""Network security domain: country codes, IP blocks, GeoIP resolution."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.domain.security.geoip import (
    StaticGeoIPProvider,
    UnavailableGeoIPProvider,
    resolve_country,
)
from app.domain.security.network import (
    IpBlock,
    IpBlockKind,
    normalise_country_code,
    parse_network,
    temporary_expiry,
)
from app.domain.shared import UserId, new_id, utcnow


class TestCountryCode:
    def test_a_lowercase_code_is_uppercased(self) -> None:
        assert normalise_country_code("gb") == "GB"

    def test_surrounding_whitespace_is_ignored(self) -> None:
        assert normalise_country_code(" ng ") == "NG"

    @pytest.mark.parametrize("value", ["G", "GBR", "1B", "G!", "", "  "])
    def test_a_malformed_code_is_rejected(self, value: str) -> None:
        with pytest.raises(ValueError):
            normalise_country_code(value)


class TestParseNetwork:
    def test_a_bare_ipv4_address_becomes_a_host_network(self) -> None:
        assert parse_network("192.168.0.1") == "192.168.0.1/32"

    def test_a_bare_ipv6_address_becomes_a_host_network(self) -> None:
        assert parse_network("2001:db8::1") == "2001:db8::1/128"

    def test_a_cidr_is_canonicalised(self) -> None:
        assert parse_network("10.0.0.5/24") == "10.0.0.0/24"

    @pytest.mark.parametrize("value", ["not-an-ip", "999.1.1.1", "", "10.0.0.0/99"])
    def test_an_invalid_address_is_rejected(self, value: str) -> None:
        with pytest.raises(ValueError):
            parse_network(value)


class TestIpBlock:
    def _block(self, **overrides: object) -> IpBlock:
        base: dict[str, object] = {
            "network": "203.0.113.0/24",
            "kind": IpBlockKind.PERMANENT,
            "reason": "Abuse",
            "created_by": UserId(new_id()),
        }
        base.update(overrides)
        return IpBlock(**base)  # type: ignore[arg-type]

    def test_a_permanent_block_has_no_expiry(self) -> None:
        block = self._block(expires_at=utcnow() + timedelta(days=1))
        assert block.expires_at is None
        assert not block.is_expired()

    def test_a_temporary_block_requires_an_expiry(self) -> None:
        with pytest.raises(ValueError):
            self._block(kind=IpBlockKind.TEMPORARY)

    def test_a_temporary_block_expires(self) -> None:
        block = self._block(
            kind=IpBlockKind.TEMPORARY,
            expires_at=utcnow() - timedelta(minutes=1),
        )
        assert block.is_expired()
        assert not block.is_active()

    def test_a_block_without_a_reason_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._block(reason="   ")

    def test_a_removed_block_is_no_longer_active(self) -> None:
        block = self._block()
        assert block.is_active()
        block.remove()
        assert block.is_removed
        assert not block.is_active()

    def test_covers_only_addresses_inside_the_network(self) -> None:
        block = self._block()
        assert block.covers("203.0.113.7")
        assert not block.covers("198.51.100.7")

    def test_covers_ignores_a_different_address_family(self) -> None:
        block = self._block()
        assert not block.covers("2001:db8::1")

    def test_covers_rejects_an_invalid_address(self) -> None:
        assert not self._block().covers("not-an-ip")

    def test_temporary_expiry_is_in_the_future(self) -> None:
        assert temporary_expiry(30) > utcnow()


class TestGeoIPProvider:
    def test_the_unavailable_provider_resolves_nothing(self) -> None:
        provider = UnavailableGeoIPProvider()
        assert not provider.available
        assert resolve_country(provider, "203.0.113.7") is None

    def test_a_static_provider_resolves_a_mapped_network(self) -> None:
        provider = StaticGeoIPProvider({"203.0.113.0/24": "ng"})
        assert provider.available
        assert resolve_country(provider, "203.0.113.7") == "NG"

    def test_a_static_provider_falls_back_to_its_default(self) -> None:
        provider = StaticGeoIPProvider({"203.0.113.0/24": "NG"}, default="GB")
        assert resolve_country(provider, "198.51.100.7") == "GB"

    def test_a_static_provider_returns_none_without_a_match_or_default(self) -> None:
        provider = StaticGeoIPProvider({"203.0.113.0/24": "NG"})
        assert resolve_country(provider, "198.51.100.7") is None

    def test_resolving_with_no_address_is_unknown(self) -> None:
        provider = StaticGeoIPProvider({"203.0.113.0/24": "NG"}, default="GB")
        assert resolve_country(provider, None) is None

    def test_a_static_provider_rejects_a_bad_country_code(self) -> None:
        with pytest.raises(ValueError):
            StaticGeoIPProvider({"203.0.113.0/24": "NGA"})
