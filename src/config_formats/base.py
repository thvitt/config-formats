from io import BytesIO
import sys
from abc import ABC, abstractmethod
from numbers import Number
from pathlib import Path
from typing import IO, Any, ClassVar, Iterable, Mapping, Type
import logging

logger = logging.getLogger(__name__)


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

    use_stdinout: bool = False
    path: Path | None = None
    stream: IO | None = None

    @abstractmethod
    def load(self, stream: IO[bytes]) -> Any: ...

    @abstractmethod
    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None: ...

    def __init__(self, path: Path | IO | None):
        if path is None:
            self.use_stdinout = True
        elif isinstance(path, Path):
            self.path = path
        else:
            self.stream = path

    def __init_subclass__(cls):
        Format.registry[cls.name] = cls

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

    def __repr__(self) -> str:
        if self.use_stdinout:
            what = "stdin/stdout"
        elif self.path:
            what = str(self.path)
        else:
            what = f"a {type(self.stream)}"
        return f"<{self.__class__.__name__}: {self.label} Formatter ({self.name}) for <{what}>"


class PersistentBytesIO(BytesIO):
    def close(self):
        pass

    def getvalue(self) -> bytes:
        result = super().getvalue()
        super().close()
        return result
