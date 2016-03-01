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

"""Usage: mut-lint <builddir> [--verbose]

-h --help             show this
--verbose             print more verbose debugging information

"""

import logging

import docopt
import libgiza.git

from typing import Any, Dict

import mut.tuft.driver
import mut.tuft.exts
import mut.tuft.visitors

logger = logging.getLogger(__name__)

EXTLINKS = {
    'hardlink': 'http://docs.mongodb.org/master/{0}',
    'issue': 'https://jira.mongodb.org/browse/{0}',
    'wiki': 'http://www.mongodb.org/display/DOCS/{0}',
    'api': 'https://api.mongodb.org/{0}',
    'manual': 'https://docs.mongodb.org/manual{0}',
    'gettingstarted': 'https://docs.mongodb.org/getting-started{0}',
    'ecosystem': 'https://docs.mongodb.org/ecosystem{0}',
    'meta-driver': 'http://docs.mongodb.org/meta-driver/latest{0}',
    'mms-docs': 'https://docs.cloud.mongodb.com{0}',
    'mms-home': 'https://cloud.mongodb.com{0}',
    'opsmgr': 'https://docs.opsmanager.mongodb.com{0}',
    'about': 'https://www.mongodb.org/about{0}',
    'products': 'https://www.mongodb.com/products{0}'
}


def load_config(path: str) -> Dict[str, Any]:
        config = {}  # type: Dict[str, Any]
        try:
            with open('conf.yaml') as f:
                config = dict(yaml.load(f))
        except FileNotFoundError:
            pass

        return config


def report_links(linter: mut.tuft.visitors.LinkLinter, verbose: bool) -> None:
    for url, ok, references in linter.test_links():
        if ok and verbose:
            logger.info('OK:   %s', url)

        if not ok:
            logger.warn('FAIL: %s', url)
            logger.warn('      %s', ', '.join(references))

def main() -> None:
    options = docopt.docopt(__doc__)

    root = str(options['<builddir>'])
    verbose = bool(options.get('--verbose', False))

    if verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    for name, pattern in EXTLINKS.items():
        mut.tuft.exts.register_extlink(name, pattern)

    config = load_config('conf.yaml')
    driver = mut.tuft.driver.Driver(src_path=root, config=config)

    link_linter = mut.tuft.visitors.LinkLinter()
    code_linter = mut.tuft.visitors.CodeLinter()
    driver.crawl([link_linter, code_linter])

    #report_links(link_linter, verbose)
    code_linter.test_code()


if __name__ == '__main__':
    main()
