import logging
import sys
from importlib.metadata import packages_distributions, version
from inspect import getdoc
from pathlib import Path
from typing import Annotated, Any

import rich
from cyclopts import App, Parameter
from rich import color
from rich.console import Console
from rich.logging import RichHandler
from rich.syntax import ANSISyntaxTheme, Syntax, ANSI_DARK, ANSI_LIGHT
from rich.table import Table

import colorsaurus

from .base import Format, PersistentBytesIO, jsonpath_query, prefix_table
from .simplify import RecursiveAdapter
from .formats import DEFAULT_FORMAT

logger = logging.getLogger(__name__)
app = App(version_flags=["--version"], version=lambda: version("config-formats"))


def format_for(src: Path) -> str | None:
    for format in Format.registry.values():
        if src.suffix in format.suffixes:
            return format.name


def autodetect_read(src: Path | None) -> tuple[Any, Format]:
    if src is None:
        src_data = PersistentBytesIO(sys.stdin.buffer.read())
        src_data.seek(0)
    else:
        src_data = None
    format_errors = []
    for format_type in Format.registry.values():
        try:
            format = format_type(src or src_data, strict=True)
            return format, format.read()
        except FileNotFoundError as e:
            logger.error(str(e))
            raise
        except Exception as e:
            logger.debug(
                "%s is not a %s file: %s", src or "stdin", format_type.label, e
            )
            format_errors.append(e)
            if src_data is not None:
                src_data.seek(0)
    raise ExceptionGroup("No format was able to read the source", format_errors)


def should_print_highlighted(pretty: bool) -> bool:
    if pretty:
        console = rich.get_console()
        return console.is_terminal and not console.is_dumb_terminal
    else:
        return False


@app.command
def formats(simple: bool = False):
    """
    List the supported file formats.

    Args:
        simple: Only list the identifier and first extension of each format
    """
    if simple:
        for format in Format.registry.values():
            print(format.name, format.suffixes[0], sep="\t")
    else:
        table = Table("ID", "Label", "Extensions", "Notes", box=None)
        for format in Format.registry.values():
            notes = getdoc(format) or ""
            if hasattr(format, "post_load") and format.post_load:
                notes += f"\nafter parsing: {format.post_load}"
            if hasattr(format, "pre_dump") and format.pre_dump:
                notes += f"\nbefore serializing: {format.pre_dump}"
            table.add_row(
                format.name, format.label, " ".join(format.suffixes), notes.strip()
            )
        rich.get_console().print(table)


@app.default
def convert(
    src: Path | None = None,
    dst: Path | None = None,
    /,
    *,
    from_: Annotated[
        str | None,
        Parameter(
            ["-f", "--from"], help="Source format. One of " + ", ".join(Format.registry)
        ),
    ] = None,
    to_: Annotated[str | None, Parameter(["-t", "--to"])] = None,
    pretty: bool | None = None,
    query: Annotated[str | None, Parameter(["-q", "--query"])] = None,
    prefix: Annotated[str | None, Parameter(["-p", "--prefix"])] = None,
    verbose: Annotated[bool, Parameter(["-v", "--verbose"], negative=False)] = False,
    debug: Annotated[bool, Parameter(["-vv", "--debug"], negative=False)] = False,
    simplify: Annotated[bool, Parameter(["-s", "--simplify"])] = False,
):
    """
    Convert between configuration formats.

    Args:
        src: file to read from. If missing, use standard input.
        dst: file to write to. If missing, use standard output.
        from_: source format.
        to_: destination format.
        pretty: pretty-print the output. What this means and whether it makes any difference
                depends on the format. If we are printing to a terminal, we will also try syntax
            highlighting. The default is true for printing to a terminal and false otherwise.
        query: run the given JSONpath query on the data and return only the result.
        prefix: put the data in a mapping defined by the given prefix string (as you would put between the [] of a TOML table header)
        verbose: print info on detected formats etc.
        debug: print detailed info, e.g. on issues causing a format to be rejected during auto-detection
        simplify: force converting all types to the limited set of list, hashmap, string, float, integer, bool and null. Options for simplification:
    """
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        handlers=[RichHandler(show_time=False, console=Console(stderr=True))],
        format="%(message)s",
    )

    logger.debug(
        "Package: %s, Distribution: %s",
        __package__,
        packages_distributions().get(__package__ or ""),
    )

    if from_ is None and src is not None:
        from_ = format_for(src)
    if to_ is None and dst is not None:
        to_ = format_for(dst)
    if to_ is None:
        to_ = DEFAULT_FORMAT

    try:
        if from_ is None:
            src_format, data = autodetect_read(src)
            logger.info("Auto-detected %s", src_format)
        elif from_ in Format.registry:
            src_format = Format.registry[from_](src)
            data = src_format.read()
            logger.info("Read %s as specified", src_format)
        else:
            raise ValueError(
                f"Unknown source format: {from_}. Must be one of {', '.join(Format.registry)}"
            )
    except Exception as read_error:
        logger.critical(read_error, exc_info=False, stack_info=False)
        sys.exit(3)

    if simplify:
        dumb_down = RecursiveAdapter()
        data = dumb_down(data)

    if query:
        data = jsonpath_query(data, query)

    if prefix:
        data = prefix_table(data, prefix)

    if pretty is None:
        pretty = dst is None

    try:
        dst_format = Format.registry[to_](dst)
        logger.info("Writing %s", dst_format)

        if dst is None and should_print_highlighted(pretty):
            buf = PersistentBytesIO()
            dst_format.dump(data, buf, pretty)
            rich.get_console().print(
                Syntax(
                    buf.getvalue().decode("utf-8", errors="replace").strip(),
                    lexer=dst_format.highlight,
                    theme=ANSISyntaxTheme(ANSI_LIGHT)
                    if colorsaurus.color_scheme() == colorsaurus.ColorScheme.LIGHT
                    else ANSISyntaxTheme(ANSI_DARK),
                )
            )
        else:
            dst_format.write(data, pretty)
    except Exception as write_error:
        logger.critical(write_error, exc_info=False, stack_info=False)
        sys.exit(4)
