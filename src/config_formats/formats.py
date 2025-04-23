import logging
from io import TextIOWrapper
from typing import IO, Any, Mapping, cast

from .base import Format, dumb_down

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = "yaml"


class FormatException(OSError): ...


class JSON(Format):
    name = "json"
    suffixes = [".json"]
    label = "JSON"

    def load(self, stream: IO[bytes]) -> Any:
        import json

        return json.load(stream)

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        import json

        options = {"indent": 4, "ensure_ascii": False} if pretty else {}

        json.dump(dumb_down(data), TextIOWrapper(stream, encoding="utf-8"), **options)


class JSON5(Format):
    name = "json5"
    suffixes = [".json5"]
    label = "JSON5"

    def load(self, stream: IO[bytes]) -> Any:
        from json5 import load

        return load(TextIOWrapper(stream))

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        import json5

        json5.dump(data, TextIOWrapper(stream), indent=4 if pretty else 0)


class TOML(Format):
    """
    If the top level item is not a mapping, create a mapping with a key called "DEFAULT".
    """

    name = "toml"
    suffixes = [".toml"]
    label = "TOML"

    def load(self, stream: IO[bytes]) -> Any:
        import tomllib

        data = tomllib.load(stream)
        if len(data) == 1 and "DEFAULT" in data:
            data = data["DEFAULT"]
        elif len(data) == 0 and self.strict and stream.seekable():
            stream.seek(0)
            self.check_remainder(stream)
        return data

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        import tomli_w

        processed_data = dumb_down(
            data, allow_date=True, parse_date=True, skip_none=True
        )
        if not isinstance(processed_data, Mapping):
            processed_data = {"DEFAULT": processed_data}
        tomli_w.dump(processed_data, stream, multiline_strings=pretty)


class MessagePack(Format):
    name = "msgpack"
    suffixes = [".msgpack"]
    label = "MessagePack"

    def load(self, stream: IO[bytes]) -> Any:
        from umsgpack import load, UnpackException

        try:
            result = load(stream)
            logger.debug("stream: %s (%s)", stream, vars(stream))
            remainder = stream.read()
            if len(remainder) > 0:
                msg = f"{self}: {len(remainder)} bytes remaining (starting with {remainder[:50]})"
                if self.strict:
                    raise FormatException(msg)
                else:
                    logger.warning(msg)
            return result
        except UnpackException as e:
            logger.error("%s reading %s", e, self)
            raise
        # except ExtraData as ed:
        #     logger.debug("Extra data: %s", ed.extra)
        #     if self.strict:
        #         raise
        #     else:
        #         logger.warning("%d bytes of extra data in %s", len(ed.extra), self)
        #         return ed.unpacked

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        from umsgpack import dump

        dump(data, stream)


class HJSON(Format):
    name = "hjson"
    suffixes = [".hjson"]
    label = "HJSON"

    def load(self, stream: IO[bytes]) -> Any:
        import hjson

        return hjson.load(stream)

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        import hjson

        try:
            hjson.dump(data, TextIOWrapper(stream))
        except Exception:
            logger.debug("Failed to serialize %s", self, exc_info=True)
            raise


class INI(Format):
    """
    Windows-Style INI files. These are essentially [section] key=value files, and existing
    data will be forced into that format, so don’t expect round-tripping.
    """

    name = "ini"
    suffixes = [".ini"]
    label = "INI"

    def load(self, stream: IO[bytes]) -> Any:
        from configparser import ConfigParser

        parser = ConfigParser(
            strict=False,
            allow_no_value=True,
            empty_lines_in_values=True,
            allow_unnamed_section=True,
            interpolation=None,
        )
        parser.read_file(
            TextIOWrapper(stream),
            source=str(self.path) if self.path is not None else None,
        )
        result = cast(dict, dumb_down(parser, parse_str=True))
        if "DEFAULT" in result and not result["DEFAULT"]:
            del result["DEFAULT"]
        unnamed = "<UNNAMED_SECTION>"
        if unnamed in result:
            result.update(result[unnamed])
            del result[unnamed]
        return result

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        from configparser import ConfigParser

        parser = ConfigParser(strict=False, allow_unnamed_section=True)

        if not isinstance(data, Mapping):
            data = {"": data}

        logger.debug("data: %s", data)

        for title, content in data.items():
            if isinstance(content, Mapping):
                if not parser.has_section(title):
                    parser.add_section(title)
                    logger.debug("Added section %s", title)
                for key, value in content.items():
                    logger.debug("[%s]: %s=%s", title, key, value)
                    parser.set(title, str(key), "" if value is None else str(value))
            else:
                logger.debug("[]: %s=%s", title, content)
                parser.set(
                    "",
                    title,
                    "" if content is None else str(content),
                )

        parser.write(TextIOWrapper(stream))


class SEXP(Format):
    """S-Expressions – very experimental"""

    name = "sexp"
    suffixes = [".sexp"]
    label = "S-Expression"
    highlight = "lisp"

    def load(self, stream: IO[bytes]) -> Any:
        from sexpdata import load

        return load(TextIOWrapper(stream))

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        from sexpdata import dump

        dump(data, TextIOWrapper(stream))


class Python(Format):
    """Python literals. Does not execute arbitrary code ..."""

    name = "python"
    suffixes = [".py"]
    label = "Python"

    def load(self, stream: IO[bytes]) -> Any:
        from ast import literal_eval

        return literal_eval(stream.read().decode("utf-8"))

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        out = TextIOWrapper(stream)
        if pretty:
            from pprint import pprint

            pprint(data, out)
        else:
            out.write(repr(data))


class Pickle(Format):
    """
    Python pickle files. Reading is dangerous, as it can execute arbitrary code. Fails if a pickled class cannot be found.
    """

    name = "pickle"
    suffixes = [".pickle"]
    label = "Python Pickle"

    def load(self, stream: IO[bytes]) -> Any:
        from pickle import load

        try:
            return load(stream)
        except ImportError as e:
            logger.critical(
                "Import error unpickling %s: %s. It is expected that pickle files using non-stdlib classes are not readable.",
                self,
                e,
            )
            raise

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        from pickle import dump

        dump(data, stream)


class EDN(Format):
    name = "edn"
    suffixes = [".edn"]
    label = "EDN"
    highlight = "clojure"

    def load(self, stream: IO[bytes]) -> Any:
        import edn_format

        return edn_format.loads(stream.read())

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        import edn_format

        TextIOWrapper(stream).write(
            edn_format.dumps(data, keyword_keys=True, indent=4 if pretty else None)  # type: ignore
        )


class HOCON(Format):
    name = "hocon"
    suffixes = [".hocon"]
    label = "HOCON"

    def load(self, stream: IO[bytes]) -> Any:
        from pyhocon import ConfigFactory

        return ConfigFactory.parse_string(stream.read().decode())

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        from pyhocon import ConfigFactory, HOCONConverter

        config = ConfigFactory.from_dict(data, root=True)
        TextIOWrapper(stream).write(HOCONConverter.to_hocon(config, compact=not pretty))


class YAML(Format):
    """Supports almost any (even unsafe) data types. Reading is unsafe."""

    name = "yaml"
    suffixes = [".yaml", ".yml"]
    label = "YAML"

    def load(self, stream: IO[bytes]) -> Any:
        from yaml import Loader, load

        return load(stream, Loader=Loader)

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        from yaml import Dumper, dump

        class IndentDumper(Dumper):
            def increase_indent(self, flow=False, indentless=False):
                return super().increase_indent(flow, False)

        # passing our stream directly to yaml.dump causes a type error
        stream.write(
            dump(
                data,
                Dumper=IndentDumper,
                sort_keys=False,
                encoding="utf-8",
                allow_unicode=True,
            )  # .encode(encoding="utf-8")
        )


class DotEnv(Format):
    ".env files are essentially environment variable associations. Don’t expect roundtripping – complex values are not really supported, and variable names will be sanitized."

    name = "env"
    suffixes = [".env", ".envrc"]
    label = ".env"

    def load(self, stream: IO[bytes]) -> Any:
        from dotenv import dotenv_values

        return dotenv_values(stream=TextIOWrapper(stream))

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        import re
        from shlex import quote

        output = TextIOWrapper(stream)
        data = dumb_down(data)
        if not isinstance(data, Mapping):
            raise TypeError(
                f"Cannot serialize anything but mappings as .env file, but input is a {type(data)}"
            )
        for idx, (key, value) in enumerate(data.items(), start=1):
            sane_key = re.sub(r"[^a-zA-Z0-9_]+", "_", key)
            if not sane_key:
                logger.warning(
                    "entry %d in %s does not have a valid key: skipping", idx, self
                )
            if sane_key[0].isdigit():
                logger.warning(
                    "key %s of entry %d in %s starts with a number: prefixing with _",
                    sane_key,
                    idx,
                    self,
                )
                sane_key = "_" + sane_key
            if value is None:
                value = ""
            if isinstance(value, Mapping) or isinstance(value, list):
                logger.warning(
                    "complex value (a %s) of entry %s (#%d) in %s cannot be fully represented: check the result",
                    type(value),
                    sane_key,
                    idx,
                    self,
                )
                value = str(value)
            output.write(f"{key}={quote(value)}\n")
