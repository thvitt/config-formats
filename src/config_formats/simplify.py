from dataclasses import MISSING, dataclass, field, fields
from datetime import date, datetime, time
from numbers import Number
from types import NoneType
from typing import Any, Iterable, Mapping, Type, cast


@dataclass(repr=False)
class RecursiveAdapter:
    """
    Converter that recursively walks down a structure of nested lists and mappings and converts
    it according to a list of rules.

    While the various configuration formats _basically_ all accept or produce a structure
    of nested sequences, mappings, and simple types, the details vary. E.g., YAML and Pickle
    can represent basically arbitrary data, JSON knows only a quite limited list of datatypes,
    TOML knows date and time, but does _not_ accept null values. So when converting JSON to TOML,
    you will probably want to parse dates, but you will definitively have to skip null values.

    Instantiate this class with the desired options to get a callable that can then be
    used to convert the data structures.
    """

    allow_date: bool = False
    """Retain date and time types in the data"""

    parse_date: bool = False
    """Try to parse strings as date or time"""

    parse_str: bool = False
    """Try to "upconvert" strings to other simple types (bool, numbers, null)"""

    special_tokens: Mapping[str, Any] = field(
        default_factory=lambda: {
            "null": None,
            "none": None,
            "nil": None,
            "true": True,
            "false": False,
            "on": True,
            "off": False,
            "yes": True,
            "no": False,
        }
    )
    """
    if parse_str is true and the casefolded, stripped version of a string value
    is in this mapping, use the corresponding value instead
    """

    skip_null_values: bool = False
    """Remove null values"""

    skip_null_keys: bool = False
    """Remove null as keys"""

    force_string_keys: bool = False
    """Keys must be strings"""

    parse_simple_lists: bool = False
    """should we try to parse strings into simple lists?"""

    join_simple_lists: bool = False
    """should we convert a list of values that are all simple types to a string?"""

    simple_list_separator: str = ";"
    """separator char for simple lists"""

    simple_list_final_separator: bool = False
    """do we need to end a simple list with the separator?"""

    simple_types: list[Type] = field(
        default_factory=lambda: [bool, int, float, str, NoneType]
    )
    """
    List of acceptable simple types.
    """

    max_level: int | None = None
    """Levels deeper than this are serialized using max_level_format"""

    max_level_format: str = "json"
    """Format for complex structures on level max_level"""

    def _convert_string(self, data: str, level: int = 0) -> Any:
        """Tries to convert the given string into a better matching simple type."""
        s = data.casefold().strip()
        if s in self.special_tokens:
            return self.special_tokens[s]

        if self.parse_date:
            for type_ in [time, date, datetime]:
                try:
                    return type_.fromisoformat(data)
                except ValueError:
                    pass

        for type_ in [int, float]:
            try:
                cand = type_(s)
                if str(cand) == s:
                    return cand
            except ValueError:
                pass

        if self.max_level is not None and self.max_level == level:
            from .base import Format

            deep_format = Format.registry[self.max_level_format]
            try:
                return self(deep_format.from_str(data), level + 1)
            except Exception:
                pass

        return data

    def _split_simple_list(self, data: str) -> list[Any]:
        """
        Converts a string into a list of simple types.

        The string is required to contain at least one simple_list_separator,
        and if simple_list_final_separator is True, it needs to end with the
        separator (or a ValueError will be thrown)
        """
        if data[:-1].count(self.simple_list_separator) < 2:
            raise ValueError(
                f"Separator {self.simple_list_separator} not at least twice inside string {data!r}"
            )
        if (
            self.simple_list_final_separator
            and data.strip()[-1] != self.simple_list_separator
        ):
            raise ValueError(f"{data!r} does not end with {self.simple_list_separator}")
        items = [item.strip() for item in data.split(self.simple_list_separator)]
        if self.simple_list_final_separator:
            items = items[:-1]
        if self.parse_str:
            return [self._convert_string(item) for item in items]
        else:
            return items

    def _get_simple_type(self, data: Any, *candidates) -> Type | None:
        """
        Tries to identify a compatible simple type for the given data item.

        Returns the first of the given candidate types of which the
        given data is an instance, or None of none of the candidates match.
        If no candiates are given, use the configured simple_types.
        """
        if not candidates:
            candidates = self.simple_types
        for type_ in candidates:
            if isinstance(data, type_):
                return type_
        return None

    def _is_simple_list(self, data: list[Any]) -> bool:
        return all(self._get_simple_type(item) for item in data)

    def _join_simple_list(self, data: list[Any]) -> str:
        result = self.simple_list_separator.join(str(item) for item in data)
        if self.simple_list_final_separator:
            result += self.simple_list_separator
        return result

    def __call__(self, data: Any, _level: int = 0):
        """
        Recursively convert the given data according to the configured rules.

        data can be any sequence or mapping or simple type.
        """
        if data is None:
            return None

        if self.allow_date:
            for datetime_type in [date, time, datetime]:
                if isinstance(data, datetime_type):
                    return data

        if isinstance(data, str):
            try:
                return self._split_simple_list(data)
            except ValueError:
                pass
            if self.parse_str:
                return self._convert_string(data, _level)

        if simple_type := self._get_simple_type(data):
            return simple_type(data)

        # TODO handle bytes

        if isinstance(data, Number):
            try:
                if data == int(data):  # type: ignore
                    return int(data)  # type: ignore
            except Exception:
                pass
            try:
                return float(data)  # type: ignore
            except Exception:
                pass

        if datetype := self._get_simple_type(data, datetime, date, time):
            if self.allow_date:
                return data
            else:
                return cast(datetime, data).isoformat()

        if isinstance(data, Mapping):
            if self.max_level == _level:
                from .base import Format

                return Format.registry[self.max_level_format].to_str(data)

            result = {}
            for key, value in data.items():
                if key is None and self.skip_null_keys:
                    continue
                if value is None and self.skip_null_values:
                    continue
                key = str(key) if self.force_string_keys else self(key, _level + 1)
                value = self(value, _level + 1)
                result[key] = value
            return result

        if isinstance(data, Iterable):
            if self.join_simple_lists:
                data = list(data)
                if self._is_simple_list(data):
                    return self._join_simple_list(data)
            if self.max_level == _level:
                from .base import Format

                return Format.registry[self.max_level_format].to_str(data)

            return [self(item, _level + 1) for item in data]

        # fallback
        return str(data)

    def configured_options(self) -> dict[str, Any]:
        result = {}
        for class_field in fields(self):
            value = getattr(self, class_field.name)
            if (
                class_field.default is not MISSING
                and class_field.default != value
                or (
                    class_field.default_factory is not MISSING
                    and class_field.default_factory() != value
                )
            ):
                result[class_field.name] = value
        return result

    def __str__(self) -> str:
        result = ", ".join(
            f"{key}={value!r}" for key, value in self.configured_options().items()
        )
        return result or "default JSON conversion"

    def __repr__(self) -> str:
        params = ", ".join(
            f"{key}={value!r}" for key, value in self.configured_options().items()
        )
        return f"{self.__class__.__qualname__}({params})"
