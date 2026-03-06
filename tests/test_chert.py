import pytest

from chert.cli import init
from chert.core import Site


@pytest.fixture(scope="function")
def chert_site_path(tmp_path):
    """Create a test site directory and initialize chert."""
    ret = tmp_path / 'test_site'
    init(target_dir=str(ret))
    return ret


def test_init_dirs_exist(chert_site_path):
    assert (chert_site_path / 'entries').is_dir()
    assert (chert_site_path / 'themes').is_dir()
    assert (chert_site_path / 'chert.yaml').is_file()
    assert (chert_site_path / 'custom.py').is_file()


@pytest.fixture(scope="function")
def chert_render_path(chert_site_path):
    """Render the test site and return the output directory."""
    site = Site(str(chert_site_path))
    site.process()
    return chert_site_path / 'site'


def test_render_assets_exist(chert_render_path):
    assert chert_render_path.is_dir()
    assert (chert_render_path / 'index.html').is_file()
