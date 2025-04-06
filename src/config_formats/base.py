import sys
from abc import ABC, abstractmethod
from numbers import Number
from pathlib import Path
from typing import IO, Any, ClassVar, Iterable, Mapping, Type


def dumb_down(data: Any) -> list | dict | str | int | float | bool | None:
    # TODO special handling (for TOML)
    if data is None:
        return None

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
        return {dumb_down(key): dumb_down(value) for key, value in data.items()}

    if isinstance(data, Iterable):
        return [dumb_down(item) for item in data]

    return str(data)


class Format(ABC):
    name: ClassVar[str]
    suffixes: ClassVar[list[str]]
    label: ClassVar[str]

    registry: ClassVar[dict[str, Type]] = {}

    def __init__(self, path: Path | None):
        self.path = path

    def __init_subclass__(cls):
        Format.registry[cls.name] = cls

    def read(self) -> Any:
        if self.path is None:
            return self.load(sys.stdin.buffer)
        elif hasattr(self.path, "open"):
            with self.path.open("rb") as f:
                return self.load(f)
        else:
            return self.load(self.path)

    def write(self, data: Any) -> None:
        if self.path is None:
            self.dump(data, sys.stdout.buffer)
        else:
            with self.path.open("wb") as f:
                self.dump(data, f)

    @abstractmethod
    def load(self, stream: IO[bytes]) -> Any: ...

    @abstractmethod
    def dump(self, data: Any, stream: IO[bytes]) -> None: ...
