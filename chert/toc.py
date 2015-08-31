
"""
Add a Table of Contents to any HTML via cElementTree and friends.

Partially based on an extraction from python-markdown.
"""
import re
#from xml.etree import Element, ElementTree as ET
from HTMLParser import HTMLParser

import html5lib
from boltons.strutils import slugify


def to_unicode(obj):
    try:
        return unicode(obj)
    except UnicodeDecodeError:
        return unicode(obj, encoding='utf8')


class TOCifier(object):
    id_count_re = re.compile(r'^(.*)_([0-9]+)$')
    header_re = re.compile("[Hh][123456]")
    slugify = slugify

    def __init__(self, html, marker, title, base_header_level=1):
        self.raw_html = html
        self.marker = marker
        self.title = title
        self.html = to_unicode(html)
        self.base_header_level = base_header_level

    def run(self):
        self.root = html5lib.parse(self.html)
        self.used_ids = set()

        header_tokens = []
        for el in self.root:
            if not isinstance(el.tag, basestring):
                continue
            h_match = self.header_re.match(el.tag)
            if not h_match:
                continue
            # TODO: tocskip in class
            self.set_header_level(el)

            text = ''.join(el.itertext()).strip()
            if not el.attrib.get('id'):
                slug = self.slugify(text)
                el.attrib['id'] = self.get_unique_id(slug)

            header_tokens.append({'level': int(el.tag[-1]),
                                  'id': el.attrib['id'],
                                  'text': text})
            self.anchorize_header(el)
        import pdb;pdb.set_trace()
        return

    def anchorize_header(self, header_el):
        anchor_el = Element("a")
        anchor_el.text = header_el.text
        anchor_el.attrib["href"] = "#" + header_el.attrib['id']
        anchor_el.attrib["class"] = "toclink"
        header_el.text = ""  # blank the header element
        # transfer all header subelements into the anchor
        for el in header_el:
            anchor_el.append(el)
            header_el.remove(el)
        header_el.append(anchor_el)  # put the anchor into the header
        return

    def set_header_level(self, header_el):
        level = int(header_el.tag[-1]) + self.base_header_level
        if level > 6:
            level = 6
        header_el.tag = 'h%d' % level

    def get_unique_id(self, id_str, used_id_set):
        """ Ensure id is unique in set of ids. Append '_1', '_2'... if not """
        while id_str and id_str in used_id_set:
            match = self.id_count_re.match(id_str)
            if match:
                new_num = int(match.group(2)) + 1
                id_str = '%s_%d' % (match.group(1), new_num)
            else:
                id_str = '%s_%d' % (id_str, 1)
            used_id_set.add(id_str)
        return id_str


class TOCHTMLProcessor(HTMLParser):
    def __init__(self, tocifier):
        self.tocifier = tocifier
        self.cur_h_text = ''
        self.cur_h_level = 0
        self.cur_h_startpos = None
        self.cur_h_endpos = None
        self.cur_h_id = None
        self.h_tokens = []
        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        h_match = self.tocifier.header_re.match(tag)
        if not h_match:
            return
        if self.cur_h_offset:
            raise ValueError('h tags do not nest')


    def handle_data(self, data):
        pass

    def handle_endtag(self, tag):
        pass


def get_used_ids(html):
    ret = set()
    id_parser = HTMLParser()
    id_parser.handle_starttag = lambda _, attrs: ret.add(dict(attrs).get('id'))
    id_parser.feed(html)
    id_parser.close()
    ret.remove(None)
    return ret


class TOCifierNo(object):
    id_count_re = re.compile(r'^(.*)_([0-9]+)$')
    header_re = re.compile("[Hh][123456]")
    slugify = slugify

    def __init__(self, html, marker, title, base_header_level=1):
        self.raw_html = html
        self.marker = marker
        self.title = title
        self.html = to_unicode(html)
        self.base_header_level = base_header_level

    def run(self):
        self.used_ids = get_used_ids(self.html)
        # build tokens
        # text replace

    def get_unique_id(self, id_str, used_id_set):
        """ Ensure id is unique in set of ids. Append '_1', '_2'... if not """
        while id_str and id_str in used_id_set:
            match = self.id_count_re.match(id_str)
            if match:
                new_num = int(match.group(2)) + 1
                id_str = '%s_%d' % (match.group(1), new_num)
            else:
                id_str = '%s_%d' % (id_str, 1)
            used_id_set.add(id_str)
        return id_str


def main():
    html = open('/home/mahmoud/projects/sedimental/site/build_your_own_topic_bot.html').read()
    tocifier = TOCifier(html, '', '')
    tocifier.run()
    #thp = TOCHTMLProcessor(tocifier)
    #thp.feed(html)
    #thp.close()
    #print
    #print thp.id_set
    # ''.join(html5lib.serializer.HTMLSerializer().serialize(html5lib.getTreeWalker('etree')(self.root)))
    return


if __name__ == '__main__':
    main()
