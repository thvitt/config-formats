import io
import logging
import sys
from abc import ABC, ABCMeta, abstractmethod
from numbers import Number
from pathlib import Path
from typing import IO, Any, ClassVar, Iterable, Mapping, Type

from cyclopts import App
from rich.logging import RichHandler
from rich.pretty import pprint

logger = logging.getLogger(__name__)

app = App()


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

        data = tomllib.load(stream)
        if len(data) == 1 and "DEFAULT" in data:
            data = data["DEFAULT"]
        return data

    def dump(self, data: Any, stream: IO[bytes]) -> None:
        import tomli_w

        processed_data = dumb_down(data)
        if not isinstance(processed_data, Mapping):
            processed_data = {"DEFAULT": processed_data}
        tomli_w.dump(processed_data, stream)


def format_for(src: Path) -> str | None:
    for format in Format.registry.values():
        if src.suffix in format.suffixes:
            return format.name


def autodetect_read(src: Path | None) -> tuple[Any, Format]:
    if src is None:
        src_data = io.BytesIO(sys.stdin.buffer.read())
        src_data.seek(0)
    else:
        src_data = None
    for format_type in Format.registry.values():
        try:
            format = format_type(src or src_data)
            return format, format.read()
        except Exception as e:
            logger.debug("%s is not a %s: %s", src or "stdin", format_type.name, e)
            if src_data:
                src_data.seek(0)
    raise ValueError("No format was able to read the source")


DEFAULT_FORMAT = "json"


@app.default
def convert(
    src: Path | None = None,
    dst: Path | None = None,
    /,
    *,
    from_: str | None = None,
    to_: str | None = None,
):
    """
    Convert between configuration formats.

    Args:
        src: file to read from. If missing, use standard input.
        dst: file to write to. If missing, use standard output.
        from_: source format.
        to_: destination format.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[RichHandler(show_time=False)],
        format="%(message)s",
    )

    if from_ is None and src is not None:
        from_ = format_for(src)
    if to_ is None and dst is not None:
        to_ = format_for(dst)
    if to_ is None:
        to_ = DEFAULT_FORMAT

    if from_ is None:
        src_format, data = autodetect_read(src)
    elif from_ in Format.registry:
        src_format = Format.registry[from_](src)
        data = src_format.read()
    else:
        raise ValueError(
            f"Unknown source format: {from_}. Must be one of {', '.join(Format.registry)}"
        )

    Format.registry[to_](dst).write(data)
