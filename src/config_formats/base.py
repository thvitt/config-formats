from io import BytesIO
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import IO, Any, ClassVar, Iterable, Self, Sequence, Type, TypeVar
import logging

from config_formats.simplify import RecursiveAdapter

logger = logging.getLogger(__name__)


def jsonpath_query(data: Any, path: str) -> Any:
    import jsonpath

    result = jsonpath.findall(path, data)
    if isinstance(result, Sequence) and len(result) == 1:
        result = result[0]

    return result


T = TypeVar("T")


def first(it: Iterable[T]) -> T:
    try:
        return next(iter(it))
    except StopIteration:
        raise IndexError("Iterable {it} must contain at least one item")


def prefix_table(data: Any, prefix: str) -> dict:
    """
    Prefix the data with the toml path given in the argument.

    Example:
        prefix({'foo': 42, 'bar': True}, "tool.example")
        {'tool': {'example': {'foo': 42, 'bar': True}}}

    """
    from tomllib import loads

    result = table = loads(
        f"[{prefix}]"
    )  # for prefix foo."bar.baz", table will be {"foo": {"bar.baz": {}}}

    while (inner := first(table.values())) != {}:
        table = inner

    key = first(table.keys())
    table[key] = data
    return result


class Format(ABC):
    """ """

    name: ClassVar[str]
    suffixes: ClassVar[list[str]]
    label: ClassVar[str]
    registry: ClassVar[dict[str, Type[Self]]] = {}
    binary: ClassVar[bool] = False
    pre_dump: ClassVar[RecursiveAdapter | None] = None
    post_load: ClassVar[RecursiveAdapter | None] = None

    use_stdinout: bool = False
    path: Path | None = None
    stream: IO | None = None

    strict: bool = False

    @abstractmethod
    def load(self, stream: IO[bytes]) -> Any: ...

    @abstractmethod
    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None: ...

    def smart_load(self, stream: IO[bytes]) -> Any:
        data = self.load(stream)
        if self.post_load is None:
            return data
        else:
            return self.post_load(data)

    def smart_dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        if self.pre_dump is not None:
            data = self.pre_dump(data)
        self.dump(data, stream, pretty)

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
            result = self.smart_load(stream)
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
            self.smart_dump(data, sys.stdout.buffer, pretty)
        elif self.path:
            with self.path.open("wb") as f:
                self.smart_dump(data, f, pretty)
        elif self.stream:
            self.smart_dump(data, self.stream, pretty)

    @classmethod
    def from_str(cls, source: str) -> Any:
        stream = PersistentBytesIO(source.encode("utf-8"))
        format = cls(stream)
        return format.read()

    @classmethod
    def to_str(cls, data: Any, pretty: bool = False) -> str | bytes:
        stream = PersistentBytesIO()
        format = cls(stream)
        format.smart_dump(data, stream, pretty)
        result = stream.getvalue()
        if cls.binary:
            return result
        else:
            return result.decode("utf-8")

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
