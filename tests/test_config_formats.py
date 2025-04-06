from config_formats import dumb_down
from pathlib import Path
from fractions import Fraction


def test_dumb_down_idempotency():
    already_dumb = [
        1,
        2.0,
        ["hello", "wold", {"foo": 42, "nothing": None}],
        True,
        False,
        0,
    ]
    assert dumb_down(already_dumb) == already_dumb
    assert dumb_down("Test") == "Test"


def test_dumb_down_set():
    assert dumb_down({1, 2, 3}) == [1, 2, 3]
    assert type(dumb_down({1, 2, 3})) is list


def test_dumb_down_simple():
    assert dumb_down(Path("foo")) == "foo"
    assert dumb_down(Fraction(3, 4)) == 0.75
