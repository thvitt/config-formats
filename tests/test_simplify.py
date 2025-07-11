from datetime import date, datetime, time
from pathlib import Path
from fractions import Fraction

import pytest

from config_formats.simplify import RecursiveAdapter


def test_dumb_down_idempotency():
    already_dumb = [
        1,
        2.0,
        ["hello", "wold", {"foo": 42, "nothing": None}],
        True,
        False,
        0,
    ]
    dumb_down = RecursiveAdapter()
    assert dumb_down(already_dumb) == already_dumb
    assert dumb_down("Test") == "Test"


def test_dumb_down_set():
    dumb_down = RecursiveAdapter()
    assert dumb_down({1, 2, 3}) == [1, 2, 3]
    assert type(dumb_down({1, 2, 3})) is list


def test_dumb_down_simple():
    dumb_down = RecursiveAdapter()
    assert dumb_down(Path("foo")) == "foo"
    assert dumb_down(Fraction(3, 4)) == 0.75


@pytest.mark.parametrize(
    ("string", "value"),
    [
        ("42", 42),
        ("1.0", 1.0),
        (" 0.1", 0.1),
        ("null", None),
        ("true", True),
        ("bla ", "bla "),
        ("2020-02-20", date(2020, 2, 20)),
        ("12:34:56", time(12, 34, 56)),
        ("2020-02-20T12:34:56", datetime(2020, 2, 20, 12, 34, 56)),
    ],
)
def test_str2simpletype_int(string, value):
    convert = RecursiveAdapter(parse_date=True, parse_str=True)
    result = convert(string)
    assert result == value
    assert type(result) is type(value)
