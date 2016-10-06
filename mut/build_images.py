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

"""Usage: mut-images [--edition=<edition>]

-h --help           - show this
--edition <edition> - specify the project edition to build.

"""

import logging
import multiprocessing

import docopt

from typing import Any, Dict

import mut
import mut.main
import mut.images

logger = logging.getLogger(__name__)


def main():
    options = docopt.docopt(__doc__)
    edition = str(options['--edition'] or '')
    logging.basicConfig(level=logging.INFO)

    config = mut.RootConfig('.', edition)
    config.n_workers = multiprocessing.cpu_count()

    collector = mut.main.FileCollector()
    collector.walk(config.source_path, ['images'])
    mut.images.run_build_images(config, collector.get_prefixes(['images']))

if __name__ == '__main__':
    main()
