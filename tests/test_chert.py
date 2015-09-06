
import os
import sys
from os.path import dirname

import py
import pytest

EXPECTED_VIRTUALENV = 'chert-tests'


def test_virtualenv():
    assert getattr(sys, 'real_prefix', None), 'virtualenv not active'

    virtualenv_name = os.path.split(dirname(dirname(sys.executable)))[-1]
    #assert virtualenv_name == EXPECTED_VIRTUALENV  # TODO: addoption


@pytest.fixture
def chert_site_path(tmpdir):
    ret = tmpdir.join('test_site')
    os.chdir(str(tmpdir))
    py.process.cmdexec('chert init %s' % ret)
    return ret


def test_init_dirs_exist(chert_site_path):
    assert chert_site_path.join('entries').isdir()


@pytest.fixture
def chert_render_path(chert_site_path):
    os.chdir(str(chert_site_path))
    py.process.cmdexec('chert render')
    return chert_site_path.join('site')


def test_render_assets_exist(chert_render_path):
    assert chert_render_path.isdir()
