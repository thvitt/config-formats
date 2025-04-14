from io import BytesIO
import sys
from abc import ABC, abstractmethod
from numbers import Number
from pathlib import Path
from typing import IO, Any, ClassVar, Iterable, Mapping, Type
from datetime import date, time, datetime
import logging

logger = logging.getLogger(__name__)

_SPECIAL = {
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


def str2datetime(data: str) -> date | time | datetime | str:
    s = data.strip()
    for t in [date, time, datetime]:
        try:
            return t.fromisoformat(s)
        except ValueError:
            pass
    return data


def str2simpletype(
    data: str, date_types: bool = False
) -> str | int | float | bool | date | time | datetime | None:
    s = data.casefold().strip()
    if s in _SPECIAL:
        return _SPECIAL[s]
    else:
        for t in [int, float]:
            try:
                cand = t(s)
                if str(cand) == s:
                    return cand
            except ValueError:
                pass
    if date_types:
        return str2datetime(data)
    return data


def dumb_down(
    data: Any,
    allow_date: bool = False,
    parse_date: bool = False,
    parse_str: bool = False,
    skip_none: bool = False,
) -> list | dict | str | int | float | bool | None | datetime | date | time:
    # TODO special handling (for TOML)
    if data is None:
        return None

    if allow_date:
        for datetime_type in [date, time, datetime]:
            if isinstance(data, datetime_type):
                return data

    if isinstance(data, str) and parse_str:
        return str2simpletype(data, date_types=parse_date)
    elif isinstance(data, str) and parse_date:
        return str2datetime(data)

    # if it is a subtype of one of those primitive types, cast it directly into the specific type
    for primitive_type in (bool, int, float, str):
        if isinstance(data, primitive_type):
            return primitive_type(data)

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

    if isinstance(data, Mapping):
        return {
            dumb_down(key): dumb_down(
                value, allow_date, parse_date, parse_str, skip_none
            )
            for key, value in data.items()
            if key is not None and value is not None or not skip_none
        }

    if isinstance(data, Iterable):
        return [
            dumb_down(item, allow_date, parse_date, parse_str, skip_none)
            for item in data
        ]

    return str(data)


class Format(ABC):
    """ """

    name: ClassVar[str]
    suffixes: ClassVar[list[str]]
    label: ClassVar[str]
    registry: ClassVar[dict[str, Type]] = {}

    use_stdinout: bool = False
    path: Path | None = None
    stream: IO | None = None

    strict: bool = False

    @abstractmethod
    def load(self, stream: IO[bytes]) -> Any: ...

    @abstractmethod
    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None: ...

    def __init__(self, path: Path | IO | None, strict: bool = False):
        if path is None:
            self.use_stdinout = True
        elif isinstance(path, Path):
            self.path = path
        else:
            self.stream = path
        self.strict = strict

    def __init_subclass__(cls):
        Format.registry[cls.name] = cls
        if not hasattr(cls, "highlight"):
            cls.highlight = cls.name

    def read(self) -> Any:
        if self.use_stdinout:
            return self.load(sys.stdin.buffer)
        elif self.path:
            with self.path.open("rb") as f:
                return self.load(f)
        elif self.stream:
            return self.load(self.stream)
        else:
            raise ValueError(
                f"Format {self.name} has neither path nor stream, this is probably a bug."
            )

    def write(self, data: Any, pretty: bool = False) -> None:
        if self.use_stdinout:
            self.dump(data, sys.stdout.buffer, pretty)
        elif self.path:
            with self.path.open("wb") as f:
                self.dump(data, f, pretty)
        elif self.stream:
            self.dump(data, self.stream, pretty)

    @property
    def _src_label(self) -> str:
        if self.use_stdinout:
            return "stdin/stdout"
        elif self.path:
            return str(self.path)
        else:
            return f"a {type(self.stream)}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.label} Formatter ({self.name}) for {self._src_label}"

    def __str__(self) -> str:
        kind = "data of" if self.path is None else "file"
        return f"{self.label} {kind} {self._src_label}"


class PersistentBytesIO(BytesIO):
    def close(self):
        pass

    def getvalue(self) -> bytes:
        result = super().getvalue()
        super().close()
        return result
