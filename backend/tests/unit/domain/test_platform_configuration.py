"""The configuration registry: types, bounds, and the absence of secrets."""

from __future__ import annotations

import pytest

from app.domain.admin.entities import AdminPrivilege
from app.domain.configuration.entities import ConfigSection, ConfigSettingSpec, ConfigType
from app.domain.configuration.settings import SETTINGS, get_spec, known_keys


class TestRegistry:
    def test_every_setting_key_is_unique(self) -> None:
        keys = [spec.key for spec in SETTINGS]
        assert len(keys) == len(set(keys))

    def test_every_setting_declares_an_administrative_privilege(self) -> None:
        for spec in SETTINGS:
            assert spec.privilege in AdminPrivilege.ALLOWED, spec.key

    def test_every_setting_has_a_description(self) -> None:
        for spec in SETTINGS:
            assert spec.description.strip(), spec.key

    def test_numeric_settings_declare_bounds(self) -> None:
        for spec in SETTINGS:
            if spec.type is ConfigType.INT:
                assert spec.minimum is not None, spec.key
                assert spec.maximum is not None, spec.key
                assert spec.minimum <= spec.maximum, spec.key

    def test_select_settings_declare_options(self) -> None:
        for spec in SETTINGS:
            if spec.type is ConfigType.SELECT:
                assert spec.options, spec.key

    def test_no_setting_is_named_like_a_secret(self) -> None:
        forbidden = ("secret", "password", "api_key", "credential", "token", "private_key")
        for spec in SETTINGS:
            lowered = spec.key.lower()
            assert not any(word in lowered for word in forbidden), spec.key

    def test_sections_cover_the_declared_settings(self) -> None:
        declared = {spec.section for spec in SETTINGS}
        assert ConfigSection.MAINTENANCE in declared
        assert ConfigSection.QUOTAS in declared
        assert ConfigSection.RATE_LIMITS in declared
        assert ConfigSection.SECURITY in declared

    def test_an_unknown_key_is_not_a_setting(self) -> None:
        assert get_spec("database.password") is None
        assert "database.password" not in known_keys()


class TestCoercion:
    def _spec(self, **overrides: object) -> ConfigSettingSpec:
        base: dict[str, object] = {
            "key": "example.setting",
            "type": ConfigType.INT,
            "section": ConfigSection.GENERAL,
            "privilege": AdminPrivilege.CONFIGURATION_MANAGE,
            "default": 5,
            "description": "An example.",
            "minimum": 1,
            "maximum": 10,
        }
        base.update(overrides)
        return ConfigSettingSpec(**base)  # type: ignore[arg-type]

    def test_a_boolean_rejects_a_string(self) -> None:
        spec = self._spec(type=ConfigType.BOOL, default=True, minimum=None, maximum=None)
        with pytest.raises(ValueError):
            spec.coerce("true")

    def test_an_integer_rejects_a_boolean(self) -> None:
        with pytest.raises(ValueError):
            self._spec().coerce(True)

    def test_an_integer_below_the_minimum_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._spec().coerce(0)

    def test_an_integer_above_the_maximum_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._spec().coerce(11)

    def test_an_integer_within_bounds_is_accepted(self) -> None:
        assert self._spec().coerce(7) == 7

    def test_a_select_rejects_an_option_outside_the_list(self) -> None:
        spec = self._spec(
            type=ConfigType.SELECT,
            default="a",
            options=("a", "b"),
            minimum=None,
            maximum=None,
        )
        with pytest.raises(ValueError):
            spec.coerce("c")

    def test_a_select_accepts_a_declared_option(self) -> None:
        spec = self._spec(
            type=ConfigType.SELECT,
            default="a",
            options=("a", "b"),
            minimum=None,
            maximum=None,
        )
        assert spec.coerce("b") == "b"

    def test_a_string_list_rejects_non_strings(self) -> None:
        spec = self._spec(type=ConfigType.STRING_LIST, default=[], minimum=None, maximum=None)
        with pytest.raises(ValueError):
            spec.coerce(["GB", 4])

    def test_a_string_list_is_trimmed_and_empties_dropped(self) -> None:
        spec = self._spec(type=ConfigType.STRING_LIST, default=[], minimum=None, maximum=None)
        assert spec.coerce([" GB ", "", "NG"]) == ["GB", "NG"]

    def test_a_string_list_respects_the_item_limit(self) -> None:
        spec = self._spec(
            type=ConfigType.STRING_LIST,
            default=[],
            minimum=None,
            maximum=None,
            max_items=2,
        )
        with pytest.raises(ValueError):
            spec.coerce(["GB", "NG", "US"])
