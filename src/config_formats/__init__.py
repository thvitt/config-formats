import io
import logging
import sys
from pathlib import Path
from typing import Any

from cyclopts import App
from rich.logging import RichHandler

from .base import Format, PersistentBytesIO
from .formats import DEFAULT_FORMAT
import rich
from rich.syntax import Syntax


logger = logging.getLogger(__name__)

app = App()


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


def should_print_highlighted(pretty: bool) -> bool:
    if pretty:
        console = rich.get_console()
        return console.is_terminal and not console.is_dumb_terminal
    else:
        return False


@app.default
def convert(
    src: Path | None = None,
    dst: Path | None = None,
    /,
    *,
    from_: str | None = None,
    to_: str | None = None,
    pretty: bool | None = None,
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

    if pretty is None:
        pretty = dst is None

    dst_format = Format.registry[to_](dst)

    if dst is None and should_print_highlighted(pretty):
        buf = PersistentBytesIO()
        dst_format.dump(data, buf, pretty)
        rich.get_console().print(
            Syntax(
                buf.getvalue().decode("utf-8", errors="replace"), lexer=dst_format.name
            )
        )
    else:
        dst_format.write(data, pretty)
