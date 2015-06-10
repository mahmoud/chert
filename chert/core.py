# -*- coding: utf-8 -*-

import io
import re
import os
import imp
import time
import string
import shutil
import hashlib
import argparse
import itertools
import subprocess
from datetime import datetime
from os.path import abspath, join as pjoin
from SimpleHTTPServer import SimpleHTTPRequestHandler
from BaseHTTPServer import HTTPServer
from threading import Thread
from pipes import quote as shell_quote
from HTMLParser import HTMLParser
import htmlentitydefs

import yaml
from markdown import Markdown
from boltons.strutils import slugify
from boltons.dictutils import OrderedMultiDict as OMD
from boltons.tzutils import LocalTZ, UTC
from boltons.fileutils import mkdir_p, copytree, iter_find_files
from boltons.debugutils import pdb_on_signal
from lithoxyl import Logger, SensibleSink, Formatter, StreamEmitter
from ashes import AshesEnv, Template
from dateutil.parser import parse
from markdown.extensions.toc import TocExtension
from markdown.extensions.codehilite import CodeHiliteExtension

from hematite.url import URL

DEBUG = False
if DEBUG:
    pdb_on_signal()

CUR_PATH = os.path.dirname(abspath(__file__))
DEFAULT_DATE = datetime(2001, 2, 3, microsecond=456789, tzinfo=UTC)


SITE_TITLE = 'Chert'
SITE_HEAD_TITLE = SITE_TITLE  # goes in the head tag
SITE_AUTHOR = 'Mahmoud Hashemi'
SITE_COPYRIGHT = '&copy; 2015 Mahmoud Hashemi <img height="14" src="/img/by-sa.png" />'
DEFAULT_AUTOREFRESH = 4

PREV_ENTRY_COUNT, NEXT_ENTRY_COUNT = 5, 5
LENGTH_BOUNDARIES = [(0, 'short'),
                     (100, 'long'),
                     (1000, 'manifesto')]
READING_WPM = 200.0

BASE_MD_EXTENSIONS = ['markdown.extensions.def_list',
                      'markdown.extensions.footnotes',
                      'markdown.extensions.fenced_code']
_HILITE = CodeHiliteExtension()
_TOC_EXTENSION = TocExtension(title='Contents', anchorlink=True, baselevel=2)
# baselevel is actually a really useful feature regardless of TOC usage
MD_EXTENSIONS = BASE_MD_EXTENSIONS + [_HILITE, _TOC_EXTENSION]
_HILITE_INLINE = CodeHiliteExtension(noclasses=True,
                                     pygments_style='emacs')
INLINE_MD_EXTENSIONS = BASE_MD_EXTENSIONS + [_HILITE_INLINE]
# TODO: is leftover [TOC] in feed such a bad thing?

ENTRY_ENCODING = 'utf-8'
ENTRY_PAT = '*.md'
LAYOUT_EXT = '.html'
LAYOUT_PAT = '*' + LAYOUT_EXT

FEED_FILENAME = 'atom.xml'
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

DEFAULT_LAYOUT = 'entry'
RESERVED_PAGES = ('index', 'archive')

_UNSET = object()


chert_log = Logger('chert')
# TODO: duration_s, duration_ms, duration_us
stderr_fmt = Formatter('{end_local_iso8601_noms_notz} - {duration_msecs}ms - {message}')
stderr_emt = StreamEmitter('stderr')
stderr_sink = SensibleSink(formatter=stderr_fmt,
                           emitter=stderr_emt)
chert_log.add_sink(stderr_sink)


_link_re = re.compile("((?P<attribute>src|href)=\"/)")


def canonicalize_links(text, base):
    # turns links into canonical links for RSS
    return _link_re.sub(r'\g<attribute>="' + base + '/', text)


def _ppath(path):  # lithoxyl todo
    # find module path (or package path) and relativize to that?
    if not path.startswith('/'):
        return path
    rel_path = os.path.relpath(path, input_path)
    if rel_path.startswith('..'):
        return path
    return rel_path


def rec_dec(record, inject_as=None):
    def func_wrapper(func):
        def wrapped_func(*a, **kw):
            # kwargs: reraise + extras. message/raw_message/etc?
            # rewrite Callpoint of record to be the actual wrapped function?
            logger = record.logger
            rec_func = getattr(logger, record.level.name)
            new_record = rec_func(record.name)
            if inject_as:
                kw[inject_as] = new_record
            with new_record:
                return func(*a, **kw)
        return wrapped_func
    return func_wrapper


def logged_open(path, mode='rb'):
    # TODO: configurable level
    # TODO: needs to be a context manager of its own, composing the
    # logging and opening together

    open_type = mode[0]
    if open_type == 'r':
        msg = 'open {path} for read'
    elif open_type == 'w':
        msg = 'open {path} for write'
    elif open_type == 'a':
        msg = 'open {path} for append'
    else:
        msg = 'open {path}'
    with chert_log.critical(msg, path=path):
        return open(path, mode)


class Entry(object):
    def __init__(self, title=None, content=None, **kwargs):
        self.title = title
        self.entry_id = None or slugify(title)
        self.content = content or ''
        self.source_text = kwargs.pop('source_text', None)
        self.input_path = kwargs.pop('input_path', None)
        self.metadata = kwargs
        self.edit_list = []
        pub_date = self.metadata.get('publish_date')
        if not pub_date:
            # None = not present = not published (see is_draft)
            pub_dt = DEFAULT_DATE
        else:
            pub_dt = parse(pub_date)
            if not pub_dt.tzinfo:
                pub_dt = pub_dt.replace(tzinfo=LocalTZ)
        self.publish_date = pub_dt

        self.last_edit_date = None  # TODO

        # TODO: needs to be set at process time, as prev/next links change
        hash_content = (self.title + self.content).encode('utf-8')
        self.entry_hash = hashlib.sha256(hash_content).hexdigest()

        no_punct = _punct_re.sub('', self.content)
        self.word_count = len(no_punct.split())
        self.reading_time = self.word_count / READING_WPM

        self.summary = self.metadata.get('summary')

    @property
    def is_special(self):
        return bool(self.metadata.get('special'))

    @property
    def is_draft(self):
        ret = bool(self.metadata.get('draft'))
        ret = ret or self.publish_date is DEFAULT_DATE
        ret = ret or self.publish_date > datetime.now(LocalTZ)
        return ret

    @property
    def tags(self):
        return self.metadata.setdefault('tags', [])

    @property
    def layout(self):
        return self.metadata.get('layout', DEFAULT_LAYOUT)

    @classmethod
    def from_dict(cls, in_dict):
        ret = cls(**in_dict)
        return ret

    @classmethod
    def from_path(cls, in_path):
        entry_dict, text = read_yaml_text(in_path)
        for key in entry_dict.keys():
            entry_dict[key.lower()] = entry_dict.pop(key)
        entry_dict['source_text'] = logged_open(in_path).read()
        entry_dict['content'] = text
        entry_dict['input_path'] = in_path
        return cls.from_dict(entry_dict)

    def __repr__(self):
        cn = self.__class__.__name__
        return ('<%s title=%r word_count=%r>'
                % (cn, self.title, self.word_count))

    def to_dict(self, with_links=False):
        ret = dict(self.metadata,
                   title=self.title,
                   content=self.content,
                   entry_id=self.entry_id)
        ret['rendered_content'] = self.rendered_content
        ret['inline_rendered_content'] = self.inline_rendered_content
        ret['summary'] = self.summary
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

        ret['output_filename'] = ret['entry_id'] + EXPORT_HTML_EXT
        return ret

    def _autosummarize(self):
        if getattr(self, 'rendered_content', None) is None:
            raise ValueError('expected self.rendered_content to be set.'
                             ' render the entry, then autosummarize.')
        rendered_text = html2text(self.rendered_content)
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
        canonical_feed_url = canonical_url + FEED_FILENAME
        ret['tag'] = self.tag or ''
        ret['canonical_url'] = canonical_url
        ret['canonical_feed_url'] = canonical_feed_url
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
        self.rendered_feed = site_obj.atom_template.render(feed_render_ctx)

        tag_archive_layout = site_obj.get_config('site', 'tag_archive_layout', 'brief')
        tag_archive_layout = 'archive_' + tag_archive_layout + LAYOUT_EXT
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

        set_path = self._set_path
        set_path('input_path', input_path)
        set_path('config_path', kw.pop('config_path', None), 'config.yaml')
        set_path('entries_path', kw.pop('entries_path', None), 'entries')
        set_path('theme_path', kw.pop('theme_path', None), 'theme')
        set_path('uploads_path', kw.pop('uploads_path', None), 'uploads',
                 required=False)
        set_path('output_path', kw.pop('output_path', None), 'site',
                 required=False)
        self.reset()
        chert_log.debug('init site').success()
        self.dev_mode = kw.pop('dev_mode', False)
        if kw:
            raise TypeError('unexpected keyword arguments: %r' % kw)
        return

    def reset(self):
        """Called on __init__ and on reload before processing. Does not reset
        paths, etc., just state mutated during processing"""
        self.entries = self._entry_list_type()
        self.draft_entries = self._entry_list_type()
        self.special_entries = self._entry_list_type()
        self._rebuild_tag_map()

        # TODO: take optional kwarg
        self.config = yaml.load(logged_open(self.paths['config_path']))

        self.last_load = None

        self.md_renderer = Markdown(extensions=MD_EXTENSIONS)
        self.inline_md_renderer = Markdown(extensions=INLINE_MD_EXTENSIONS)
        self._load_atom_template()

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
        with chert_log.debug('set {path_name} path to {path_val}',
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

    def _load_atom_template(self):
        default_atom_tmpl_path = pjoin(CUR_PATH, FEED_FILENAME)
        atom_tmpl_path = pjoin(self.theme_path, FEED_FILENAME)
        if not os.path.exists(atom_tmpl_path):
            atom_tmpl_path = default_atom_tmpl_path

        # TODO: defer opening to loading?
        atom_tmpl_str = open(atom_tmpl_path).read()
        self.atom_template = Template(FEED_FILENAME, atom_tmpl_str)

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
        ret['feed_url'] = ret['canonical_base_path'] + FEED_FILENAME
        ret['canonical_feed_url'] = ret['canonical_url'] + FEED_FILENAME

        now = datetime.now(LocalTZ)
        ret['last_generated'] = to_timestamp(now)
        ret['last_generated_utc'] = to_timestamp(now, to_utc=True)
        ret['export_html_ext'] = EXPORT_HTML_EXT
        ret['export_src_ext'] = EXPORT_SRC_EXT
        return ret

    def _get_analytics_code(self):
        with chert_log.info('set analytics code') as rec:
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
    def theme_path(self):
        return self.paths['theme_path']

    @property
    def uploads_path(self):
        return self.paths['uploads_path']

    @property
    def output_path(self):
        return self.paths['output_path']

    def process(self):
        if self.last_load:
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
        site_name = os.path.split(input_path)[1]
        with chert_log.debug('import site custom module'):
            mod_name = site_name + '.custom'
            self.custom_mod = imp.load_source(mod_name, custom_mod_path)

    def _call_custom_hook(self, hook_name):
        with chert_log.debug('call custom {hook_name} hook',
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

    @rec_dec(chert_log.critical('load site'))
    def load(self):
        self.last_load = time.time()
        self._load_custom_mod()
        self._call_custom_hook('pre_load')
        self.html_renderer = AshesEnv(paths=[self.theme_path])
        self.html_renderer.load_all()

        entries_path = self.paths['entries_path']
        entry_paths = []
        for entry_path in iter_find_files(entries_path, ENTRY_PAT):
            entry_paths.append(entry_path)
        for ep in entry_paths:
            with chert_log.info('entry load') as rec:
                try:
                    entry = self._entry_type.from_path(ep)
                except IOError:
                    rec.exception('unopenable entry path: {}', ep)
                    continue
            if entry.is_draft:
                self.draft_entries.append(entry)
            elif entry.is_special:
                self.special_entries.append(entry)
            else:
                self.entries.append(entry)

        # Sorting the EntryLists
        self.entries.sort()
        self.draft_entries.sort()  # sorting drafts/special pages does do much
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

    @rec_dec(chert_log.critical('validate site'))
    def validate(self):
        self._call_custom_hook('pre_validate')
        dup_id_map = {}
        eid_map = OMD([(e.entry_id, e) for e in self.entries])
        for eid in eid_map:
            elist = eid_map.getlist(eid)
            if len(elist) > 1:
                dup_id_map[eid] = elist
        if dup_id_map:
            raise ValueError('duplicate entry IDs detected: %r' % dup_id_map)
        self._call_custom_hook('post_validate')

        # TODO: assert necessary templates are present (entry.html, etc.)

    @rec_dec(chert_log.critical('render site'))
    def render(self):
        self._call_custom_hook('pre_render')
        entries = self.entries
        mdr, imdr = self.md_renderer, self.inline_md_renderer
        site_info = self.get_site_info()
        canonical_domain = site_info['canonical_domain']
        def render_content(entry):
            entry.rendered_content = mdr.convert(entry.content)
            mdr.reset()
            entry.inline_rendered_content = canonicalize_links(imdr.convert(entry.content),
                                                               canonical_domain)
            imdr.reset()

            if not entry.summary:
                entry.summary = entry._autosummarize()

        def render_html(entry, with_links=False):
            tmpl_name = entry.layout + LAYOUT_EXT
            render_ctx = {'entry': entry.to_dict(with_links=with_links),
                          'site': site_info}
            rendered_html = self.html_renderer.render(tmpl_name, render_ctx)
            entry.rendered_html = rendered_html
            return

        for entry in entries:
            render_content(entry)
        for entry in self.draft_entries:
            render_content(entry)
        for entry in self.special_entries:
            render_content(entry)

        for entry in entries:
            render_html(entry, with_links=True)
        for entry in self.draft_entries:
            render_html(entry)
        for entry in self.special_entries:
            render_html(entry)

        # render feeds
        self.entries.render(site_obj=self)
        for tag, entry_list in self.tag_map.items():
            entry_list.render(site_obj=self)

        self._call_custom_hook('post_render')

    @rec_dec(chert_log.critical('audit site'))
    def audit(self):
        """
        Validation of rendered content, to be used for link checking.
        """
        # TODO: check for &nbsp; and other common HTML entities in
        # feed xml (these entities aren't supported in XML/Atom/RSS)
        # the only ok ones are here: https://en.wikipedia.org/wiki/List_of_XML_and_HTML_character_entity_references#Predefined_entities_in_XML
        self._call_custom_hook('pre_audit')
        self._call_custom_hook('post_audit')

    @rec_dec(chert_log.critical('export site'))
    def export(self):
        self._call_custom_hook('pre_export')
        output_path = self.paths['output_path']

        with chert_log.critical('create output path'):
            mkdir_p(output_path)

        def export_entry(entry):
            entry_src_fn = entry.entry_id + EXPORT_SRC_EXT
            entry_html_fn = entry.entry_id + EXPORT_HTML_EXT
            src_output_path = pjoin(output_path, entry_src_fn)
            html_output_path = pjoin(output_path, entry_html_fn)

            with logged_open(html_output_path, 'w') as f:
                f.write(entry.rendered_html.encode('utf-8'))
            with logged_open(src_output_path, 'w') as f:
                f.write(entry.source_text.encode('utf-8'))

        for entry in self.entries:
            export_entry(entry)
        for entry in self.draft_entries:
            export_entry(entry)
        for entry in self.special_entries:
            export_entry(entry)

        # index is just the most recent entry for now
        index_path = pjoin(output_path, 'index' + EXPORT_HTML_EXT)
        if self.entries:
            index_content = self.entries[0].rendered_html
        else:
            index_content = 'No entries yet!'
        with logged_open(index_path, 'w') as f:
            f.write(index_content.encode('utf-8'))
        archive_path = pjoin(output_path, ('archive' + EXPORT_HTML_EXT))
        with logged_open(archive_path, 'w') as f:
            f.write(self.entries.rendered_html.encode('utf-8'))

        # atom feeds
        atom_path = pjoin(output_path, FEED_FILENAME)
        with logged_open(atom_path, 'w') as f:
            f.write(self.entries.rendered_feed.encode('utf-8'))
        for tag, entry_list in self.tag_map.items():
            tag_path = pjoin(output_path, entry_list.path_part)
            mkdir_p(tag_path)
            atom_path = pjoin(tag_path, 'atom.xml')
            archive_path = pjoin(tag_path, 'index.html')
            with logged_open(atom_path, 'w') as f:
                f.write(entry_list.rendered_feed.encode('utf-8'))
            with logged_open(archive_path, 'w') as f:
                f.write(entry_list.rendered_html.encode('utf-8'))

        # copy assets, i.e., all directories under the theme path
        for sdn in get_subdirectories(self.theme_path):
            cur_src_dir = pjoin(self.theme_path, sdn)
            cur_dest_dir = pjoin(output_path, sdn)
            with chert_log.critical('copy assets {src} to {dest}',
                                    src=cur_src_dir, dest=cur_dest_dir):
                copytree(cur_src_dir, cur_dest_dir)

        # optionally symlink the uploads directory.  this is an
        # important step for sites with uploads because Chert's
        # default rsync behavior picks up on these uploads by
        # following the symlink.
        with chert_log.critical('link uploads directory') as rec:
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

        server = HTTPServer((host, port), Handler)
        serving = False

        entries_path = self.paths['entries_path']
        theme_path = self.paths['theme_path']
        output_path = self.paths['output_path']
        for changed in _iter_changed_files(entries_path, theme_path):
            if serving:
                print 'Changed %s files, regenerating...' % len(changed)
                server.shutdown()
            with chert_log.critical('site generation', reraise=False):
                self.process()
            print 'Serving from %s' % output_path
            os.chdir(abspath(output_path))
            print 'Serving at http://%s:%s%s' % (host, port, base_url)

            thread = Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()
            if not serving:
                serving = True
        # TODO: hook(s)?
        return

    @rec_dec(chert_log.critical('publish site'))
    def publish(self):  # deploy?
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
        print 'Executing', full_rsync_cmd
        try:
            rsync_output = subprocess.check_output(full_rsync_cmd, shell=True)
        except subprocess.CalledProcessError as cpe:
            return_code = cpe.returncode
            rsync_output = cpe.output
            print rsync_output
            print 'Publish failed, rsync got exit code', return_code
        else:
            print rsync_output
            print 'Publish succeeded.'
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
    if to_utc and dt_obj.tzinfo:
        dt_obj = dt_obj.astimezone(UTC)
    if dt_obj.tzinfo in (UTC, None):
        return dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    return dt_obj.strftime('%Y-%m-%dT%H:%M:%S%z')


def _iter_changed_files(entries_path, theme_path, interval=0.5):
    mtimes = {}
    while True:
        changed = []
        to_check = itertools.chain(iter_find_files(entries_path, ENTRY_PAT),
                                   iter_find_files(theme_path, LAYOUT_PAT))
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
TODO: tie-break publish dates with modified times

Metadata ideas:
  - Source
  - Via
"""

_docstart_re = re.compile(b'^---\r?\n')


def read_yaml_text(path):
    with open(path, 'rb') as fd:
        if fd.read(3) != b'---':
            raise ValueError('file did not start with "---": %r' % path)
        lines = []
        while True:
            line = fd.readline()
            if _docstart_re.match(line):
                break
            elif line == b'':
                return None
            lines.append(line)
        yaml_bio = io.BytesIO(b''.join(lines))
        yaml_bio.name = path
        yaml_dict = yaml.load(yaml_bio)
        if not yaml_dict:
            yaml_dict = {}
        text_content = fd.read().decode(ENTRY_ENCODING)
        return yaml_dict, text_content


def delete_dir_contents(path):
    for entry in os.listdir(path):
        cur_path = os.path.join(path, entry)
        if os.path.isfile(cur_path) or os.path.islink(cur_path):
            os.unlink(cur_path)
        elif os.path.isdir(cur_path):
            shutil.rmtree(cur_path)
    return


def get_argparser():
    prs = argparse.ArgumentParser()
    subprs = prs.add_subparsers(dest='action',
                                help='chert supports init, serve, and publish'
                                ' subcommands')
    init_prs = subprs.add_parser('init',
                                 help='create a new Chert site')
    init_prs.add_argument('target_dir',
                          help='path of a non-existent directory to'
                          ' create a new Chert site')
    subprs.add_parser('serve',
                      help='work on a Chert site using the local server')
    subprs.add_parser('render',
                      help='generate a local copy of the site')
    subprs.add_parser('publish',
                      help='upload a Chert site to the remote server')
    subprs.add_parser('clean',
                      help='clean Chert output site directory')

    return prs


def main():
    prs = get_argparser()
    kwargs = dict(prs.parse_args()._get_kwargs())
    action = kwargs['action']
    if action == 'serve':
        ch = Site(os.getcwd(), dev_mode=True)
        ch.serve()
    elif action == 'publish':
        ch = Site(os.getcwd())
        ch.process()
        ch.publish()
    elif action == 'render':
        ch = Site(os.getcwd())
        ch.process()
    elif action == 'init':
        target_dir = abspath(kwargs['target_dir'])
        if os.path.exists(target_dir):
            raise RuntimeError('chert init failed, path already exists: %s'
                               % target_dir)
        src_dir = pjoin(CUR_PATH, 'scaffold')
        copytree(src_dir, target_dir)
        print 'Created Chert instance in directory: %s' % target_dir
    elif action == 'clean':
        ch = Site(os.getcwd())
        delete_dir_contents(ch.output_path)
        print 'Cleaned Chert output path: %s' % ch.output_path
    else:
        raise ValueError('unknown action: %s' % action)


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.result = []

    def handle_data(self, d):
        self.result.append(d)

    def handle_charref(self, number):
        if number[0] == u'x' or number[0] == u'X':
            codepoint = int(number[1:], 16)
        else:
            codepoint = int(number)
        self.result.append(unichr(codepoint))

    def handle_entityref(self, name):
        try:
            codepoint = htmlentitydefs.name2codepoint[name]
        except KeyError:
            self.result.append(u'&' + name + u';')
        else:
            self.result.append(unichr(codepoint))

    def get_text(self):
        return u''.join(self.result)


def html2text(html):
    """Strips tags from HTML text, returning markup-free text. Also, does
    a best effort replacement of entities like "&nbsp;"

    >>> r = html2text(u'<a href="#">Test &amp;<em>(\u0394&#x03b7;&#956;&#x03CE;)</em></a>')
    >>> r == u'Test &(\u0394\u03b7\u03bc\u03ce)'
    True
    """
    # based on answers to http://stackoverflow.com/questions/753052/
    s = HTMLTextExtractor()
    s.feed(html)
    return s.get_text()


if __name__ == '__main__':
    main()
