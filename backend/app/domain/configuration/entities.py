from __future__ import annotations

from enum import StrEnum


class ConfigType(StrEnum):
    BOOL = "bool"
    INT = "int"
    STRING = "string"
    STRING_LIST = "string_list"
    SELECT = "select"


class ConfigSection(StrEnum):
    GENERAL = "general"
    MAINTENANCE = "maintenance"
    QUOTAS = "quotas"
    RATE_LIMITS = "rate_limits"
    SECURITY = "security"


class ConfigSettingSpec:
    __slots__ = (
        "default",
        "description",
        "key",
        "max_items",
        "maximum",
        "minimum",
        "options",
        "privilege",
        "restart_required",
        "section",
        "type",
    )

    def __init__(
        self,
        *,
        key: str,
        type: ConfigType,
        section: ConfigSection,
        privilege: str,
        default: object,
        description: str,
        minimum: int | None = None,
        maximum: int | None = None,
        options: tuple[str, ...] = (),
        max_items: int | None = None,
        restart_required: bool = False,
    ) -> None:
        self.key = key
        self.type = type
        self.section = section
        self.privilege = privilege
        self.default = default
        self.description = description
        self.minimum = minimum
        self.maximum = maximum
        self.options = options
        self.max_items = max_items
        self.restart_required = restart_required

    def coerce(self, value: object) -> object:
        if self.type is ConfigType.BOOL:
            if not isinstance(value, bool):
                raise ValueError(f"{self.key} requires a boolean.")
            return value

        if self.type is ConfigType.INT:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{self.key} requires an integer.")
            if self.minimum is not None and value < self.minimum:
                raise ValueError(f"{self.key} must be at least {self.minimum}.")
            if self.maximum is not None and value > self.maximum:
                raise ValueError(f"{self.key} must be at most {self.maximum}.")
            return value

        if self.type is ConfigType.SELECT:
            if not isinstance(value, str) or value not in self.options:
                raise ValueError(f"{self.key} must be one of: {', '.join(self.options)}.")
            return value

        if self.type is ConfigType.STRING:
            if not isinstance(value, str):
                raise ValueError(f"{self.key} requires a string.")
            return value

        if self.type is ConfigType.STRING_LIST:
            if not isinstance(value, (list, tuple)) or any(
                not isinstance(item, str) for item in value
            ):
                raise ValueError(f"{self.key} requires a list of strings.")
            items = [item.strip() for item in value if item.strip()]
            if self.max_items is not None and len(items) > self.max_items:
                raise ValueError(f"{self.key} accepts at most {self.max_items} entries.")
            return items

        raise ValueError(f"Unknown configuration type for {self.key}.")
