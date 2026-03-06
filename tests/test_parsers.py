import pytest
from boltons.dictutils import OMD
from chert.parsers import parse_entry, parse_entry_parts, omd_load


def test_parse_entry_basic():
    raw = b"""---
title: Hello World
publish_date: 2023-01-01
---
This is the body.
"""
    headers, parts = parse_entry(raw)
    assert headers['title'] == 'Hello World'
    assert len(parts) >= 1


def test_parse_entry_missing_headers_sep():
    with pytest.raises(ValueError, match='headers section'):
        parse_entry(b'No separator here')


def test_parse_entry_with_data_part():
    raw = b"""---
title: Test
---
Some text.
---
key: value
"""
    headers, parts = parse_entry(raw)
    assert headers['title'] == 'Test'
    assert len(parts) == 2
    assert isinstance(parts[0], str)
    assert isinstance(parts[1], dict)
    assert parts[1]['key'] == 'value'


def test_omd_load_preserves_order():
    stream = b"a: 1\nb: 2\nc: 3"
    result = omd_load(stream)
    assert isinstance(result, OMD)
    assert list(result.keys()) == ['a', 'b', 'c']
