from io import BytesIO
from os import setegid
import sys
from abc import ABC, abstractmethod
from numbers import Number
from pathlib import Path
from types import TracebackType
from typing import IO, Any, ClassVar, Iterable, Mapping, Sequence, Type, final
from datetime import date, time, datetime
import logging

logger = logging.getLogger(__name__)


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


def query(data: Any, path: str) -> Any:
    import jsonpath

    result = jsonpath.findall(path, data)
    if isinstance(result, Sequence) and len(result) == 1:
        result = result[0]

    return result


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
        close_stream = False
        stream = None
        try:
            if self.use_stdinout:
                stream = sys.stdin.buffer
            elif self.path:
                stream = self.path.open("rb")
            elif self.stream:
                stream = self.stream
            else:
                raise ValueError(
                    f"Format {self.name} has neither path nor stream, this is probably a bug."
                )
            result = self.load(stream)
            self.check_remainder(stream)
            return result
        finally:
            if stream is not None and close_stream:
                stream.close()

    def check_remainder(self, stream, force=False):
        """
        Check for unread data in the stream.

        Args:
            stream: an open stream
            force: if True, unconditionally check independent from strict mode

        Raises:
            RemainingDataError if there is remaining data.
        """
        if self.strict or force:
            try:
                remainder = stream.read()
                if len(remainder):
                    raise RemainingDataError(remainder, self)
            except OSError as e:
                logger.warning(
                    "An %s occurred while checking for remaining data in the stream of %s. Ignoring.",
                    e,
                    self,
                )

    def write(self, data: Any, pretty: bool = False) -> None:
        if self.use_stdinout:
            self.dump(data, sys.stdout.buffer, pretty)
        elif self.path:
            with self.path.open("wb") as f:
                self.dump(data, f, pretty)
        elif self.stream:
            self.dump(data, self.stream, pretty)

    @classmethod
    def from_str(cls, source: str) -> Any:
        stream = PersistentBytesIO(source.encode("utf-8"))
        format = cls(stream)
        return format.read()

    @classmethod
    def to_str(cls, data: Any, pretty: bool = False) -> str:
        stream = PersistentBytesIO()
        format = cls(stream)
        format.dump(data, stream, pretty)
        return stream.getvalue().decode("utf-8")

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
        self.seek(0)

    def getvalue(self) -> bytes:
        result = super().getvalue()
        self.seek(0)
        return result

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        super().close()
        return super().__exit__(exc_type, exc_val, exc_tb)


class RemainingDataError(Exception):
    def __init__(self, remainder: bytes, format: Format, message: str = ""):
        error = f"Found {len(remainder)} remaining bytes in stream after parsing {format}: {remainder[:30]}{'...' if len(remainder) > 30 else ''}"
        if message:
            error = error + ": " + message
        self.remainder = remainder
        self.format = format
        super().__init__(message)


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
