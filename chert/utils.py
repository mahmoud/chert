
import re


def dt_to_dict(dt):
    ret = {'year': dt.year,
           'month': dt.month,
           'day': dt.day,
           'hour': dt.hour,
           'minute': dt.minute,
           'second': dt.second,
           'microsecond': dt.microsecond}
    if dt.tzname:
        ret['tzname'] = dt.tzname
        ret['dst'] = dt.dst
    return ret
