from datetime import date, datetime, time
from config_formats.simplify import RecursiveAdapter
import pytest


@pytest.mark.parametrize(
    "string,value",
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
