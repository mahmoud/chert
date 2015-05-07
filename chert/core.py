# -*- coding: utf-8 -*-

import io
import re
import os
import time
import string
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

import yaml
from markdown import Markdown
from boltons.tbutils import ExceptionInfo
from boltons.strutils import slugify
from boltons.dictutils import OrderedMultiDict as OMD
from boltons.fileutils import mkdir_p, copytree, iter_find_files
from boltons.debugutils import pdb_on_signal
from ashes import AshesEnv, Template
from dateutil.parser import parse
from markdown.extensions.toc import TocExtension
from markdown.extensions.codehilite import CodeHiliteExtension


DEBUG = False
if DEBUG:
    pdb_on_signal()

CUR_PATH = os.path.dirname(abspath(__file__))
DEFAULT_DATE = datetime(2000, 1, 1)

SITE_TITLE = 'Chert'
SITE_HEAD_TITLE = SITE_TITLE  # goes in the head tag
SITE_AUTHOR = 'Mahmoud Hashemi'
SITE_COPYRIGHT = '&copy; 2015 Mahmoud Hashemi <img height="14" src="/img/by-sa.png" />'

PREV_ENTRY_COUNT, NEXT_ENTRY_COUNT = 5, 5
LENGTH_BOUNDARIES = [(0, 'short'),
                     (100, 'long'),
                     (1000, 'manifesto')]
READING_WPM = 200.0

BASE_MD_EXTENSIONS = ['markdown.extensions.def_list',
                      'markdown.extensions.footnotes']
_HILITE = CodeHiliteExtension()
_TOC_EXTENSION = TocExtension(title='Contents', anchorlink=True, baselevel=2)
# baselevel is actually a really useful feature regardless of TOC usage
MD_EXTENSIONS = BASE_MD_EXTENSIONS + [_HILITE, _TOC_EXTENSION]
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
_UNSET = object()


_link_re = re.compile("((?P<attribute>src|href)=\"/)")


def canonicalize_links(text, base):
    # turns links into canonical links for RSS
    return _link_re.sub(r'\g<attribute>="' + base + '/', text)


class Chert(object):
    def __init__(self, input_path, **kw):
        self.entries = []

        self.entry_lists = kw.pop('entry_lists', [])

        # setting up paths
        self.paths = OMD()
        self._paths = OMD()  # for the raw input paths

        set_path = self._set_path
        set_path('input_path', input_path)
        set_path('config_path', kw.pop('config_path', None), 'config.yaml')
        set_path('entries_path', kw.pop('entries_path', None), 'entries')
        set_path('theme_path', kw.pop('theme_path', None), 'theme')
        set_path('output_path', kw.pop('output_path', None), 'site',
                 required=False)
        self.config = yaml.load(open(self.paths['config_path']))
        self.last_load = None
        self._autoload = kw.pop('autoload', None)
        if self._autoload:
            self.load()

        self.md_renderer = Markdown(extensions=MD_EXTENSIONS)
        self.inline_md_renderer = Markdown(extensions=INLINE_MD_EXTENSIONS)

        default_atom_tmpl_path = pjoin(CUR_PATH, 'atom.xml')
        atom_tmpl_path = pjoin(self.theme_path, 'atom.xml')
        if not os.path.exists(atom_tmpl_path):
            atom_tmpl_path = default_atom_tmpl_path

        self.atom_template = Template('atom.xml', open(atom_tmpl_path).read())

    def _set_path(self, name, path, default_prefix=None, required=True):
        """Set a path.

        Args:
            name: name of attribute (e.g., input_path)
            path: the path or None
            default_prefix: if path is None, self.input_path +
                default_prefix is used. The input_path should already
                be set.
            required: raise an error if path does not exist
        """
        self._paths[name] = path
        if path:
            self.paths[name] = abspath(path)
        elif default_prefix:
            self.paths[name] = pjoin(self.input_path, default_prefix)
        else:
            raise ValueError('no path or default prefix set for %r' % name)
        if required:
            if not os.path.exists(self.paths[name]):
                raise RuntimeError('expected existent %s path, not %r'
                                   % (name, self.paths[name]))
        return

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
        site_config = self.get_config('site')
        ret['title'] = SITE_TITLE
        ret['head_title'] = SITE_HEAD_TITLE
        ret['tagline'] = site_config.get('tagline', '')
        ret['main_links'] = site_config.get('main_links', [])
        ret['alt_links'] = site_config.get('alt_links', [])
        ret['lang_code'] = site_config.get('lang_code', 'en')
        ret['copyright_notice'] = SITE_COPYRIGHT
        ret['author_name'] = SITE_AUTHOR
        ret['canonical_url'] = CANONICAL_URL
        ret['canonical_domain'] = CANONICAL_DOMAIN
        ret['canonical_base_path'] = CANONICAL_BASE_PATH
        ret['feed_url'] = CANONICAL_BASE_PATH + 'atom.xml'
        ret['canonical_feed_url'] = ret['feed_url'] + 'atom.xml'
        ret['last_generated'] = format_date(datetime.now())
        ret['export_html_ext'] = EXPORT_HTML_EXT
        return ret

    @property
    def input_path(self):
        return self.paths['input_path']

    @property
    def theme_path(self):
        return self.paths['theme_path']

    @property
    def output_path(self):
        return self.paths['output_path']

    def process(self, reread=False):
        if reread or not self.last_load:
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
        self.entries.sort(key=lambda e: e.publish_date or datetime.now(),
                          reverse=True)

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
            start_next = max(0, i - NEXT_ENTRY_COUNT)
            entry.next_entries = std_pub_entries[start_next:i - 1][::-1]
            entry.prev_entries = std_pub_entries[i:i + PREV_ENTRY_COUNT]

    def render(self):
        entries = self.entries
        mdr, imdr = self.md_renderer, self.inline_md_renderer
        # render markdown
        for e in entries:
            e.rendered_content = mdr.convert(e.content)
            mdr.reset()
            e.inline_rendered_content = canonicalize_links(imdr.convert(e.content),
                                                           CANONICAL_DOMAIN)
            imdr.reset()

        # render html
        site_info = self.get_site_info()
        for entry in entries:
            tmpl_name = entry.layout + LAYOUT_EXT
            render_ctx = {'entry': entry.to_dict(with_links=True),
                          'site': site_info}
            rendered_html = self.html_renderer.render(tmpl_name, render_ctx)
            entry.rendered_html = rendered_html

        # render feed
        entry_ctxs = [e.to_dict(with_links=True) for e in entries]
        feed_render_ctx = {'entries': entry_ctxs,
                           'site': site_info}
        self.rendered_feed = self.atom_template.render(feed_render_ctx)
        # print rendered_feed

    def audit(self):
        """
        Validation of rendered content, to be used for link checking.
        """
        # TODO: check for &nbsp; and other common HTML entities in
        # feed xml (these entities aren't supported in XML/Atom/RSS)
        # the only ok ones are here: https://en.wikipedia.org/wiki/List_of_XML_and_HTML_character_entity_references#Predefined_entities_in_XML
        pass

    def export(self):
        output_path = self.paths['output_path']

        mkdir_p(output_path)

        for entry in self.entries:
            entry_fn = entry.entry_id + EXPORT_HTML_EXT
            cur_output_path = pjoin(output_path, entry_fn)

            with open(cur_output_path, 'w') as f:
                print 'writing to', cur_output_path
                f.write(entry.rendered_html.encode('utf-8'))

        # index is just the most recent entry for now
        index_path = pjoin(output_path, 'index' + EXPORT_HTML_EXT)
        if self.entries:
            index_content = self.entries[0].rendered_html
        else:
            index_content = 'No entries yet!'
        with open(index_path, 'w') as f:
            print 'writing to', index_path
            f.write(index_content.encode('utf-8'))

        # atom feed
        atom_path = pjoin(output_path, 'atom.xml')
        with open(atom_path, 'w') as f:
            f.write(self.rendered_feed.encode('utf-8'))

        # copy all directories under the theme path
        for sdn in get_subdirectories(self.theme_path):
            cur_src_dir = pjoin(self.theme_path, sdn)
            cur_dest_dir = pjoin(output_path, sdn)
            print 'copying from', cur_src_dir, 'to', cur_dest_dir
            copytree(cur_src_dir, cur_dest_dir)

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
                self.process(reread=True)
            except KeyboardInterrupt:
                raise
            except Exception:
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

    def publish(self):  # deploy?
        prod_config = self.get_config('prod')
        rsync_cmd = prod_config.get('rsync_cmd', 'rsync')
        if not rsync_cmd.isalpha():
            rsync_cmd = shell_quote(rsync_cmd)
        # TODO: add -e 'ssh -o "NumberOfPasswordPrompts 0"' to fail if
        # ssh keys haven't been set up.
        rsync_flags = prod_config.get('rsync_flags', 'avzP')
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
        self.publish_date = parse(pub_date) if pub_date else DEFAULT_DATE

        self.edit_list = []
        self.last_edit_date = None  # TODO

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
            ret['inline_rendered_content'] = self.inline_rendered_content
        except AttributeError as ae:
            print '---', ae, self.title

        if with_links:
            ret['prev_entries'] = [pe.to_dict() for pe in self.prev_entries]
            ret['next_entries'] = [ne.to_dict() for ne in self.next_entries]

        ret['publish_date_iso8601'] = format_date(self.publish_date)
        if self.last_edit_date:
            ret['update_date_iso8601'] = format_date(self.last_edit_date)
        else:
            ret['update_date_iso8601'] = None
        ret['output_filename'] = ret['entry_id'] + EXPORT_HTML_EXT
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
    return prs


def main():
    prs = get_argparser()
    kwargs = dict(prs.parse_args()._get_kwargs())
    action = kwargs['action']
    if action == 'serve':
        ch = Chert(os.getcwd())
        ch.serve()
    elif action == 'publish':
        ch = Chert(os.getcwd())
        ch.process()
        ch.publish()
    elif action == 'render':
        ch = Chert(os.getcwd())
        ch.process()
    elif action == 'init':
        target_dir = abspath(kwargs['target_dir'])
        if os.path.exists(target_dir):
            raise RuntimeError('chert init failed, path already exists: %s'
                               % target_dir)
        src_dir = pjoin(CUR_PATH, 'scaffold')
        copytree(src_dir, target_dir)
        print 'Created Chert instance in directory: %s' % target_dir
    else:
        raise ValueError('unknown action: %s' % action)

if __name__ == '__main__':
    main()
