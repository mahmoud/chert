import os
import sys
from os.path import dirname
import subprocess

import pytest


@pytest.fixture(scope="function")
def chert_site_path(tmp_path):
    """Create a test site directory and initialize chert."""
    ret = tmp_path / 'test_site'
    os.chdir(str(tmp_path))
    subprocess.run(['chert', 'init', str(ret)], check=True)
    return ret


def test_init_dirs_exist(chert_site_path):
    assert (chert_site_path / 'entries').is_dir()


@pytest.fixture(scope="function")
def chert_render_path(chert_site_path):
    """Render the test site and return the output directory."""
    os.chdir(str(chert_site_path))
    subprocess.run(['chert', 'render'], check=True)
    return chert_site_path / 'site'


def test_render_assets_exist(chert_render_path):
    assert chert_render_path.is_dir()
