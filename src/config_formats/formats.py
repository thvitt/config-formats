from io import TextIOWrapper

from .base import Format, dumb_down
from typing import IO, Any, Mapping

DEFAULT_FORMAT = "json"


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

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        import tomli_w

        processed_data = dumb_down(data)
        if not isinstance(processed_data, Mapping):
            processed_data = {"DEFAULT": processed_data}
        tomli_w.dump(processed_data, stream, multiline_strings=pretty)


class YAML(Format):
    name = "yaml"
    suffixes = [".yaml", ".yml"]
    label = "YAML"

    def load(self, stream: IO[bytes]) -> Any:
        from yaml import load, Loader

        return load(stream, Loader=Loader)

    def dump(self, data: Any, stream: IO[bytes], pretty: bool = False) -> None:
        from yaml import dump, Dumper

        # passing our stream directly to yaml.dump causes a type error
        stream.write(dump(data, Dumper=Dumper).encode(encoding="utf-8"))
