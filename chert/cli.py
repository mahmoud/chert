
from __future__ import print_function
import os
from os.path import abspath, dirname, join as pjoin
import shutil

from face import Command, Flag, face_middleware
from boltons.fileutils import mkdir_p, copytree, iter_find_files

from chert.log import chert_log as chlog
from chert.core import Site, __version__

CUR_PATH = dirname(abspath(__file__))
DEFAULT_CONFIG_FILENAME = 'chert.yaml'


def find_chert_dir(start_dir, config_filename=DEFAULT_CONFIG_FILENAME):
    prev_dir = None
    cur_dir = abspath(start_dir)
    while prev_dir != cur_dir:
        if os.path.isfile(pjoin(cur_dir, config_filename)):
            break
        prev_dir = cur_dir
        cur_dir = dirname(cur_dir)
    else:
        raise ValueError('expected current or parent directories to'
                         ' contain a Chert config file (chert.yaml),'
                         ' not found in: %s' % start_dir)
    return cur_dir



@chlog.wrap('critical')
def init(target_dir):
    'create a new Chert site'
    target_dir = abspath(target_dir)
    if os.path.exists(target_dir):
        raise RuntimeError('chert init failed, path already exists: %s'
                           % target_dir)
    src_dir = pjoin(CUR_PATH, 'scaffold')
    copytree(src_dir, target_dir)
    print('Created Chert instance in directory: %s' % target_dir)


@face_middleware(provides=['input_path'], optional=True)
def _cur_input_path_mw(next_):
    input_path = find_chert_dir(os.getcwd())
    return next_(input_path=input_path)


def serve(input_path):
    'work on a Chert site using the local server'
    ch = Site(input_path, dev_mode=True)
    ch.serve()


@chlog.wrap('critical')
def render(input_path):
    'generate a local copy of the site'
    ch = Site(input_path)
    ch.process()


@chlog.wrap('critical', inject_as='_act')
def publish(input_path, _act):
    'upload a Chert site to the remote server'
    ch = Site(input_path)
    ch.process()
    success = ch.publish()
    if success:
        _act.success()
    else:
        _act.failure()


def delete_dir_contents(path):
    for entry in os.listdir(path):
        cur_path = pjoin(path, entry)
        if os.path.isfile(cur_path) or os.path.islink(cur_path):
            os.unlink(cur_path)
        elif os.path.isdir(cur_path):
            shutil.rmtree(cur_path)
    return


@chlog.wrap('critical')
def clean(input_path):
    'clean Chert output site directory'
    ch = Site(input_path)
    delete_dir_contents(ch.output_path)
    print('Cleaned Chert output path: %s' % ch.output_path)


def version():
    'display the version and other metadata'
    print('chert version %s' % __version__)
    print('  located at: %s' % os.path.abspath(os.path.dirname(__file__)))



def main():
    cmd = Command(name='chert', func=None)

    cmd.add(init, posargs={'count': 1, 'name': 'target_dir'})
    cmd.add(serve)
    cmd.add(render)
    cmd.add(publish)
    cmd.add(clean)
    cmd.add(version)

    # cmd.add('--target-dir', doc='path to generate new chert site')

    cmd.add(_cur_input_path_mw)
    cmd.run()
