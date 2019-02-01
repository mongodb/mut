"""Usage: mut-intersphinx --update=<configpath>
                          [--timeout=<timeout>] [-v|--verbose]
mut-intersphinx --version

-h --help               show this
--update=<configpath>   update
--timeout=<timeout>     wait <timeout> seconds before giving up [default: 5]
-v --verbose            turn on additional debugging messages
--version               show mut version

"""

import base64
import datetime
import email.utils
import http.client
import logging
import os
import posixpath
import urllib.error
import urllib.request
import yaml

import docopt
from . import __version__

MAX_AGE = 60 * 60 * 24 * 1  # One day
logger = logging.getLogger(__name__)


def resolve_path(name: str, url: str) -> str:
    """Transform a URL into a filesystem-safe filename."""
    url_base = posixpath.dirname(url)
    return '.'.join((
        name,
        str(base64.b64encode(bytes(url_base, 'utf-8')), 'utf-8'),
        'inv'))


def update(name: str, url: str, timeout: float) -> None:
    """Update the intersphinx inventory at the given URL, and download
       it into build/<filename>.inv"""
    path = os.path.join('./build', resolve_path(name, url))
    try:
        mtime = os.stat(path).st_mtime
    except FileNotFoundError:
        mtime = -1

    now = datetime.datetime.now().timestamp()

    if now < (mtime + MAX_AGE):
        logger.debug('Still young: %s', url)
        return

    request = urllib.request.Request(url, headers={
        'If-Modified-Since': email.utils.formatdate(mtime)
    })

    try:
        response = urllib.request.urlopen(request, timeout=timeout)
        with open(path, 'wb') as f:
            f.write(response.read())
    except urllib.error.HTTPError as err:
        if err.code == 304:
            logger.debug('Not modified: %s', url)
            return
        logger.error('Error downloading %s: Got %d', url, err.code)
    except (http.client.HTTPException,
            urllib.error.URLError) as err:
        logger.error('Error downloading %s: %s', url, str(err))


def main():
    """Main program entry point."""
    options = docopt.docopt(__doc__)

    if options.get('--version', False):
        print('mut ' + __version__)
        return

    update_path = str(options['--update'])
    timeout = float(options['--timeout'])
    verbose = options.get('--verbose', False)

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Ensure our output directory exists
    try:
        os.mkdir('build')
    except FileExistsError:
        pass

    with open(update_path, 'r') as f:
        for stanza in yaml.safe_load_all(f):
            try:
                name = str(stanza['name'])
                url = str(stanza['url'])
                update(name.strip(), url.strip(), timeout=timeout)
            except KeyError:
                logger.error('Error reading %s: Need both a "name" field and a "url" field',
                             update_path)


if __name__ == '__main__':
    main()
