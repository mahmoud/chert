# -*- coding: utf-8 -*-

from __future__ import print_function

import re
import os
import imp
import json
import time
import string
import itertools
import subprocess
from datetime import datetime
from os.path import abspath, join as pjoin
try:
    from SocketServer import ThreadingMixIn
    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
except ImportError:
    from socketserver import ThreadingMixIn
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    unicode = str

from threading import Thread
from pipes import quote as shell_quote

import yaml
from markdown import Markdown
from boltons.urlutils import URL
from boltons.strutils import slugify, html2text
from boltons.dictutils import OrderedMultiDict as OMD
from boltons.timeutils import LocalTZ, UTC
from boltons.fileutils import mkdir_p, copytree, iter_find_files
from boltons.debugutils import pdb_on_signal

from ashes import AshesEnv, Template
from dateutil.parser import parse as parse_date
from markdown.extensions.codehilite import CodeHiliteExtension

from chert import hypertext
from chert.utils import dt_to_dict
from chert.version import __version__
from chert.log import chert_log as chlog
from chert.fal import ChertFAL
from chert.parsers import parse_entry

DEBUG = False
if DEBUG:
    pdb_on_signal()

CUR_PATH = os.path.dirname(abspath(__file__))
DEFAULT_DATE = datetime(2001, 2, 3, microsecond=456789, tzinfo=UTC)

DEFAULT_CONFIG_FILENAME = 'chert.yaml'

SITE_TITLE = 'Chert'
SITE_HEAD_TITLE = SITE_TITLE  # goes in the head tag
SITE_AUTHOR = 'Mahmoud Hashemi'
SITE_COPYRIGHT = '&copy; 2019 Mahmoud Hashemi <img height="14" src="/img/by-sa.png" />'
DEFAULT_AUTOREFRESH = 4

PREV_ENTRY_COUNT, NEXT_ENTRY_COUNT = 5, 5
LENGTH_BOUNDARIES = [(0, 'short'),
                     (100, 'long'),
                     (1000, 'manifesto')]
READING_WPM = 200.0

BASE_MD_EXTENSIONS = ['markdown.extensions.def_list',
                      'markdown.extensions.footnotes',
                      'markdown.extensions.fenced_code',
                      'markdown.extensions.tables']
_HILITE = CodeHiliteExtension()

MD_EXTENSIONS = BASE_MD_EXTENSIONS + [_HILITE]
_HILITE_INLINE = CodeHiliteExtension(noclasses=True,
                                     pygments_style='emacs')
INLINE_MD_EXTENSIONS = BASE_MD_EXTENSIONS + [_HILITE_INLINE]

ENTRY_ENCODING = 'utf-8'
ENTRY_PATS = ['*.md', '*.yaml']
HTML_LAYOUT_EXT = '.html'
HTML_LAYOUT_PAT = '*' + HTML_LAYOUT_EXT
MD_LAYOUT_EXT = '.md'
MD_LAYOUT_PAT = '*' + MD_LAYOUT_EXT

RSS_FEED_FILENAME = 'rss.xml'
ATOM_FEED_FILENAME = 'atom.xml'
EXPORT_SRC_EXT = '.md'
EXPORT_HTML_EXT = '.html'  # some people might prefer .htm

DEV_SERVER_HOST = '0.0.0.0'
DEV_SERVER_PORT = 8080
DEV_SERVER_BASE_PATH = '/'  # TODO: merge with prod canonical_base_path?

_punct_re = re.compile('[%s]+' % re.escape(string.punctuation))
_analytics_re = re.compile("(?P<code>[\w-]+)")

CANONICAL_DOMAIN = 'http://sedimental.org'
CANONICAL_BASE_PATH = '/'
if not CANONICAL_BASE_PATH.endswith('/'):
    CANONICAL_BASE_PATH += '/'
CANONICAL_URL = CANONICAL_DOMAIN + CANONICAL_BASE_PATH

DEFAULT_ENTRY_LAYOUT = 'entry'
DEFAULT_CONTENT_LAYOUT = 'content'
RESERVED_PAGES = ('index', 'archive')

_UNSET = object()

_part_sep_re = re.compile(b'^---(?:\r\n?|\n)', flags=re.MULTILINE)


class StringLoaded(Exception):
    pass


class Part(dict):
    def __init__(self, raw_part, entry, part_idx):
        self.raw_part = raw_part
        self.entry = entry
        self['part_idx'] = part_idx


class TextPart(Part):
    def __init__(self, *a, **kw):
        super(TextPart, self).__init__(*a, **kw)
        self['content'] = self.raw_part


class DataPart(Part):
    # TODO: test the ordinal template?
    # TODO: are there other special attr types besides "link",
    # "image", "date" (rating?)

    builtin_roles = set(['content', 'title', 'date', 'summary', 'image'])

    def __init__(self, raw_part, entry, part_idx, data_idx, data_consec_idx):
        super(DataPart, self).__init__(raw_part, entry, part_idx)
        self['data_idx'] = data_idx
        self['data_consec_idx'] = data_consec_idx
        ordinal_tmpl = self.entry.headers.get('ordinal_format') or ''
        self['ordinal_text'] = ordinal_tmpl.format(i=self['data_idx'],
                                                   ci=self['data_consec_idx'])
        self['summary'] = self.get_builtin_value('summary')
        self['title'] = self.get_builtin_value('title', '')

        custom_slug = self.get_builtin_value('title_slug', '')
        title_slug = custom_slug or slugify(self['title'])
        if title_slug != slugify(title_slug):
            raise ValueError('invalid custom slug: %r' % custom_slug)
        self['title_slug'] = title_slug

        self['content'] = self.get_builtin_value('content')
        self['tags'] = self.get_builtin_value('tags', [])
        self.load_date()
        self.load_attrs()

    def load_attrs(self):
        self['attrs'] = attrs = []
        for key, value in self.raw_part.items():
            if self.is_builtin_field(key):
                continue
            # TODO: multiple links or media for a single field
            # e.g., multiple authors or multiple angles
            cur_attr = {'key': key}
            cur_attr['title'] = self.get_field_label(key)
            cur_attr['type'] = self.get_field_type(key)
            fmt_func = getattr(self, '_format_' + cur_attr['type'])
            cur_attr['value'] = fmt_func(key, value)
            attrs.append(cur_attr)

        self['links'] = []
        self['images'] = []
        self['dates'] = []
        for attr in attrs:
            attr_type = attr['type']
            if attr_type in ('link', 'date', 'image'):
                self[attr_type + 's'].append(attr)
        return

    def load_date(self):
        # TODO: allow some degree of control over what attribute
        # represents the primary date (because parts can have multiple
        # types of dates. e.g., premiere_date and cancellation_date)
        dt = self.get_builtin_value('date')
        if dt:
            if not dt.tzinfo:
                # TODO: how would a part specify a date
                dt = dt.replace(tzinfo=LocalTZ)
            dt_dict = dt_to_dict(dt)
        else:
            dt_dict = {}
        self['date_obj'] = dt_dict

        date_tmpl = self.entry.headers.get('date_tmpl') or ''
        # TODO: use Templette or somesuch
        self['date_text'] = date_tmpl.format(**dt_dict)

    def _format_default(self, field_name, value):
        return value

    def _format_default_list(self, field_name, value):
        return [self._format_default(field_name, v) for v in value]

    def _format_link(self, field_name, value):
        if isinstance(value, str):
            return {'text': self.get_field_label(field_name),
                    'href': value,
                    'tip': None}
        return value

    def _format_link_list(self, field_name, value):
        return [self._format_link(field_name, v) for v in value]

    # TODO: *_format_image_*

    def is_builtin_field(self, field_name):
        builtins = set(self.entry.field_role_map.values()) | self.builtin_roles
        return field_name in builtins

    def get_builtin_value(self, builtin_name, default=None):
        field_name = self.entry.field_role_map.get(builtin_name, builtin_name)
        return self.raw_part.get(field_name, default)

    def get_field_label(self, field_name):
        try:
            return self.entry.field_label_map[field_name]
        except KeyError:
            return field_name.replace('_', ' ').title()

    def get_field_type(self, field_name):
        # TODO: to ensure consistent type detection, field types
        # could/should be determined at Entry load_mappings time.
        ret = 'default'
        value = self.raw_part[field_name]
        if not value:
            # falsy values should all be omitted in rendering anyways
            return ret
        is_list = isinstance(value, list)
        if is_list:
            value = value[0]
        if self._is_link(value):
            ret = 'link'
        elif self._is_image(value):
            ret = 'image'
        # TODO: detect date
        if is_list:
            ret += '_list'
        return ret

    def _is_image(self, value):
        # TODO
        if isinstance(value, str) and self._is_link(value):
            if value.endwith('jpg') or value.endswith('png'):
                return True
        return False

    def _is_link(self, value):
        # TODO: use a real check (hematite.url?)
        if isinstance(value, str) and '://' in value and ' ' not in value:
            return True
        return False


class Entry(object):
    def __init__(self, headers=None, parts=None, **kwargs):
        self.headers = headers or {}
        self.headers.update(kwargs)
        self.parts = parts

        self.source_text = kwargs.pop('source_text', None)
        self.source_path = kwargs.pop('source_path', None)

        pub_date = self.headers.get('publish_date')
        if not pub_date:
            # None = not present = not published (see is_draft)
            pub_dt = DEFAULT_DATE
        else:
            pub_dt = parse_date(pub_date)
            if not pub_dt.tzinfo:
                # TODO: allow timezone setting in chert config
                pub_dt = pub_dt.replace(tzinfo=LocalTZ)
        self.publish_date = pub_dt

        self.changelog = []  # TODO
        self.last_edit_date = []

        self.summary = self.headers.get('summary')
        self._load_mappings()
        self._load_parts()

    @property
    def title(self):
        return self.headers['title']

    @property
    def entry_root(self):
        entry_root = self.headers.get('entry_root', '')
        entry_base_path, entry_base_name = os.path.split(entry_root)

        if not entry_base_name:
            entry_base_name = slugify(self.title)
        elif entry_base_name.lower() != slugify(entry_base_name):
            raise ValueError('invalid custom entry_root: %r' % entry_root)

        entry_base_path = entry_base_path.strip('/')
        if entry_base_path:
            entry_base_path += '/'

        return entry_base_path + entry_base_name

    @property
    def output_filename(self):
        return self.entry_root + EXPORT_HTML_EXT

    @property
    def is_special(self):
        return bool(self.headers.get('special'))

    @property
    def is_draft(self):
        ret = bool(self.headers.get('draft'))
        ret = ret or self.publish_date is DEFAULT_DATE
        ret = ret or self.publish_date > datetime.now(LocalTZ)
        return ret

    @property
    def tags(self):
        return self.headers.setdefault('tags', [])

    @property
    def entry_layout(self):
        return self.headers.get('entry_layout', DEFAULT_ENTRY_LAYOUT)

    @property
    def content_layout(self):
        return self.headers.get('content_layout', DEFAULT_CONTENT_LAYOUT)

    @classmethod
    def from_dict(cls, in_dict, **kwargs):
        in_dict.update(kwargs)
        ret = cls(**in_dict)
        return ret

    @classmethod
    def from_path(cls, in_path):
        bytestring = ChertFAL(chlog).read(in_path)
        ret = cls.from_string(bytestring,
                              source_path=in_path)
        return ret

    def get_word_count(self):
        # TODO
        str_parts = [p for p in self.parts if isinstance(p, str)]
        content = ' '.join(str_parts)
        no_punct = _punct_re.sub('', content)
        return len(no_punct.split())

    def get_reading_time(self, rate=READING_WPM):
        return self.get_word_count() / float(rate)

    def _load_mappings(self):
        # a little like role->field map, but this strikes me as a more
        # intuitive name for users.
        self.field_role_map = frm = self.headers.get('field_role_map') or {}
        # self.field_role_map = frm = dict([(v, k) for k, v in _frm.items()])
        # TODO: scan over data and generate a uniform type map
        self.field_type_map = ftm = self.headers.get('field_type_map') or {}
        self.field_label_map = flm = self.headers.get('field_label_map') or {}

        # Validation
        frm, ftm, flm
        # TODO: etc.

    def _load_parts(self):
        """Loads each part to a standardized dictionary format suitable for
        rendering.

        di = data index, dci = consecutive data index, pi = part index
        di and pi always increase. dci resets at every text element.
        text parts have no data indices (di and dci).
        """
        self.loaded_parts = lps = []

        di, dci = 1, 1
        for pi, part in enumerate(self.parts, start=1):
            cur = {}
            cur['part_idx'] = pi
            if isinstance(part, str):
                cur = TextPart(part, self, pi)
                dci = 1
            elif isinstance(part, dict):
                cur = DataPart(part, self, pi, di, dci)
                di += 1
                dci += 1
            else:
                raise ValueError('unexpected part type: %r' % part)
            lps.append(cur)
        return

    @classmethod
    def from_string(cls, string, **kwargs):
        # for thought:
        #   * Markdown heading could look like YAML comment
        #   * how can a user explicitly delineate a YAML vs MD section
        #   * if no source_file, write out source_text to under_title.md
        #     (or something)
        headers, parts = parse_entry(string, **kwargs)
        return cls.from_dict({'headers': headers, 'parts': parts}, **kwargs)

    def __repr__(self):
        cn = self.__class__.__name__
        try:
            part_count = ' parts=%s' % len(self.parts)
        except:
            part_count = ''
        return '<%s title=%r%s>' % (cn, self.title, part_count)

    def to_dict(self, with_links=False):
        ret = dict(headers=self.headers,
                   parts=self.parts,
                   entry_root=self.entry_root,
                   output_filename=self.output_filename)

        attrs = ('rendered_md', 'entry_html', 'loaded_parts', 'summary',
                 'content_html', 'content_ihtml')
        for attr in attrs:
            ret[attr] = getattr(self, attr, None)

        if with_links:
            ret['prev_entries'] = [pe.to_dict() for pe in self.prev_entries]
            ret['next_entries'] = [ne.to_dict() for ne in self.next_entries]

        ret['publish_timestamp_local'] = to_timestamp(self.publish_date)
        ret['publish_timestamp_utc'] = to_timestamp(self.publish_date,
                                                    to_utc=True)
        if self.last_edit_date:
            ret['update_timestamp_local'] = to_timestamp(self.last_edit_date)
            ret['update_timestamp_utc'] = to_timestamp(self.last_edit_date,
                                                       to_utc=True)
        else:
            ret['update_timestamp_local'] = None
            ret['update_timestamp_utc'] = None
        return ret

    def _autosummarize(self):
        if not self.loaded_parts:
            raise ValueError('expected loaded_parts to be set.'
                             ' load and render, then autosummarize')
        first_part = self.loaded_parts[0]
        first_part_html = first_part.get('content_html')
        if first_part_html is None:
            raise ValueError('expected first part\'s content_html to be set.'
                             ' render the entry parts, then autosummarize.')
        rendered_text = html2text(first_part_html)
        summary = ' '.join(rendered_text.split()[:28]) + '...'
        return summary


class EntryList(object):
    # should end in a slash
    tag_path_part = 'tagged/'

    # Render HTML and atom feeds for a list of entries
    def __init__(self, entries=None, tag=None):
        self.entries = entries or []
        self.tag = tag
        self.path_part = ''
        if self.tag:
            self.path_part = self.tag_path_part + self.tag + '/'

        # list style (index or all-expanded)

    def get_list_info(self, site_info):
        ret = {}
        canonical_url = site_info['canonical_url']
        if self.tag:
            canonical_url += self.tag_path_part + self.tag + '/'
        canonical_rss_feed_url = canonical_url + RSS_FEED_FILENAME
        canonical_atom_feed_url = canonical_url + ATOM_FEED_FILENAME

        ret['tag'] = self.tag or ''
        ret['canonical_url'] = canonical_url
        ret['canonical_rss_feed_url'] = canonical_rss_feed_url
        ret['canonical_atom_feed_url'] = canonical_atom_feed_url
        return ret

    def render(self, site_obj):
        # TODO: with a more complex API this could be made stateless
        # and return the feed, making the site object track rendered
        # feeds
        site_info = site_obj.get_site_info()
        list_info = self.get_list_info(site_info)
        entry_ctxs = [e.to_dict(with_links=True) for e in self.entries]
        feed_render_ctx = {'entries': entry_ctxs,
                           'site': site_info,
                           'list': list_info}
        self.rendered_rss_feed = site_obj.rss_template.render(feed_render_ctx)
        self.rendered_atom_feed = site_obj.atom_template.render(feed_render_ctx)

        tag_archive_layout = site_obj.get_config('site', 'tag_archive_layout', 'brief')
        tag_archive_layout = 'archive_' + tag_archive_layout + HTML_LAYOUT_EXT
        self.rendered_html = site_obj.html_renderer.render(tag_archive_layout,
                                                           feed_render_ctx)

    def append(self, entry):
        return self.entries.append(entry)

    def clear(self):
        del self.entries[:]

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __getitem__(self, idx):
        return self.entries.__getitem__(idx)

    def __repr__(self):
        cn = self.__class__.__name__
        length = len(self.entries)
        titles = [e.title for e in self.entries]
        return '<%s length=%s titles=%r>' % (cn, length, titles)

    def sort(self, key=None, reverse=None):
        """Sort the entry list by a *key* function, defaulting to sorting by
        publish date. Unlike the built-in :meth:`list.sort`, the
        EntryList is sorted in reverse order by default. Change this
        with *reverse* set to *True*.
        """
        if key is None:
            key = lambda e: e.publish_date or datetime.now(LocalTZ)
        reverse = True if reverse is None else reverse
        return self.entries.sort(key=key, reverse=reverse)


class Site(object):
    _entry_type = Entry
    _entry_list_type = EntryList

    def __init__(self, input_path, **kw):
        # setting up paths
        self.paths = OMD()
        self._paths = OMD()  # for the raw input paths
        self.fal = ChertFAL(chlog)

        set_path = self._set_path
        set_path('input_path', input_path)
        set_path('config_path', kw.pop('config_path', None),
                 DEFAULT_CONFIG_FILENAME)
        set_path('entries_path', kw.pop('entries_path', None), 'entries')
        set_path('themes_path', kw.pop('themes_path', None), 'themes')
        set_path('uploads_path', kw.pop('uploads_path', None), 'uploads',
                 required=False)
        set_path('output_path', kw.pop('output_path', None), 'site',
                 required=False)
        self.reload_config()
        self.reset()
        self.dev_mode = kw.pop('dev_mode', False)
        if kw:
            raise TypeError('unexpected keyword arguments: %r' % kw)
        chlog.debug('init site').success()
        return

    def reload_config(self, **kw):
        # TODO: take optional kwarg
        self.config = yaml.safe_load(self.fal.read(self.paths['config_path']))

        # set theme
        with chlog.debug('setting theme'):
            theme_name = self.get_config('theme', 'name')
            theme_path = pjoin(self.themes_path, theme_name)
            self._set_path('theme_path', theme_path)

    def reset(self):
        """Called on __init__ and on reload before processing. Does not reset
        paths, etc., just state mutated during processing"""
        self.entries = self._entry_list_type()
        self.draft_entries = self._entry_list_type()
        self.special_entries = self._entry_list_type()
        self._rebuild_tag_map()

        self.last_load = None

        self.md_converter = Markdown(extensions=MD_EXTENSIONS)
        self.inline_md_converter = Markdown(extensions=INLINE_MD_EXTENSIONS)
        self._load_feed_templates()
        return

    def _set_path(self, name, path, default_suffix=None, required=True):
        """Set a path.

        Args:
            name: name of attribute (e.g., input_path)
            path: the path or None
            default_suffix: if path is None, self.input_path +
                default_suffix is used. The input_path should already
                be set.
            required: raise an error if path does not exist
        """
        with chlog.debug('set {path_name} path to {path_val}',
                         path_name=name, path_val=path) as rec:
            self._paths[name] = path
            if path:
                self.paths[name] = abspath(path)
            elif default_suffix:
                self.paths[name] = pjoin(self.input_path, default_suffix)
            else:
                raise ValueError('no path or default set for %r' % name)
            if required:
                if not os.path.exists(self.paths[name]):
                    raise RuntimeError('expected existent %s path, not %r'
                                       % (name, self.paths[name]))
            rec.success('set {path_name} path to {path_val}',
                        path_val=self.paths[name])
        return

    def _load_feed_templates(self):
        default_atom_tmpl_path = pjoin(CUR_PATH, ATOM_FEED_FILENAME)
        atom_tmpl_path = pjoin(self.theme_path, ATOM_FEED_FILENAME)
        if not os.path.exists(atom_tmpl_path):
            atom_tmpl_path = default_atom_tmpl_path
        # TODO: defer opening to loading?
        self.atom_template = Template.from_path(atom_tmpl_path,
                                                name=ATOM_FEED_FILENAME)

        default_rss_tmpl_path = pjoin(CUR_PATH, RSS_FEED_FILENAME)
        rss_tmpl_path = pjoin(self.theme_path, RSS_FEED_FILENAME)
        if not os.path.exists(rss_tmpl_path):
            rss_tmpl_path = default_rss_tmpl_path
        # TODO: defer opening to loading?
        self.rss_template = Template.from_path(rss_tmpl_path,
                                               name=RSS_FEED_FILENAME)

    def get_config(self, section, key=None, default=_UNSET):
        try:
            section_map = self.config[section]
        except KeyError:
            if default is _UNSET:
                raise
            return default
        if key is None:
            return section_map
        try:
            return section_map[key]
        except KeyError:
            if default is _UNSET:
                raise
            return default

    def get_site_info(self):
        ret = {}
        ret['dev_mode'] = self.dev_mode
        refresh_secs = self.get_config('dev', 'autorefresh', DEFAULT_AUTOREFRESH) or False

        ret['dev_mode_refresh_seconds'] = refresh_secs
        site_config = self.get_config('site')
        ret['title'] = site_config.get('title', SITE_TITLE)
        ret['head_title'] = site_config.get('title', ret['title'])
        ret['tagline'] = site_config.get('tagline', '')
        ret['primary_links'] = self._get_links('site', 'primary_links')
        ret['secondary_links'] = self._get_links('site', 'secondary_links')
        ret['charset'] = 'UTF-8'  # not really overridable
        ret['lang_code'] = site_config.get('lang_code', 'en')
        ret['copyright_notice'] = site_config.get('copyright', SITE_COPYRIGHT)
        ret['author_name'] = site_config.get('author', SITE_AUTHOR)
        ret['enable_analytics'] = site_config.get('enable_analytics', True)
        ret['analytics_code'] = self._get_analytics_code()

        prod_config = self.get_config('prod')
        ret['canonical_domain'] = prod_config.get('canonical_domain',
                                                  CANONICAL_DOMAIN).rstrip('/')
        ret['canonical_base_path'] = prod_config.get('canonical_base_path',
                                                     CANONICAL_BASE_PATH)
        if not ret['canonical_base_path'].endswith('/'):
            ret['canonical_base_path'] += '/'
        ret['canonical_url'] = ret['canonical_domain'] + ret['canonical_base_path']
        ret['rss_feed_url'] = ret['canonical_base_path'] + RSS_FEED_FILENAME
        ret['canonical_rss_feed_url'] = ret['canonical_url'] + RSS_FEED_FILENAME
        ret['atom_feed_url'] = ret['canonical_base_path'] + ATOM_FEED_FILENAME
        ret['canonical_atom_feed_url'] = ret['canonical_url'] + ATOM_FEED_FILENAME

        now = datetime.now(LocalTZ)
        ret['last_generated'] = to_timestamp(now)
        ret['last_generated_utc'] = to_timestamp(now, to_utc=True)
        ret['export_html_ext'] = EXPORT_HTML_EXT
        ret['export_src_ext'] = EXPORT_SRC_EXT
        return ret

    def _get_analytics_code(self):
        with chlog.debug('set analytics code') as rec:
            code = self.get_config('site', 'analytics_code', None)
            if code is None:
                rec.failure('site.analytics_code not set in config.yaml')
                return ''
            match = _analytics_re.search(unicode(code))
            if not match:
                rec.failure('analytics code blank or invalid: {!r}', code)
                return ''
            code = match.group('code')
            if len(code) < 6:
                rec.failure('analytics code too short: {!r}', code)
                return ''
            rec.success('analytics code set to {!r}', code)
        return code

    def _get_links(self, group, name):
        link_list = list(self.get_config(group, name, []))
        for link in link_list:
            if link['href'] and URL(link['href']).host:
                link['is_external'] = True
            else:
                link['is_external'] = False
        return link_list

    @property
    def input_path(self):
        return self.paths['input_path']

    @property
    def entries_path(self):
        return self.paths['entries_path']

    @property
    def themes_path(self):
        return self.paths['themes_path']

    @property
    def theme_path(self):
        return self.paths['theme_path']

    @property
    def uploads_path(self):
        return self.paths['uploads_path']

    @property
    def output_path(self):
        return self.paths['output_path']

    @property
    def all_entries(self):
        return (self.special_entries.entries
                + self.entries.entries
                + self.draft_entries.entries)

    def process(self):
        if self.last_load:
            self.reload_config()
            self.reset()
        self.load()
        self.validate()
        self.render()
        self.audit()
        self.export()

    def _load_custom_mod(self):
        input_path = self.paths['input_path']
        custom_mod_path = pjoin(input_path, 'custom.py')
        if not os.path.exists(custom_mod_path):
            self.custom_mod = None
            return
        # site_name = os.path.split(input_path)[1]
        with chlog.debug('import site custom module'):
            mod_name = 'custom'
            self.custom_mod = imp.load_source(mod_name, custom_mod_path)

    def _call_custom_hook(self, hook_name):
        with chlog.debug('call custom {hook_name} hook',
                         hook_name=hook_name,
                         reraise=False) as rec:
            if not self.custom_mod:
                # TODO: success or failure?
                rec.failure('no custom module loaded')
            try:
                hook_func = getattr(self.custom_mod, 'chert_' + hook_name)
            except AttributeError:
                rec.failure('no {} hook defined', hook_name)
                return
            hook_func(self)
        return

    @chlog.wrap('critical', 'load site')
    def load(self):
        self.last_load = time.time()
        self._load_custom_mod()
        self._call_custom_hook('pre_load')
        self.html_renderer = AshesEnv(paths=[self.theme_path])
        self.html_renderer.load_all()
        self.md_renderer = AshesEnv(paths=[self.theme_path],
                                    exts=['md'],
                                    keep_whitespace=False)
        self.md_renderer.autoescape_filter = ''
        self.md_renderer.load_all()

        entries_path = self.paths['entries_path']
        entry_paths = []
        for entry_path in iter_find_files(entries_path, ENTRY_PATS):
            entry_paths.append(entry_path)
        entry_paths.sort()

        for ep in entry_paths:
            with chlog.info('entry load') as rec:
                try:
                    entry = self._entry_type.from_path(ep)
                    rec['entry_title'] = entry.title
                    rec['entry_length'] = round(entry.get_reading_time(), 1)
                except IOError:
                    rec.exception('unopenable entry path: {}', ep)
                    continue
                except:
                    import pdb;pdb.post_mortem()
                    rec['entry_path'] = ep
                    rec.exception('entry {entry_path} load error: {exc_message}')
                    continue
                else:
                    rec.success('entry loaded:'
                                ' {entry_title} ({entry_length}m)')
            if entry.is_draft:
                self.draft_entries.append(entry)
            elif entry.is_special:
                self.special_entries.append(entry)
            else:
                self.entries.append(entry)

        # Sorting the EntryLists
        self.entries.sort()
        # sorting drafts/special pages doesn't do much
        self.draft_entries.sort(key=lambda e: os.path.getmtime(e.source_path))
        self.special_entries.sort()

        self._rebuild_tag_map()

        for i, entry in enumerate(self.entries, start=1):
            start_next = max(0, i - NEXT_ENTRY_COUNT)
            entry.next_entries = self.entries[start_next:i - 1][::-1]
            entry.prev_entries = self.entries[i:i + PREV_ENTRY_COUNT]

        self._call_custom_hook('post_load')

    def _rebuild_tag_map(self):
        self.tag_map = {}
        for entry in self.entries:
            for tag in entry.tags:
                try:
                    self.tag_map[tag].append(entry)
                except KeyError:
                    self.tag_map[tag] = self._entry_list_type([entry], tag=tag)
        for tag, entry_list in self.tag_map.items():
            entry_list.sort()

    @chlog.wrap('critical', 'validate site')
    def validate(self):
        self._call_custom_hook('pre_validate')
        dup_id_map = {}
        eid_map = OMD([(e.entry_root, e) for e in self.entries])
        for eid in eid_map:
            elist = eid_map.getlist(eid)
            if len(elist) > 1:
                dup_id_map[eid] = elist
        if dup_id_map:
            raise ValueError('duplicate entry IDs detected: %r' % dup_id_map)
        self._call_custom_hook('post_validate')

        # TODO: assert necessary templates are present (entry.html, etc.)

    def _make_anchor_id(self, header_text):
        return slugify(header_text,
                       delim=self.get_config('site', 'anchor_delim', '-'))

    @chlog.wrap('critical', 'render site', verbose=True)
    def render(self):
        self._call_custom_hook('pre_render')
        entries = self.entries
        mdc, imdc = self.md_converter, self.inline_md_converter
        site_info = self.get_site_info()
        canonical_domain = site_info['canonical_domain']

        def markdown2html(string):
            if not string:
                return ''
            ret = mdc.convert(string)
            mdc.reset()
            return ret

        def markdown2ihtml(string, entry_fn):
            if not string:
                return ''

            ret = hypertext.canonicalize_links(imdc.convert(string),
                                               canonical_domain,
                                               entry_fn)
            imdc.reset()
            return ret

        def render_parts(entry):
            for part in entry.loaded_parts:
                part['content_html'] = markdown2html(part['content'])
                part['content_ihtml'] = markdown2ihtml(part['content'],
                                                       entry.output_filename)
            if not entry.summary:
                with chlog.debug('autosummarizing', reraise=False):
                    entry.summary = entry._autosummarize()

            tmpl_name = entry.entry_layout + MD_LAYOUT_EXT
            render_ctx = {'entry': entry.to_dict(with_links=False),
                          'site': site_info}
            entry.content_md = self.md_renderer.render(tmpl_name, render_ctx)

            tmpl_name = entry.content_layout + HTML_LAYOUT_EXT
            content_html = self.html_renderer.render(tmpl_name, render_ctx)
            with chlog.debug('parse_content_html'):
                content_html_tree = hypertext.html_text_to_tree(content_html)
            with chlog.debug('add_toc_content_html'):
                hypertext.add_toc(content_html_tree, make_anchor_id=self._make_anchor_id)
            with chlog.debug('retarget_links_content_html'):
                _mode = self.get_config('site', 'retarget_links', 'external')
                hypertext.retarget_links(content_html_tree, mode=_mode)
            with chlog.debug('reserialize_content_html'):
                content_html = hypertext.html_tree_to_text(content_html_tree)
            entry.content_html = content_html

            render_ctx['inline'] = True
            content_ihtml = self.html_renderer.render(tmpl_name, render_ctx)
            with chlog.debug('canonicalize_ihtml_links'):
                # TODO: use tree (and move slightly down)
                content_ihtml = hypertext.canonicalize_links(content_ihtml,
                                                             canonical_domain,
                                                             entry.output_filename)
            with chlog.debug('parse_content_ihtml'):
                content_ihtml_tree = hypertext.html_text_to_tree(content_ihtml)
            with chlog.debug('add_toc_content_ihtml'):
                hypertext.add_toc(content_ihtml_tree)
            with chlog.debug('reserialize_content_ihtml'):
                content_ihtml = hypertext.html_tree_to_text(content_ihtml_tree)

            entry.content_ihtml = content_ihtml
            return

        def render_html(entry, with_links=False):
            tmpl_name = entry.entry_layout + HTML_LAYOUT_EXT
            render_ctx = {'entry': entry.to_dict(with_links=with_links),
                          'site': site_info}
            entry_html = self.html_renderer.render(tmpl_name, render_ctx)
            entry.entry_html = entry_html
            return

        with chlog.info('render published entry content', verbose=True):
            for entry in entries:
                render_parts(entry)
        with chlog.info('render draft entry content', verbose=True):
            for entry in self.draft_entries:
                render_parts(entry)
        with chlog.info('render special entry content', verbose=True):
            for entry in self.special_entries:
                render_parts(entry)

        with chlog.info('render entry html'):
            for entry in entries:
                render_html(entry, with_links=True)
            for entry in self.draft_entries:
                render_html(entry)
            for entry in self.special_entries:
                render_html(entry)

        # render feeds
        with chlog.info('render feed and tag lists'):
            self.entries.render(site_obj=self)
            for tag, entry_list in self.tag_map.items():
                entry_list.render(site_obj=self)

        self._call_custom_hook('post_render')

    @chlog.wrap('critical', 'audit site')
    def audit(self):
        """
        Validation of rendered content, to be used for link checking.
        """
        # TODO: check for &nbsp; and other common HTML entities in
        # feed xml (these entities aren't supported in XML/Atom/RSS)
        # the only ok ones are here: https://en.wikipedia.org/wiki/List_of_XML_and_HTML_character_entity_references#Predefined_entities_in_XML
        self._call_custom_hook('pre_audit')
        self._call_custom_hook('post_audit')

    @chlog.wrap('critical', 'export site')
    def export(self):
        fal = self.fal
        self._call_custom_hook('pre_export')
        output_path = self.paths['output_path']

        with chlog.critical('create output path'):
            mkdir_p(output_path)

        def export_entry(entry):
            entry_custom_base_path = os.path.split(entry.entry_root)[0]
            if entry_custom_base_path:
                mkdir_p(pjoin(output_path, entry_custom_base_path))
            er = entry.entry_root
            entry_html_fn = er + EXPORT_HTML_EXT
            entry_gen_md_fn = er + '.gen.md'
            entry_data_fn = er + '.json'

            html_output_path = pjoin(output_path, entry_html_fn)
            data_output_path = pjoin(output_path, entry_data_fn)
            gen_md_output_path = pjoin(output_path, entry_gen_md_fn)

            #fal.write(html_output_path, entry.entry_html)
            #
            fal.write(html_output_path, entry.entry_html)
            fal.write(gen_md_output_path, entry.content_md)  # TODO
            _data = json.dumps(entry.loaded_parts, indent=2, sort_keys=True)
            fal.write(data_output_path, _data)

            # TODO: copy file
            # fal.write(src_output_path, entry.source_text)
            return

        for entry in self.entries:
            export_entry(entry)
        for entry in self.draft_entries:
            export_entry(entry)
        for entry in self.special_entries:
            export_entry(entry)

        # index is just the most recent entry for now
        index_path = pjoin(output_path, 'index' + EXPORT_HTML_EXT)
        if self.entries:
            index_content = self.entries[0].entry_html
        else:
            index_content = 'No entries yet!'
        fal.write(index_path, index_content)
        archive_path = pjoin(output_path, ('archive' + EXPORT_HTML_EXT))
        fal.write(archive_path, self.entries.rendered_html)

        # output feeds
        rss_path = pjoin(output_path, RSS_FEED_FILENAME)
        fal.write(rss_path, self.entries.rendered_rss_feed)
        atom_path = pjoin(output_path, ATOM_FEED_FILENAME)
        fal.write(atom_path, self.entries.rendered_atom_feed)

        for tag, entry_list in self.tag_map.items():
            tag_path = pjoin(output_path, entry_list.path_part)
            mkdir_p(tag_path)
            rss_path = pjoin(tag_path, RSS_FEED_FILENAME)
            atom_path = pjoin(tag_path, ATOM_FEED_FILENAME)
            archive_path = pjoin(tag_path, 'index.html')
            fal.write(rss_path, entry_list.rendered_rss_feed)
            fal.write(atom_path, entry_list.rendered_atom_feed)
            fal.write(archive_path, entry_list.rendered_html)

        # copy assets, i.e., all directories under the theme path
        for sdn in get_subdirectories(self.theme_path):
            cur_src = pjoin(self.theme_path, sdn)
            cur_dest = pjoin(output_path, sdn)
            with chlog.critical('copy assets', src=cur_src, dest=cur_dest):
                copytree(cur_src, cur_dest)

        # optionally symlink the uploads directory.  this is an
        # important step for sites with uploads because Chert's
        # default rsync behavior picks up on these uploads by
        # following the symlink.
        with chlog.critical('link uploads directory') as rec:
            uploads_link_path = pjoin(output_path, 'uploads')
            if not os.path.isdir(self.uploads_path):
                rec.failure('no uploads directory at {}', self.uploads_path)
            else:
                message = None
                if os.path.islink(uploads_link_path):
                    os.unlink(uploads_link_path)
                    message = 'refreshed existing uploads symlink'
                os.symlink(self.uploads_path, uploads_link_path)
                rec.success(message)

        self._call_custom_hook('post_export')

    def serve(self):
        dev_config = self.get_config('dev')
        host = dev_config.get('server_host', DEV_SERVER_HOST)
        port = dev_config.get('server_port', int(DEV_SERVER_PORT))
        base_url = dev_config.get('base_path', DEV_SERVER_BASE_PATH)

        class Handler(SimpleHTTPRequestHandler):
            def send_head(self):
                if not self.path.startswith(base_url):
                    self.send_error(404, 'File not found')
                    return None
                self.path = self.path[len(base_url):]
                if not self.path.startswith('/'):
                    self.path = '/' + self.path
                return SimpleHTTPRequestHandler.send_head(self)
        Handler.extensions_map.update({'.md': 'text/plain',
                                       '.json': 'application/json'})


        class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
            """Handle requests in a separate thread."""

        server = ThreadedHTTPServer((host, port), Handler)
        serving = False

        config_path = self.paths['config_path']
        entries_path = self.paths['entries_path']
        theme_path = self.paths['theme_path']
        output_path = self.paths['output_path']
        for changed in _iter_changed_files(entries_path, theme_path, config_path):
            if serving:
                print('Changed %s files, regenerating...' % len(changed))
                server.shutdown()
            with chlog.critical('site generation', reraise=True):
                self.process()
            print('Serving from %s' % output_path)
            os.chdir(abspath(output_path))
            print('Serving at http://%s:%s%s' % (host, port, base_url))

            thread = Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()
            if not serving:
                serving = True
        # TODO: hook(s)?
        return

    @chlog.wrap('critical', 'publish site', inject_as='log_rec')
    def publish(self, log_rec):  # deploy?
        #self._load_custom_mod()
        #self._call_custom_hook('pre_publish')
        prod_config = self.get_config('prod')
        rsync_cmd = prod_config.get('rsync_cmd', 'rsync')
        if not rsync_cmd.isalpha():
            rsync_cmd = shell_quote(rsync_cmd)
        # TODO: add -e 'ssh -o "NumberOfPasswordPrompts 0"' to fail if
        # ssh keys haven't been set up.
        rsync_flags = prod_config.get('rsync_flags', 'avzPk')
        local_site_path = self.output_path
        if not local_site_path.endswith('/'):
            local_site_path += '/'  # not just cosmetic; rsync needs this
        assert os.path.exists(local_site_path + 'index.html')
        remote_host = prod_config['remote_host']
        remote_user = prod_config['remote_user']
        remote_path = prod_config['remote_path']
        remote_slug = "%s@%s:'%s'" % (remote_user,
                                      remote_host,
                                      shell_quote(remote_path))

        full_rsync_cmd = '%s -%s %s %s' % (rsync_cmd,
                                           rsync_flags,
                                           local_site_path,
                                           remote_slug)
        log_rec['rsync_cmd'] = full_rsync_cmd
        print('Executing', full_rsync_cmd)
        try:
            rsync_output = subprocess.check_output(full_rsync_cmd, shell=True)
        except subprocess.CalledProcessError as cpe:
            log_rec['rsync_exit_code'] = cpe.returncode
            rsync_output = cpe.output
            print(rsync_output)
            log_rec.failure('publish failed: rsync got exit code {rsync_exit_code}')
            return False
        else:
            print(rsync_output)
            log_rec.success()
        return True
        #self._call_custom_hook('post_publish')


def get_subdirectories(path):
    "Returns a list of directory names (not absolute paths) in a given path."
    if not os.path.isdir(path):
        raise ValueError('expected path to directory, not %r' % path)
    try:
        return next(os.walk(path))[1]
    except StopIteration:  # empty directories
        return []


def to_timestamp(dt_obj, to_utc=False):
    # TODO: RFC822: email.Utils.formatdate(time.mktime(dt.timetuple()))
    if to_utc and dt_obj.tzinfo:
        dt_obj = dt_obj.astimezone(UTC)
    if dt_obj.tzinfo in (UTC, None):
        return dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    return dt_obj.strftime('%Y-%m-%dT%H:%M:%S%z')


# TODO: also monitor config path
def _iter_changed_files(entries_path, theme_path, config_path, interval=0.5):
    mtimes = {}
    while True:
        changed = []
        to_check = itertools.chain([config_path],
                                   iter_find_files(entries_path, ENTRY_PATS),
                                   iter_find_files(theme_path, '*'))
        for path in to_check:
            try:
                new_mtime = os.stat(path).st_mtime
            except OSError:
                continue
            old_mtime = mtimes.get(path)
            if not old_mtime or new_mtime > old_mtime:
                mtimes[path] = new_mtime
                changed.append(path)
        if changed:
            yield changed
        time.sleep(interval)


"""
TODO: multiple entries in a single file (for short entries)?

Metadata ideas:
  - Source
  - Via
"""
_docstart_re = re.compile(b'^---(\r\n?|\n)')


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
