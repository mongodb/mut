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

"""Usage: mut-lint <builddir> (--linters=<linter>|--all) [--verbose]
mut-lint --version

-h --help               show this
--all                   run all linter passes
--linters=<linter>      comma-separated list of linter passes to run
--verbose               print more verbose debugging information
--version               show mut version

Available Linters:
  links
  code

"""

import logging
import sys

import docopt
import libgiza.git

from typing import Any, Dict

import mut.tuft
import mut.tuft.visitors

logger = logging.getLogger(__name__)


def report_links(linter: mut.tuft.visitors.LinkLinter, verbose: bool) -> None:
    for url, ok, references in linter.test_links():
        if ok and verbose:
            logger.info('OK:   %s', url)

        if not ok:
            logger.warn('FAIL: %s', url)
            logger.warn('      %s', ', '.join(set(references)))


def main() -> None:
    options = docopt.docopt(__doc__)

    if options.get('--version', False):
        import mut
        print('mut ' + mut.__version__)
        return

    root = str(options['<builddir>'])
    verbose = bool(options.get('--verbose', False))
    all_linters = bool(options.get('--all', False))
    linters = str(options.get('--linters', '')).split(',')

    if verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    unknown_linters = [l for l in linters if l not in ['links', 'code']]
    if unknown_linters:
        logger.error('Unknown linters: %s', ','.join(unknown_linters))
        sys.exit(1)

    link_linter = mut.tuft.visitors.LinkLinter()
    code_linter = mut.tuft.visitors.CodeLinter()

    logger.info('Starting analysis...')
    mut.tuft.build(root, [link_linter, code_linter], None)

    if all_linters or 'links' in linters:
        report_links(link_linter, verbose)

    if all_linters or 'code' in linters:
        logger.info('Testing code')
        code_linter.test_code()


if __name__ == '__main__':
    main()
