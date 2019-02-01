# Copyright 2015 MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Bake fonts into SVG files using Inkscape, then minify them using svgo.
Inputs all SVG files "foo.svg" under the root recursively, and outputs
each file as "foo.bakedsvg.svg".

Usage:
  mut-images [<root>]
  mut-images --version

-h --help           show this
--version           show mut version
"""

import concurrent.futures
import logging
import multiprocessing
import os
import subprocess
import tempfile
from typing import List

import docopt

from . import __version__
from . import util

logger = logging.getLogger(__name__)


def generate_svg(input_path: str, output_path: str) -> None:
    """Clean up and minify a SVG file."""
    logger.info('Generating %s', output_path)
    inkscape = None
    for path in ('/Applications/Inkscape.app/Contents/Resources/bin/inkscape',):
        if os.path.isfile(path):
            inkscape = path
            break

    if not inkscape:
        inkscape = 'inkscape'

    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)
    with tempfile.NamedTemporaryFile() as tmp:
        subprocess.check_call([inkscape,
                               input_path,
                               '--vacuum-defs',
                               '--export-text-to-path',
                               '--export-area-drawing',
                               '--export-plain-svg', tmp.name],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)

        subprocess.check_call(['svgo',
                               '-q',
                               '--multipass',
                               '-p', '1',
                               '--enable=removeTitle',
                               '--enable=removeViewBox',
                               '-i', tmp.name,
                               '-o', output_path])


def main() -> None:
    options = docopt.docopt(__doc__)
    if options.get('--version', False):
        print('mut ' + __version__)
        return

    root = str(options['<root>'] or '.')
    logging.basicConfig(level=logging.INFO)

    paths = []  # type: List[str]
    if os.path.isfile(root):
        paths.append(root)
    else:
        for root, dirs, files in os.walk(root):
            for filename in files:
                components = os.path.splitext(filename)
                if len(components) < 2 or components[1] != '.svg':
                    continue

                if components[0].endswith('.bakedsvg'):
                    continue

                paths.append(os.path.join(root, filename))

    logger.info('Build Images: %d', len(paths))

    n_workers = multiprocessing.cpu_count()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = []

        for path in paths:
            bare_path, _ = os.path.splitext(path)
            output_filename = bare_path + '.bakedsvg.svg'
            if not util.compare_mtimes(output_filename, [path]):
                continue

            futures.append(pool.submit(
                generate_svg,
                path,
                output_filename))

        for f in futures:
            exception = f.exception()
            if exception:
                logger.error(str(exception))


if __name__ == '__main__':
    main()
