from chert.hypertext import (
    canonicalize_links,
    retarget_links,
    html_text_to_tree,
    html_tree_to_text,
    nest_h_tokens,
)


def test_canonicalize_links_relative():
    text = '<a href="/about">About</a>'
    result = canonicalize_links(text, 'https://example.com', 'index.html')
    assert 'https://example.com/about' in result


def test_canonicalize_links_absolute_unchanged():
    text = '<a href="https://other.com/page">Other</a>'
    result = canonicalize_links(text, 'https://example.com', 'index.html')
    assert 'https://other.com/page' in result


def test_canonicalize_links_anchor():
    text = '<a href="#section">Section</a>'
    result = canonicalize_links(text, 'https://example.com', 'page.html')
    assert 'https://example.com/page.html#section' in result


def test_retarget_links_external():
    html = '<html><body><a href="https://external.com">Link</a></body></html>'
    tree = html_text_to_tree(html)
    retarget_links(tree, mode='external')
    text = html_tree_to_text(tree)
    assert 'target="_blank"' in text
    assert 'rel="noopener"' in text


def test_retarget_links_none():
    html = '<html><body><a href="https://external.com">Link</a></body></html>'
    tree = html_text_to_tree(html)
    retarget_links(tree, mode='none')
    text = html_tree_to_text(tree)
    assert 'target=' not in text


def test_html_roundtrip():
    html = '<html><head></head><body><p>Hello</p></body></html>'
    tree = html_text_to_tree(html)
    text = html_tree_to_text(tree)
    assert '<p>' in text
    assert 'Hello' in text


def test_nest_h_tokens_empty():
    assert nest_h_tokens([]) == []


def test_nest_h_tokens_flat():
    tokens = [{'level': 1, 'id': 'a', 'text': 'A'},
              {'level': 1, 'id': 'b', 'text': 'B'}]
    result = nest_h_tokens(tokens)
    assert len(result) == 2
    assert result[0]['children'] == []
    assert result[1]['children'] == []


def test_nest_h_tokens_nested():
    tokens = [{'level': 1, 'id': 'a', 'text': 'A'},
              {'level': 2, 'id': 'b', 'text': 'B'}]
    result = nest_h_tokens(tokens)
    assert len(result) == 1
    assert len(result[0]['children']) == 1
    assert result[0]['children'][0]['id'] == 'b'
