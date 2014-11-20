# -*- coding: utf-8 -*-

import re

ATOM_TMPL = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:thr="http://purl.org/syndication/thread/1.0" xml:lang="en">
  <title type="text">{site.title}</title>
  <subtitle type="text">{site.description}</subtitle>
  <updated></updated>
  <id>{site.canonical_url}</id>
  <link rel="alternate" type="text/html" href="{site.canonical_url}" />
  <link rel="self" type="application/atom+xml" href="{site.feed_url}" />
  <updated>{site.last_updated}</updated>
  <generator uri="https://github.com/mahmoud/chert">Chert</generator>
  {#entries}
  <entry>
    <author><name>{.author_name}</name></author>
    <title>{.title}</title>
    <link rel="alternate" type="text/html" href="" />
    <published></published>
    <updated></updated>
    <content type="xhtml">
      <div xmlns="http://www.w3.org/1999/xhtml">
        {.inline_rendered_content}
      </div>
    </content>
  </entry>
  {/entries}
</feed>
"""


_link_re = re.compile("((?P<attribute>src|href)=\"/)")


def absolutify(text, base):
    return _link_re.sub(r'\g<attribute>="' + base + '/', text)
