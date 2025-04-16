from datetime import date, time
from os import path

from yaml import serialize

from config_formats.base import PersistentBytesIO, dumb_down
from config_formats.formats import JSON, TOML, YAML, MessagePack


data1 = {
    "version": 1,
    "list": ["one", 2, 3.0, True],
    "missing": None,
    "mapping": {
        "date": date(2020, 2, 20),
        "long string": "This is a string\n"
        "that consists of\n"
        "a bunch of lines\n"
        "and quite a few words.\n",
        "name": "config-files",
        "time": time(21, 0),
    },
}

dumb_data = dumb_down(data1, skip_none=True)


def test_json():
    serialized = JSON.to_str(data1)
    parsed = JSON.from_str(serialized)
    assert parsed == dumb_down(data1)


def test_yaml():
    serialized = YAML.to_str(data1)
    parsed = YAML.from_str(serialized)
    assert parsed == data1


def test_toml():
    serialized = TOML.to_str(dumb_data)
    parsed = TOML.from_str(serialized)
    print(serialized)
    assert dumb_down(parsed) == dumb_data


def test_msgpack():
    stream = PersistentBytesIO()
    MessagePack(stream).write(dumb_data)
    stream.seek(0)
    parsed = MessagePack(stream).read()
    assert parsed == dumb_data
