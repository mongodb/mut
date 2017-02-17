"""
Generates per-build "buildinfo" artifacts that access to build-time data,
including the release.txt file that has the hash that reflects the version of
the source reflected in a build, as well as content useable in the includes
directory so that you can reference the commit in the documentation text.
"""

import logging
import os

from typing import List
import rstcloth.rstcloth

import mut.config

PREFIXES = []  # type: List[str]

logger = logging.getLogger(__name__)


def generate_hash_file(config: mut.config.RootConfig) -> None:
    filename = os.path.join(config.output_source_path,
                            'includes',
                            'hash.rst')

    cloth = rstcloth.rstcloth.RstCloth()

    if os.path.exists(filename):
        with open(filename, 'r') as f:
            existing = f.read()
    else:
        existing = []

    commit = config.commit
    cloth.directive('|commit| replace', '``{0}``'.format(commit))

    try:
        if cloth.data == existing[:-1]:
            logger.info('no new commit(s), not updating {0} ({1})'.format(filename, commit[:10]))
    except TypeError:
        logger.warning('problem generating {0}, continuing'.format(filename))
        if os.path.exists(filename):
            os.utime(filename, None)
        else:
            with open(filename, 'a'):
                os.utime(filename, None)
    else:
        cloth.write(filename)


def generate_release_file(config: mut.config.RootConfig) -> None:
    filename = os.path.join(config.output_path,
                            'html',
                            'release.txt')

    release_root = os.path.dirname(filename)
    if not os.path.exists(release_root):
        os.makedirs(release_root)

    with open(filename, 'w') as f:
        f.write(config.commit)


def run(root_config: mut.config.RootConfig, paths: List[str]):
    logger.info('Hash')
    generate_hash_file(root_config)
    generate_release_file(root_config)
