# -*- coding: utf-8 -*-

import io
import re
import os
import hashlib
from os.path import abspath, splitext, join as pjoin

import yaml
from boltons.dictutils import OrderedMultiDict as OMD


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
ENTRY_EXTS = ('md',)
PREV_ENTRY_COUNT = 5
LENGTH_BOUNDARIES = [(0, 'short'),
                     (100, 'long'),
                     (1000, 'manifesto')]

import string
_punct_re = re.compile('[%s]+' % re.escape(string.punctuation))


class Chert(object):
    def __init__(self, entries=None):
        self.entries = entries or []

    def validate(self):
        dup_id_map = {}
        eid_map = OMD([(e.entry_id, e) for e in self.entries])
        for eid in eid_map:
            elist = eid_map.getlist(eid)
            if len(elist) > 1:
                dup_id_map[eid] = elist

        if dup_id_map:
            raise ValueError('duplicate entry IDs detected: %r' % dup_id_map)

    def render(self):
        pass

    def process_entries(self):
        entry_count = len(self.entries)
        std_pub_entries = [e for e in self.entries
                           if not e.is_special and not e.is_draft]
        for i, entry in enumerate(self.std_pub_entries, start=1):
            start_prev = max(0, i - PREV_ENTRY_COUNT)
            entry.prev_entries = std_pub_entries[start_prev:i][::-1]
            if i == 1:
                entry.prev_entry = None
            else:
                entry.prev_entry = std_pub_entries[i]
            if i == entry_count:
                entry.next_entry = None
            else:
                entry.next_entry = std_pub_entries[i]

    @classmethod
    def from_path(cls, input_path):
        entries_path = abspath(pjoin(input_path, 'entries'))
        entry_paths = []
        for root, dirs, filenames in os.walk(entries_path):
            for filename in filenames:
                _, ext = splitext(filename)
                if ext[1:] in ENTRY_EXTS:
                    entry_paths.append(pjoin(root, filename))
        entries = [Entry.from_path(ep) for ep in entry_paths]
        print entries
        return cls(entries=entries)


class Entry(object):
    def __init__(self, title=None, content=None):
        self.title = title
        self.content = content or ''
        self.is_draft = None
        self.publish_date = None
        self.last_edit_date = None or self.publish_date
        self.edit_list = []

        self.layout = None
        hash_content = (self.title + self.content).encode('utf-8')
        self.entry_hash = hashlib.sha256(hash_content).hexdigest()
        self.input_path = None

        no_punct = _punct_re.sub('', self.content)
        print ' '.join(no_punct.split())
        self.word_count = len(no_punct.split())

    @classmethod
    def from_dict(cls, in_dict):
        ret = cls(title=in_dict['title'],
                  content=in_dict['content'])
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


_docstart_re = re.compile(b'^---\r?\n')
PAGE_ENCODING = 'utf-8'


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
        text_content = fd.read().decode(PAGE_ENCODING)
        return yaml_dict, text_content


if __name__ == '__main__':
    ch = Chert.from_path('scaffold')
