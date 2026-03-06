import sys
import subprocess

import pytest


CHERT_CMD = [sys.executable, '-m', 'chert']


@pytest.fixture(scope="function")
def chert_site_path(tmp_path, monkeypatch):
    """Create a test site directory and initialize chert."""
    ret = tmp_path / 'test_site'
    monkeypatch.chdir(tmp_path)
    subprocess.run([*CHERT_CMD, 'init', str(ret)], check=True)
    return ret


def test_init_dirs_exist(chert_site_path):
    assert (chert_site_path / 'entries').is_dir()


@pytest.fixture(scope="function")
def chert_render_path(chert_site_path, monkeypatch):
    """Render the test site and return the output directory."""
    monkeypatch.chdir(chert_site_path)
    subprocess.run([*CHERT_CMD, 'render'], check=True)
    return chert_site_path / 'site'


def test_render_assets_exist(chert_render_path):
    assert chert_render_path.is_dir()
