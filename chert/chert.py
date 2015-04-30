# -*- coding: utf-8 -*-

import io
import re
import os
import time
import string
import hashlib
import itertools
from datetime import datetime
from os.path import abspath, join as pjoin
from SimpleHTTPServer import SimpleHTTPRequestHandler
from BaseHTTPServer import HTTPServer
from threading import Thread

import yaml
from markdown import Markdown
from boltons.tbutils import ExceptionInfo
from boltons.osutils import mkdir_p, copytree, iter_find_files
from boltons.strutils import slugify
from boltons.dictutils import OrderedMultiDict as OMD
from boltons.debugutils import pdb_on_signal
from ashes import AshesEnv, Template
from markdown.extensions.codehilite import CodeHiliteExtension
from dateutil.parser import parse

from feed import absolutify, ATOM_TMPL

DEBUG = False
if DEBUG:
    pdb_on_signal()

"""
(notes)

Features:

 - simple edit history (not git integrated or anything fancy)
 - tags
 - length semantics
 - atom
 - footnotes

Eventual features:

 - image/static content workflow
"""

SITE_TITLE = 'Chert'
SITE_AUTHOR = 'Mahmoud Hashemi'

PREV_ENTRY_COUNT, NEXT_ENTRY_COUNT = 5, 5
LENGTH_BOUNDARIES = [(0, 'short'),
                     (100, 'long'),
                     (1000, 'manifesto')]
READING_WPM = 200.0

BASE_MD_EXTENSIONS = ['markdown.extensions.toc',
                      'markdown.extensions.def_list',
                      'markdown.extensions.footnotes']
_HILITE = CodeHiliteExtension()
MD_EXTENSIONS = BASE_MD_EXTENSIONS + [_HILITE]
_HILITE_INLINE = CodeHiliteExtension(noclasses=True,
                                     pygments_style='emacs')
INLINE_MD_EXTENSIONS = BASE_MD_EXTENSIONS + [_HILITE_INLINE]


ENTRY_ENCODING = 'utf-8'
ENTRY_PAT = '*.md'
LAYOUT_EXT = '.html'
LAYOUT_PAT = '*' + LAYOUT_EXT

EXPORT_HTML_EXT = '.html'  # some people might prefer .htm

DEV_SERVER_HOST = '0.0.0.0'
DEV_SERVER_PORT = 8080
DEV_SERVER_BASE_URL = '/'

_punct_re = re.compile('[%s]+' % re.escape(string.punctuation))

CANONICAL_DOMAIN = 'http://sedimental.org'
CANONICAL_BASE_PATH = '/'
if not CANONICAL_BASE_PATH.endswith('/'):
    CANONICAL_BASE_PATH += '/'
CANONICAL_URL = CANONICAL_DOMAIN + CANONICAL_BASE_PATH

DEFAULT_LAYOUT = 'entry'


class Chert(object):
    def __init__(self, input_path, **kw):
        self.entries = []

        self.entry_lists = kw.pop('entry_lists', [])

        # setting up paths
        self.paths = OMD()
        self._paths = OMD()  # for the raw input paths
        self._set_path('input_path', input_path)
        self._set_path('output_path', kw.pop('output_path', None), 'site')
        self._set_path('entries_path', kw.pop('entries_path', None), 'entries')
        self._set_path('theme_path', kw.pop('theme_path', None), 'theme')

        self.last_load = None
        self._autoload = kw.pop('autoload', None)
        if self._autoload:
            self.load()

        self.md_renderer = Markdown(extensions=MD_EXTENSIONS)
        self.inline_md_renderer = Markdown(extensions=INLINE_MD_EXTENSIONS)

        self.atom_template = Template('atom.xml', ATOM_TMPL)

    def _set_path(self, name, path, default_prefix=None):
        self._paths[name] = path
        if path:
            self.paths[name] = abspath(path)
        elif default_prefix:
            self.paths[name] = pjoin(self.input_path, default_prefix)
        else:
            raise ValueError('no path or default prefix set for %r' % name)
        return

    def get_site_info(self):
        ret = {}
        ret['title'] = SITE_TITLE
        ret['author_name'] = SITE_AUTHOR
        ret['canonical_url'] = CANONICAL_URL
        ret['canonical_domain'] = CANONICAL_DOMAIN
        ret['canonical_base_path'] = CANONICAL_BASE_PATH
        ret['last_updated'] = '2014-10-29T00:00:00-06:00'
        ret['export_html_ext'] = EXPORT_HTML_EXT
        return ret

    @property
    def input_path(self):
        return self.paths['input_path']

    @property
    def theme_path(self):
        return self.paths['theme_path']

    def process(self):
        if not self.last_load:
            self.load()
        self.validate()
        self.preprocess()
        self.render()
        self.audit()
        self.export()

    def load(self):
        self.last_load = time.time()
        self.html_renderer = AshesEnv(paths=[self.theme_path])
        self.html_renderer.load_all()

        entries_path = self.paths['entries_path']
        entry_paths = []
        for entry_path in iter_find_files(entries_path, ENTRY_PAT):
            entry_paths.append(entry_path)
        self.entries = []
        for ep in entry_paths:
            try:
                entry = Entry.from_path(ep)
            except IOError as ioe:
                print 'warning: skipping unopenable entry: %r' % ep
            else:
                self.entries.append(entry)
        self.entries.sort(key=lambda e: e.publish_date or datetime)

    def validate(self):
        dup_id_map = {}
        eid_map = OMD([(e.entry_id, e) for e in self.entries])
        for eid in eid_map:
            elist = eid_map.getlist(eid)
            if len(elist) > 1:
                dup_id_map[eid] = elist
        if dup_id_map:
            raise ValueError('duplicate entry IDs detected: %r' % dup_id_map)

        # TODO: assert necessary templates are present (post.html, etc.)

    def preprocess(self):
        std_pub_entries = [e for e in self.entries
                           if not e.is_special and not e.is_draft]
        for i, entry in enumerate(std_pub_entries, start=1):
            start_prev = max(0, i - PREV_ENTRY_COUNT)
            entry.prev_entries = std_pub_entries[start_prev:i - 1][::-1]
            entry.next_entries = std_pub_entries[i:i + NEXT_ENTRY_COUNT]

    def render(self):
        entries = self.entries
        mdr, imdr = self.md_renderer, self.inline_md_renderer
        # render markdown
        for e in entries:
            e.rendered_content = mdr.convert(e.content)
            mdr.reset()
            e.inline_rendered_content = absolutify(imdr.convert(e.content),
                                                   CANONICAL_DOMAIN)
            imdr.reset()

        # render html
        site_info = self.get_site_info()
        for entry in entries:
            tmpl_name = entry.layout + LAYOUT_EXT
            render_ctx = dict(entry=entry.to_dict(with_links=True),
                              site=site_info)
            rendered_html = self.html_renderer.render(tmpl_name, render_ctx)
            entry.rendered_html = rendered_html

        # render feed
        rendered_feed = self.atom_template.render('atom.xml', {})
        # print rendered_feed

    def audit(self):
        """
        Validation of rendered content, to be used for link checking.
        """
        pass

    def export(self):
        output_path = self.paths['output_path']

        mkdir_p(output_path)

        for entry in self.entries:
            entry_fn = entry.entry_id + EXPORT_HTML_EXT
            cur_output_path = pjoin(output_path, entry_fn)

            with open(cur_output_path, 'w') as f:
                f.write(entry.rendered_html.encode('utf-8'))


        # index is just the most recent entry for now
        index_path = pjoin(output_path, 'index' + EXPORT_HTML_EXT)
        if self.entries:
            index_content = self.entries[-1].rendered_html
        else:
            index_content = 'No entries yet!'
        with open(index_path, 'w') as f:
            f.write(index_content.encode('utf-8'))

        # copy all directories under the theme path
        for sdn in get_subdirectories(self.theme_path):
            copytree(pjoin(self.theme_path, sdn), pjoin(output_path, sdn))

    def serve(self):
        host = DEV_SERVER_HOST
        port = int(DEV_SERVER_PORT)
        base_url = DEV_SERVER_BASE_URL

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
            try:
                self.process()
            except KeyboardInterrupt:
                raise
            except Exception:
                import pdb;pdb.post_mortem()
                exc_info = ExceptionInfo.from_current()
                print exc_info.get_formatted()
            print 'Serving from %s' % output_path
            os.chdir(abspath(output_path))
            print 'Serving at http://%s:%s%s' % (host, port, base_url)

            thread = Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()
            if not serving:
                serving = True


def get_subdirectories(path):
    "Returns a list of directory names (not absolute paths) in a given path."
    if not os.path.isdir(path):
        raise ValueError('expected path to directory, not %r' % path)
    try:
        return next(os.walk(path))[1]
    except StopIteration:  # empty directories
        return []


def format_date(dt_obj):
    return dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')


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


_EPOCH_DATE = datetime.utcfromtimestamp(0)


"""
TODO: multiple entries in a single file (for short entries)?
TODO: tie-break publish dates with modified times

Metadata ideas:
  - Source
  - Via
"""
class Entry(object):
    def __init__(self, title=None, content=None, **kwargs):
        self.title = title
        self.entry_id = None or slugify(title)
        self.content = content or ''
        self.input_path = kwargs.pop('input_path', None)
        self.metadata = kwargs

        pub_date = self.metadata.get('publish_date')
        self.publish_date = parse(pub_date) if pub_date else _EPOCH_DATE

        self.edit_list = []
        self.last_edit_date = None or self.publish_date

        # TODO: needs to be set at process time, as prev/next links change
        hash_content = (self.title + self.content).encode('utf-8')
        self.entry_hash = hashlib.sha256(hash_content).hexdigest()

        no_punct = _punct_re.sub('', self.content)
        self.word_count = len(no_punct.split())
        self.reading_time = self.word_count / READING_WPM

    @property
    def is_special(self):
        return False

    @property
    def is_draft(self):
        return False  # 'drafts' in tags?

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
        try:
            ret['rendered_content'] = self.rendered_content
        except AttributeError as ae:
            print '---', ae, self.title

        if with_links:
            ret['prev_entries'] = [pe.to_dict() for pe in self.prev_entries]
            ret['next_entries'] = [ne.to_dict() for ne in self.next_entries]

        ret['filename'] = ret['entry_id'] + EXPORT_HTML_EXT
        return ret


class EntryList(object):
    def __init__(self, title, predicate=None):
        self.title = title
        self.predicate = predicate or (lambda e: True)
        self.entries = OMD()

        # feed url
        # list style (index or all-expanded)

    def load_entries(self, entries):
        for entry in entries:
            if entry.entry_id not in self.entries:
                self.entries[entry.entry_id] = entry

    def to_atom_xml(self):
        pass


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


if __name__ == '__main__':
    ch = Chert('scaffold_ideal')
    ch.serve()
