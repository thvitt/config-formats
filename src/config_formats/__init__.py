from abc import ABCMeta, abstractmethod
from numbers import Number
from typing import IO, Any, Type, ClassVar, Iterable, Mapping
from zipfile import Path
import io
import sys


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


class Format(ABCMeta):
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
        else:
            with self.path.open("rb") as f:
                return self.load(f)

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


class JSON(Format):
    name = "json"
    suffixes = [".json"]
    label = "JSON"

    def load(self, stream: IO[bytes]) -> Any:
        import json

        return json.load(stream)

    def dump(self, data: Any, stream: IO[bytes]) -> None:
        import json

        json.dump(dumb_down(data), io.TextIOWrapper(stream, encoding="utf-8"))


class TOML(Format):
    name = "toml"
    suffixes = [".toml"]
    label = "TOML"

    def load(self, stream: IO[bytes]) -> Any:
        import tomllib
        return tomllib.load(stream)

    def dump(self, data: Any, stream: IO[bytes]) -> None:
        import tomli_w
        tomli_w.dump(dumb_down(data), f)


def main() -> None:
    print("Hello from config-formats!")
