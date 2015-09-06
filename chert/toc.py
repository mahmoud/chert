# -*- coding: utf-8 -*-
"""Add a Table of Contents to any HTML via cElementTree and friends.

Largely based on an extraction from python-markdown, but can be run on
bare HTML (not a python-markdown-based ElementTree).
"""
import re
from xml.etree import cElementTree as ET

import html5lib
from boltons.strutils import slugify


def to_unicode(obj):
    try:
        return unicode(obj)
    except UnicodeDecodeError:
        return unicode(obj, encoding='utf8')


def remove_marker(text, marker='[TOC]'):
    return text.replace(marker, '', 1)


def add_toc(html, marker='[TOC]', title='Contents', base_header_level=1):
    """Adds a table of contents div where *marker* can be found within p
    tags on its own. Turns headings into links and optionally adjusts
    their level to be suitable for inclusion in a larger document.

    Input can be text or utf-8 bytes, but the return is text (aka a
    unicode object).

    Intended to be used on the "content" (part below the post title)
    of the HTML layout of an entry.
    """
    tocifier = TOCifier(html=html,
                        marker=marker,
                        title=title,
                        base_header_level=base_header_level)
    tocifier.process()
    html_text = tocifier.get_html_text()
    return html_text


class TOCifier(object):
    id_count_re = re.compile(r'^(.*)_([0-9]+)$')
    header_re = re.compile("[Hh][123456]")

    def __init__(self, html, marker, title, base_header_level=1):
        self.raw_html = html
        self.marker = marker
        self.title = title
        self.html = to_unicode(html)
        self.base_header_level = base_header_level
        self.slugify = slugify

    def process(self):
        self.root = html5lib.parse(self.html, namespaceHTMLElements=False)
        self.used_id_set = set()

        h_tokens = []
        for el in self.root.iter():
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

            h_tokens.append({'level': int(el.tag[-1]),
                             'id': el.attrib['id'],
                             'text': text})
            self.anchorize_header(el)
        h_token_tree = nest_h_tokens(h_tokens)
        toc_div_el = self.build_toc_div(h_token_tree)
        if self.marker:
            self.replace_marker(toc_div_el)
        return

    def get_html_text(self):
        options = {'quote_attr_values': True,
                   'use_trailing_solidus': True,
                   'space_before_trailing_solidus': True}
        serializer = html5lib.serializer.HTMLSerializer(**options)
        walker = html5lib.getTreeWalker('etree')
        stream = serializer.serialize(walker(self.root))
        return u''.join(stream)

    def replace_marker(self, elem):
        ''' Replace marker with elem. '''
        pc_pairs = ((parent, child)
                    for parent in self.root.iter()
                    for child in parent)
        for (p, c) in pc_pairs:
            if not isinstance(c.tag, basestring):
                continue
            if c.tag in ('pre', 'code'):
                continue
            if self.header_re.match(c.tag):
                continue
            text = ''.join(c.itertext()).strip()
            if not text:
                continue

            # To keep the output from screwing up the
            # validation by putting a <div> inside of a <p>
            # we actually replace the <p> in its entirety.
            # We do not allow the marker inside a header as that
            # would causes an enless loop of placing a new TOC
            # inside previously generated TOC.
            if c.text and c.text.strip() == self.marker:
                for i in range(len(p)):
                    if p[i] == c:
                        p[i] = elem
                        # add TOC a maximum of once
                        return

        # no marker found
        return

    def build_toc_div(self, h_token_tree):
        """ Return a string div given a toc list. """
        div_el = ET.Element("div")
        div_el.attrib["class"] = "toc"

        # Add title to the div
        if self.title:
            title_el = ET.SubElement(div_el, "span")
            title_el.attrib["class"] = "toctitle"
            title_el.text = self.title

        def build_etree_ul(toc_list, parent):
            ul = ET.SubElement(parent, "ul")
            for item in toc_list:
                # List item link, to be inserted into the toc div
                li = ET.SubElement(ul, "li")
                link = ET.SubElement(li, "a")
                link.text = item.get('text', '')
                link.attrib["href"] = '#' + item.get('id', '')
                if item['children']:
                    build_etree_ul(item['children'], li)
            return ul

        build_etree_ul(h_token_tree, div_el)
        return div_el

    def anchorize_header(self, header_el):
        anchor_el = ET.Element("a")
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

    def get_unique_id(self, id_str):
        """ Ensure id is unique in set of ids. Append '_1', '_2'... if not """
        used_id_set = self.used_id_set
        while id_str and id_str in used_id_set:
            match = self.id_count_re.match(id_str)
            if match:
                new_num = int(match.group(2)) + 1
                id_str = '%s_%d' % (match.group(1), new_num)
            else:
                id_str = '%s_%d' % (id_str, 1)
            used_id_set.add(id_str)
        return id_str


def nest_h_tokens(h_tokens):
    """Given an unsorted list with errors and skips, return a nested one.
    [{'level': 1}, {'level': 2}]
    =>
    [{'level': 1, 'children': [{'level': 2, 'children': []}]}]

    A wrong list is also converted:
    [{'level': 2}, {'level': 1}]
    =>
    [{'level': 2, 'children': []}, {'level': 1, 'children': []}]
    """
    toc_list = list(h_tokens)
    ordered_list = []
    if not toc_list:
        return ordered_list

    # Initialize everything by processing the first entry
    last = toc_list.pop(0)
    last['children'] = []
    levels = [last['level']]
    ordered_list.append(last)
    parents = []

    # Walk the rest nesting the entries properly
    while toc_list:
        t = toc_list.pop(0)
        current_level = t['level']
        t['children'] = []

        # Reduce depth if current level < last item's level
        if current_level < levels[-1]:
            # Pop last level since we know we are less than it
            levels.pop()

            # Pop parents and levels we are less than or equal to
            to_pop = 0
            for p in reversed(parents):
                if current_level <= p['level']:
                    to_pop += 1
                else:  # pragma: no cover
                    break
            if to_pop:
                levels = levels[:-to_pop]
                parents = parents[:-to_pop]

            # Note current level as last
            levels.append(current_level)

        # Level is the same, so append to
        # the current parent (if available)
        if current_level == levels[-1]:
            (parents[-1]['children'] if parents
             else ordered_list).append(t)

        # Current level is > last item's level,
        # So make last item a parent and append current as child
        else:
            last['children'].append(t)
            parents.append(last)
            levels.append(current_level)
        last = t

    return ordered_list


def main():
    raw_html = open('/home/mahmoud/projects/sedimental/site/podcasts.html').read()
    html = raw_html[raw_html.index('<body>'):raw_html.index('</body>') + 7]
    print add_toc(html).encode('utf-8')
    return


if __name__ == '__main__':
    main()
