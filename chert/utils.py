
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


_rel_link_re = re.compile(r'(?P<attribute>src|href)'
                          r'='
                          r'(?P<quote>[\'"])'
                          r'(?P<relpath>[/#.]+\S*)'
                          r'(?P=quote)')


def canonicalize_links(text, domain, filename):
    "turns links into canonical links for feed links"
    # does allow '..' links etc., even though they're probably errors

    def _replace_rel_link(match):
        ret = ''
        mdict = match.groupdict()
        ret += mdict['attribute']
        ret += '='
        ret += mdict['quote']
        ret += domain
        relpath = mdict['relpath']
        if relpath[0] == '#':
            ret += '/'
            ret += filename
        ret += relpath
        ret += mdict['quote']
        return ret

    return _rel_link_re.sub(_replace_rel_link, text)
