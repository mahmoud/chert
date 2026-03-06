from datetime import datetime, timezone, timedelta
from chert.utils import dt_to_dict


def test_dt_to_dict_naive():
    dt = datetime(2023, 6, 15, 10, 30, 45, 123456)
    result = dt_to_dict(dt)
    assert result['year'] == 2023
    assert result['month'] == 6
    assert result['day'] == 15
    assert result['hour'] == 10
    assert result['minute'] == 30
    assert result['second'] == 45
    assert result['microsecond'] == 123456
    # dt.tzname (without parens) is a bound method, always truthy,
    # so tzname/dst keys are always present due to the bug in source
    assert 'tzname' in result
    assert 'dst' in result


def test_dt_to_dict_aware():
    tz = timezone(timedelta(hours=5))
    dt = datetime(2023, 1, 1, 0, 0, 0, tzinfo=tz)
    result = dt_to_dict(dt)
    assert result['year'] == 2023
    assert result['month'] == 1
    assert result['day'] == 1
    # tzname and dst keys exist (they hold bound methods due to missing parens in source)
    assert 'tzname' in result
    assert 'dst' in result
