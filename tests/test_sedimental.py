import os

import pytest
import shutil

from chert.core import Site

SEDIMENTAL_PATH = '/home/mahmoud/projects/sedimental'


@pytest.fixture(scope='module')
def sedimental_render(tmp_path_factory):
    """Render sedimental into a temp directory."""
    if not os.path.isdir(SEDIMENTAL_PATH):
        pytest.skip('sedimental source not available')
    tmp = tmp_path_factory.mktemp('sedimental')
    src = tmp / 'sedimental'
    shutil.copytree(SEDIMENTAL_PATH, src,
                    ignore=shutil.ignore_patterns('site', '.git', '__pycache__'))
    site = Site(str(src))
    site.process()
    return src / 'site'


@pytest.mark.acceptance
def test_sedimental_render_structure(sedimental_render):
    site = sedimental_render
    assert site.is_dir()
    assert (site / 'index.html').is_file()
    assert (site / 'archive.html').is_file()
    assert (site / 'atom.xml').is_file()
    assert (site / 'rss.xml').is_file()
    assert (site / 'about.html').is_file()


@pytest.mark.acceptance
def test_sedimental_about_content(sedimental_render):
    about = (sedimental_render / 'about.html').read_text()
    assert 'Mahmoud Hashemi' in about
    assert 'Sedimental' in about
