
import re

import yaml
from boltons.dictutils import OMD


ENTRY_PARTS_PARSERS = {}


def _init():
    ENTRY_PARTS_PARSERS['default'] = parse_entry_parts

_part_sep_re = re.compile(b'^---(?:\r\n?|\n)', flags=re.MULTILINE)


#class EntryLoader(object):
#    entry_readers = {'---': lambda: False}
#    entry_types = {}


def parse_entry(string, **kwargs):
    if not string:
        ValueError('expected non-empty string')
    tokens = _part_sep_re.split(string, maxsplit=2)

    try:
        _, headers_str, body = tokens
    except ValueError:
        raise ValueError('expected entry to have a headers section'
                         ' surrounded with "---" on separate lines')
    try:
        headers = omd_load(headers_str)
    except yaml.YAMLError:
        raise
    if not isinstance(headers, dict):
        raise ValueError('headers must be a YAML dictionary')

    parse_func = ENTRY_PARTS_PARSERS.get(headers.get('entry_type'),
                                         ENTRY_PARTS_PARSERS['default'])
    parts = parse_func(headers, body, **kwargs)
    return headers, parts


class StringLoaded(Exception):
    pass


def parse_entry_parts(headers, body, **kwargs):
    # NOTE: headers can also be modified in-place, this is by design
    parts = []
    tokens = _part_sep_re.split(body)
    for t in tokens:
        # TODO: pull out part metadata:  "#<!--{}-->"
        try:
            item = omd_load(t)
            if item is None:
                continue
            if isinstance(item, str):
                raise StringLoaded()
            if not isinstance(item, dict):
                raise ValueError('expected str or dict, not %r' % type(item))
            parts.append(item)
        except (StringLoaded, yaml.YAMLError):
            t = t.decode('utf-8')  # TODO: YAML doesn't decode to utf-8?
            parts.append(t)
    return parts


def omd_load(stream, Loader=yaml.Loader, object_pairs_hook=OMD):
    class OrderedLoader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)


_init()
