import pytest
from datetime import datetime, timezone, timedelta
from boltons.timeutils import LocalTZ, UTC

from chert.core import Entry, to_timestamp


def test_entry_from_string_minimal():
    raw = b"""---
title: Test Entry
publish_date: '2023-06-15'
---
Hello world.
"""
    entry = Entry.from_string(raw)
    assert entry.title == 'Test Entry'
    assert len(entry.parts) >= 1


def test_entry_is_draft_no_publish_date():
    raw = b"""---
title: Draft Entry
---
Content.
"""
    entry = Entry.from_string(raw)
    assert entry.is_draft is True


def test_entry_is_draft_future_date():
    raw = b"""---
title: Future Entry
publish_date: '2099-01-01'
---
Content.
"""
    entry = Entry.from_string(raw)
    assert entry.is_draft is True


def test_entry_is_draft_explicit_flag():
    raw = b"""---
title: Explicit Draft
publish_date: '2020-01-01'
draft: true
---
Content.
"""
    entry = Entry.from_string(raw)
    assert entry.is_draft is True


def test_entry_is_not_draft():
    raw = b"""---
title: Published Entry
publish_date: '2020-01-01'
---
Content.
"""
    entry = Entry.from_string(raw)
    assert entry.is_draft is False


def test_entry_entry_root_default():
    raw = b"""---
title: My Great Post
publish_date: '2020-01-01'
---
Content.
"""
    entry = Entry.from_string(raw)
    assert entry.entry_root == 'my_great_post'


def test_entry_entry_root_custom():
    raw = b"""---
title: My Great Post
publish_date: '2020-01-01'
entry_root: custom_slug
---
Content.
"""
    entry = Entry.from_string(raw)
    assert entry.entry_root == 'custom_slug'


def test_to_timestamp_utc():
    dt = datetime(2023, 6, 15, 12, 0, 0, tzinfo=UTC)
    result = to_timestamp(dt)
    assert result == '2023-06-15T12:00:00Z'


def test_to_timestamp_with_tz():
    tz = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2023, 6, 15, 12, 0, 0, tzinfo=tz)
    result = to_timestamp(dt)
    assert result == '2023-06-15T12:00:00+0530'


def test_to_timestamp_to_utc():
    tz = timezone(timedelta(hours=5))
    dt = datetime(2023, 6, 15, 17, 0, 0, tzinfo=tz)
    result = to_timestamp(dt, to_utc=True)
    assert result == '2023-06-15T12:00:00Z'
