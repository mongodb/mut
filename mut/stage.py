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

"""Usage: mut-publish <source> <bucket> --prefix=prefix
                      (--stage|--deploy)
                      [--all-subdirectories]
                      [--redirects=htaccess]
                      [--deployed-url-prefix=prefix]
                      [--redirect-prefix=prefix]...
                      [--dry-run] [--verbose] [--json]
mut-publish --version

-h --help                       show this help message
--prefix=prefix                 the prefix under which to upload in the given bucket
--stage                         apply staging behavior: upload under a prefix
--deploy                        apply deploy behavior: upload into the bucket root

--all-subdirectories            recurse into all subdirectories under <source>.
                                By default, mut-publish will only sync the top-level
                                files, as well as the subdirectory given by the current
                                git branch.

--redirects=htaccess            use the redirects from the given .htaccess file

--redirect-prefix=<re>          regular expression specifying a prefix under which
                                mut-publish may remove redirects. You may provide this
                                option multiple times.

--deployed-url-prefix=prefix    print the full url where files were published to

--json                          print published urls as json
--dry-run                       do not actually do anything
--verbose                       print more verbose debugging information
--version                       show mut version

Environment Variables:
MUT_CACHE_CONTROL               A value for the Cache-Control header to be attached to
                                each file when in deploy mode. If not provided, it
                                uses a set of defaults derived from the Gatsby documentation.
                                Staging always uses no-cache.
"""

import collections
import concurrent.futures
import fnmatch
import functools
import hashlib
import json
import logging
import mimetypes
import os
import posixpath
import re
import sys
import time

import boto3
import boto3.s3.transfer
import botocore
import docopt

from . import AuthenticationInfo
from . import util

from typing import cast, Any, Callable, Dict, List, Set, Tuple, \
    TypeVar, Iterable, Pattern, NamedTuple, Optional

logger = logging.getLogger(__name__)
REDIRECT_PAT = re.compile(r'^Redirect 30[1|2|3] (\S+)\s+(\S+)', re.M)
FileUpdate = NamedTuple('FileUpdate', (('path', str), ('file_hash', str), ('new_file', bool)))
UPLOAD_CHUNK_SIZE = 1024 * 1024 * 8
DELETION_WARNING_THRESHOLD = 10
DELETION_DANGER_THRESHOLD = 350
T = TypeVar('T')


class CacheControl:
    """A manager for cache-control headers. When constructed it takes a list of stanzas,
       each of the type Tuple[List[str], str]: this maps a set of wildcard patterns
       to a cache-control header, following the Python fnmatch rules[1].

       See the DEFAULT_PATTERN for an example.

       [1]: https://docs.python.org/3/library/fnmatch.html
    """
    # Based on https://www.gatsbyjs.com/docs/caching/
    DEFAULT_PATTERN = '''[
        [["*.html", "*/page-data/*.json", "*/sw.js"],
            "public, max-age=0, must-revalidate"
        ],
        [["*"], "public, max-age=28800"]
    ]'''

    def __init__(self, stanzas: List[Tuple[List[str], str]]) -> None:
        self.stanzas: List[Tuple[List[re.Pattern[str]], str]] = [
            ([re.compile(fnmatch.translate(pat)) for pat in stanza[0]], stanza[1]) for stanza in stanzas
        ]

    def __getitem__(self, key: str) -> str:
        """Return a Cache-Control header value for a given key."""
        for patterns, cache_control in self.stanzas:
            if any(pat.match(key) for pat in patterns):
                return cache_control

        return "no-cache"


class Timer:
    def __init__(self, name: str) -> None:
        self.name = name
        self.time = time.perf_counter()

    def lap(self, name: str) -> None:
        """Log the time since the last lap() call or the instance construction."""
        old_time = self.time
        self.time = time.perf_counter()
        logger.info("%s: %s: %ss", self.name, name, self.time - old_time)


class StagingException(Exception):
    """Base class for all giza stage exceptions."""
    pass


class MissingSource(StagingException):
    """An exception indicating that the requested source directory does
       not exist."""
    pass


class SyncFileException(StagingException):
    """An exception indicating an S3 deletion error."""
    def __init__(self, path: str, reason: str) -> None:
        StagingException.__init__(self, 'Error syncing path: {0}'.format(path))
        self.reason = reason
        self.path = path


class SyncException(StagingException):
    """An exception indicating an error uploading files."""
    def __init__(self, errors: List[BaseException]) -> None:
        StagingException.__init__(self, 'Errors syncing data')
        self.errors = errors


def remove_beginning(beginning: str, s: str) -> str:
    return s[len(beginning):] if s.startswith(beginning) else s


def chunks(data: List[T], n: int) -> Iterable[List[T]]:
    """Split a list into chunks of at most length n."""
    for i in range(0, len(data), n):
        yield data[i:(i + n)]


def run_pool(tasks: List[Callable[[None], None]], n_workers: int = 5, retries: int = 1) -> None:
    """Run a list of tasks using a pool of threads."""
    assert retries >= 0

    results = []  # type: List[Tuple[Callable[[None], None], BaseException]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = []

        for task in tasks:
            futures.append(pool.submit(task))

        # Collect erroring tasks and the error which terminanted them. The "or exception" clause
        # satisfies the type checker.
        results = [
            (task, f.exception() or Exception()) for f, task in zip(futures, tasks) if f.exception()
        ]

    if not results:
        return

    if retries == 0:
        raise SyncException([result[1] for result in results])

    run_pool([r[0] for r in results], n_workers, retries-1)


class ChangeSummary:
    def __init__(self) -> None:
        self.suspicious_files = []  # type: List[str]

        self.files_deleted = 0
        self.redirects_deleted = 0
        self.files_modified = 0
        self.files_created = 0
        self.redirects = 0

    @property
    def suspicious(self) -> bool:
        return len(self.suspicious_files) > 0 or self.files_deleted > DELETION_DANGER_THRESHOLD

    def print(self) -> None:
        print('\nSummary\n=======')

        files_deleted_string = 'Files Deleted:     {}'.format(self.files_deleted)
        if self.files_deleted > DELETION_WARNING_THRESHOLD:
            files_deleted_string = util.color(files_deleted_string, ('red', 'bright'))

        for key in self.suspicious_files:
            logger.warn('Suspicious upload: %s', key)

        print(files_deleted_string)
        print('Redirects Deleted: {}'.format(self.redirects_deleted))
        print('Files Modified:    {}'.format(self.files_modified))
        print('Files Created:     {}'.format(self.files_created))
        print('Redirects Created: {}'.format(self.redirects))


class ChangeSet:
    """Stores a list of S3 bucket operations."""
    def __init__(self, verbose: bool, deployed_url_prefix: str) -> None:
        self.verbose = verbose
        self.suspicious_files = []  # type: List[str]
        self.modified_full_urls = []  # type: List[Tuple[str, str]]
        self.deployed_url_prefix = deployed_url_prefix

        self.commands_delete = []  # type: List[Tuple[str, str]]
        self.commands_redirect = []  # type: List[Tuple[str, str]]
        self.commands_upload = []  # type: List[Tuple[str, str, str]]

        self.s3_config = boto3.s3.transfer.TransferConfig(
            multipart_threshold=UPLOAD_CHUNK_SIZE,
            multipart_chunksize=UPLOAD_CHUNK_SIZE)

        self.cache_control = CacheControl([])

    def delete(self, keys: List[str], flag: str = 'D') -> None:
        """Request deletion of a list of keys."""
        for key in keys:
            self.commands_delete.append((flag, key))
            self.modified_full_urls.append((flag, self.deployed_url_prefix + '/' + key))

    def delete_redirects(self, keys: List[str]) -> None:
        """Request deletion of a list of redirects. Behavior is the same as ChangeSet.delete():
           the distinction is informational for ChangeSet.print()."""
        self.delete(keys, flag='DR')

    def upload(self, path: str, key: str, new_file: bool) -> None:
        """Upload a local path into the bucket. new_file is informational for ChangeSet.print()."""
        flag = 'C' if new_file else 'M'
        key = key.lstrip('/')

        if 'master/master' in key:
            self.suspicious_files.append(key)

        # full url with deploy prefix in a separate list from the list of files to actually upload
        self.modified_full_urls.append((flag, self.deployed_url_prefix + '/' + key))

        self.commands_upload.append((flag, path, key))

    def redirect(self, from_key: str, to_url: str) -> None:
        """Create an S3 redirect."""
        from_key = from_key.lstrip('/')
        self.commands_redirect.append((from_key, to_url))

    def print(self, return_json: bool) -> ChangeSummary:
        """Print to stdout all actions that will be taken by ChangeSet.commit()."""
        summary = ChangeSummary()
        summary.suspicious_files = self.suspicious_files

        # convert full urls with deploy prefix to json
        if return_json:
            json_obj = {'urls': []}  # type: Dict[str, List[str]]
            for command in self.modified_full_urls:
                flag, path = command
                json_obj['urls'].append(path)
            print(json.dumps(json_obj))
        else:
            for upload_command in self.commands_upload:
                flag, path, key = upload_command
                if flag == 'C':
                    summary.files_created += 1
                elif flag == 'M':
                    summary.files_modified += 1
                else:
                    raise ValueError('Unknown upload flag {}'.format(repr(flag)))

                print('{}  {}'.format(flag, key))

        if self.verbose:
            for redirect in self.commands_redirect:
                print('R  {} -> {}'.format(redirect[0], redirect[1]))

        for deletion in self.commands_delete:
            flag, key = deletion
            if flag == 'D':
                summary.files_deleted += 1
            elif flag == 'DR':
                summary.redirects_deleted += 1
            else:
                raise ValueError('Unknown deletion flag {}'.format(repr(flag)))

            print('{:<2} {}'.format(flag, key))

        summary.redirects = len(self.commands_redirect)

        if not return_json:
            summary.print()

        return summary

    def commit(self, s3: Any) -> None:
        """Apply the set of operations stored in this instance."""
        changes = set()  # type: Set[str]
        tasks = []
        for command in self.commands_upload:
            _, src_path, key = command
            changes.add(key)
            task = functools.partial(self.__upload, s3, src_path, key)
            tasks.append(cast(Callable[[None], None], task))

        for redirect in self.commands_redirect:
            src, dest = redirect
            changes.add(src)
            task = functools.partial(self.__redirect, s3, src, dest)
            tasks.append(cast(Callable[[None], None], task))

        run_pool(tasks)

        # S3 caps delete requests to 1,000 keys.
        for chunk in chunks(self.commands_delete, 999):
            objects = [{'Key': key} for _, key in chunk if key not in changes]
            if not objects:
                continue
            s3.delete_objects(Delete={
                'Objects': objects,
                'Quiet': True
            })

    def __upload(self, s3: Any, src_path: str, key: str) -> None:
        """Thread worker helper to handle uploading a single file to S3."""
        # Deduce a mimetype and content encoding
        guessed_type, guessed_content_encoding = mimetypes.guess_type(src_path)
        if guessed_type:
            mimetype_headers: Dict[str, str] = {
                'ContentType': guessed_type
            }
            if guessed_content_encoding:
                mimetype_headers['ContentEncoding'] = guessed_content_encoding
        else:
            mimetype_headers = {'ContentType': 'binary/octet-stream'}

        try:
            # Default to 8-hour TTL
            s3.upload_file(src_path, key, ExtraArgs={
                'CacheControl': self.cache_control[key],
                **mimetype_headers
            }, Config=self.s3_config)
            sys.stdout.write('.')
            sys.stdout.flush()
        except botocore.exceptions.ClientError as err:
            raise SyncFileException(src_path, str(err)) from err
        except IOError as err:
            logger.exception('IOError while uploading file "%s": %s', src_path, err)

    def __redirect(self, s3: Any, src: str, dest: str) -> None:
        """Thread worker helper to handle creating a redirect."""
        obj = s3.Object(src)
        try:
            if obj.website_redirect_location == dest:
                logger.debug('Skipping redirect %s', src)
                return
        except botocore.exceptions.ClientError as err:
            if int(err.response['Error']['Code']) != 404:
                logger.exception('S3 error creating redirect from %s to %s', src, dest)

        obj.put(WebsiteRedirectLocation=dest)
        sys.stdout.write('.')
        sys.stdout.flush()


def md5_file(path: str) -> str:
    """Return the S3-style MD5 hash of the given file path as a hex string."""
    parts = []

    # Read the input file in chunks, and add each chunk to the hash state.
    with open(path, 'rb') as input_file:
        while True:
            data = input_file.read(UPLOAD_CHUNK_SIZE)
            if not data:
                break

            hasher = hashlib.md5()
            hasher.update(data)
            parts.append(hasher)

    if len(parts) == 1:
        return parts[0].hexdigest()

    hasher = hashlib.md5()
    for part in parts:
        hasher.update(part.digest())

    return '{}-{}'.format(hasher.hexdigest(), len(parts))


def translate_htaccess(path: str) -> Iterable[Tuple[str, str]]:
    """Read a .htaccess file, and transform redirects into a mapping of redirects."""
    try:
        with open(path, 'r') as f:
            data = f.read()
            for match in REDIRECT_PAT.finditer(data):
                yield (match.group(1), match.group(2))
    except IOError:
        logger.warn('Failed to open %s', path)


class Config:
    """Staging and deployment runtime configuration."""
    def __init__(self, bucket: str, prefix: str) -> None:
        repo = util.git_learn()

        self.builder = 'html'
        self.branch = repo.current_branch
        self.bucket = bucket
        self.prefix = prefix

        self.root_path = repo.top_level
        self.build_path = os.path.join(self.root_path, 'build', self.branch, self.builder)
        self.all_subdirectories = False
        self.redirect_dirs = []  # type: List[Pattern]
        if prefix:
            self.redirect_dirs.append(re.compile(prefix.rstrip('/') + '/'))

        # Path to find the .htaccess file. None indicates to find it under
        # the build root.
        self.redirect_path = None  # type: Optional[str]

        self.verbose = False

        self.deployed_url_prefix = ''

        self._authentication = None  # type: Optional[AuthenticationInfo.AuthenticationInfo]

    @property
    def authentication(self) -> AuthenticationInfo.AuthenticationInfo:
        if not self._authentication:
            self._authentication = AuthenticationInfo.AuthenticationInfo.load()

        return self._authentication


class Path:
    """Wraps Unix-style paths to ensure a normalized format."""
    def __init__(self, init: str) -> None:
        self.segments = init.split('/')

    def replace_prefix(self, orig: str, new: str) -> 'Path':
        """Replace the "orig" string in this path ONLY if it is at the start."""
        cur = str(self)
        if cur.startswith(orig):
            return Path(str(self).replace(orig, new, 1))

        return Path(str(self))

    def ensure_prefix(self, prefix: str) -> 'Path':
        """Prepend a string to this path ONLY if it does not already exist."""
        cur = str(self)
        if cur.startswith(prefix):
            return Path(str(self))

        return Path(posixpath.join(prefix, cur.lstrip('/')))

    def __str__(self) -> str:
        """Format this path as a Unix-style path string."""
        return '/'.join(self.segments)


class StagingCollector:
    """File collector interface that collects a set of paths that need to be
       updated relative to a set of remote S3 objects.

       This file collector ignores the "all_subdirectories" parameter, and
       always uploads everything under the root."""
    def __init__(self, branch: str, all_subdirectories: bool, namespace: str) -> None:
        self.removed_files = []  # type: List[str]
        self.branch = branch
        self.all_subdirectories = all_subdirectories
        self.namespace = namespace

    def get_upload_set(self, root: str) -> Set[str]:
        """Return a list of folder names within which to scan for files."""
        return set(os.listdir(root))

    def collect(self, top_root: str, remote_keys: Iterable[Any]) -> Iterable[FileUpdate]:
        """Yield FileUpdate instances, indicating file paths that must be updated."""
        timer = Timer("collect")
        self.removed_files = []
        remote_hashes = {}
        roots = self.get_upload_set(top_root)

        logger.info('Publishing %s', ', '.join(roots))

        # List all current redirects
        remote_keys = list(remote_keys)
        timer.lap("listed")
        logger.info("%d entries", len(remote_keys))
        for key in remote_keys:
            # Don't register redirects for deletion in this stage
            if key.size == 0:
                continue

            if key.key.startswith('/'):
                logger.warn('Path begins with a /: "%s". This is likely unintentional.', key.key)

            local_key = remove_beginning(self.namespace, key.key).lstrip('/')

            # To process this path, either it must be:
            # - A file or a symlink to a file, or
            # - A directory in our publish set
            local_path = os.path.join(top_root, local_key)
            if not os.path.isfile(local_path) and local_key.split('/', 1)[0] not in roots:
                continue

            # Store its MD5 hash. Might be useless if encryption or multi-part
            # uploads are used.
            remote_hashes[local_key] = key.e_tag.strip('"')

            if not os.path.exists(local_path):
                logger.warn('Removing %s because %s does not exist',
                            key.key, local_path)
                self.removed_files.append(key.key)

        timer.lap("remote set scanned")

        logger.debug('Done. Scanning local filesystem')

        for basedir, dirs, files in os.walk(top_root, followlinks=True):
            # Skip branches we wish not to publish
            if basedir == top_root:
                dirs[:] = [d for d in dirs if d in roots]

            for filename in files:
                # Skip dotfiles
                if filename.startswith('.'):
                    continue

                path = os.path.join(basedir, filename)

                try:
                    local_hash = md5_file(path)
                except IOError:
                    continue

                remote_path = path.replace(top_root, '')
                remote_hash = remote_hashes.get(remote_path, None)
                if remote_hash == local_hash:
                    continue

                is_new_file = remote_hash is None
                yield FileUpdate(path, local_hash, is_new_file)

        timer.lap("filesystem scanned")


class DeployCollector(StagingCollector):
    """A variant of the StagingCollector that, if "all_subdirectories"
       is False, will only recurse into the directry given by "branch"."""
    def get_upload_set(self, root: str) -> Set[str]:
        if self.all_subdirectories:
            return set(os.listdir(root))

        # Special-case the root directory, because we want to publish only:
        # - Files
        # - The current branch (if published)
        # - Symlinks pointing to the current branch
        upload = set()
        for entry in os.listdir(root):
            path = os.path.join(root, entry)
            if os.path.isdir(path) and entry == self.branch:
                # This is the branch we want to upload
                upload.add(entry)
                continue

            # Only collect links that point to the current branch
            try:
                candidate = os.path.basename(os.path.realpath(path))
                if candidate == self.branch:
                    upload.add(entry)
                    continue
            except OSError:
                pass

        return upload


class Staging:
    PAGE_SUFFIX = ''
    Collector = StagingCollector

    def __init__(self, config: Config) -> None:
        self.config = config

        auth = config.authentication
        self.changes = ChangeSet(config.verbose, config.deployed_url_prefix)
        self.s3 = boto3.session.Session(
            aws_access_key_id=auth.access_key,
            aws_secret_access_key=auth.secret_key).resource('s3').Bucket(config.bucket)
        self.collector = self.Collector(
            self.config.branch,
            self.config.all_subdirectories,
            self.namespace)

    @property
    def namespace(self) -> str:
        """Staging places each stage under a unique namespace computed from an
           arbitrary username and branch. This helper returns such a
           namespace, appropriate for constructing a new Staging instance."""
        # The S3 prefix for this staging site
        return '/'.join([x for x in (self.config.prefix,
                                     self.config.authentication.username,
                                     self.config.branch) if x])

    def stage(self, root: str) -> None:
        """Synchronize the build directory with the staging bucket under
           the namespace [username]/[branch]/"""
        timer = Timer("stage")
        htaccess_path = self.config.redirect_path
        if htaccess_path is None:
            htaccess_path = os.path.join(root, '.htaccess')

        redirects = {}  # type: Dict[str, str]
        if self.config.branch == 'master':
            for (src, dest) in translate_htaccess(htaccess_path):
                redirects[self.normalize_key(src)] = dest

        # Ensure that the root ends with a trailing slash to make future
        # manipulations more predictable.
        if not root.endswith('/'):
            root += '/'

        if not os.path.isdir(root):
            raise MissingSource(root)

        # If a redirect is masking a file, we can run into an invalid 404
        # when the redirect is deleted but the file isn't republished.
        # If this is the case, warn and delete the redirect.
        for src, dest in redirects.items():
            src_path = os.path.join(root, src)
            if os.path.isfile(src_path) and \
                    os.path.basename(src_path) in os.listdir(os.path.dirname(src_path)):
                logger.warn('Would ignore redirect that will mask file: %s', src)
#                del redirects[src]

        timer.lap("initial staging setup")

        # Collect files that need to be uploaded
        logger.info("namespace: %s", self.namespace)
        filtered = self.s3.objects.filter(Prefix=self.namespace)
        timer.lap("S3 filter created")
        for entry in self.collector.collect(root, filtered):
            src = entry.path.replace(root, '', 1)

            if not os.path.isfile(entry.path):
                continue

            full_name = '/'.join((self.namespace, src))
            self.changes.upload(os.path.join(root, src), full_name, entry.new_file)

        timer.lap("S3 collection completed")

        # XXX Right now we only sync redirects on master.
        #     Why: Master has the "canonical" .htaccess, and we'd need to attach
        #          metadata to each redirect on S3 to differentiate .htaccess
        #          redirects from symbolic links.
        #     Ramifications: Symbolic link redirects for non-master branches
        #                    will never be published.
        if self.config.branch == 'master':
            self.sync_redirects(redirects)

        timer.lap("Sync redirects")

        # Remove from staging any files that our FileCollector thinks have been
        # deleted locally.
        remove_keys = [str(path.replace_prefix(root, '').ensure_prefix(self.namespace))
                       for path in [Path(p) for p in self.collector.removed_files]]

        if remove_keys:
            self.changes.delete(remove_keys)

        timer.lap("Files removed")

    def sync_redirects(self, redirects: Dict[str, str]) -> None:
        """Upload the given path->url redirect mapping to the remote bucket. In staging
           mode, do nothing."""
        pass

    @classmethod
    def normalize_key(cls, key: str) -> str:
        if os.path.splitext(key)[1] in ('.gz', '.pdf', '.epub', '.html'):
            return key.lstrip('/')

        return key.strip('/') + cls.PAGE_SUFFIX


class DeployStaging(Staging):
    PAGE_SUFFIX = '/index.html'
    Collector = DeployCollector

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        parsed_stanzas = json.loads(os.environ.get('MUT_CACHE_CONTROL', CacheControl.DEFAULT_PATTERN))
        self.changes.cache_control = CacheControl(parsed_stanzas)

    @property
    def namespace(self) -> str:
        return self.config.prefix

    def sync_redirects(self, redirects: Dict[str, str]) -> None:
        """Upload the given path->url redirect mapping to the remote bucket."""

        logger.debug('Finding redirects to remove')
        removed = []
        for entry in self.s3.objects.all():
            # Make sure this is a redirect
            if entry.size != 0:
                continue

            # Redirects are written /foo/bar/index.html or /foo/bar
            redirect_key = self.normalize_key(entry.key)

            # If it doesn't start with our namespace, ignore it
            if not redirect_key.startswith(self.namespace):
                continue

            # If it doesn't match one of our "owned" directories, ignore it
            if not [True for pat in self.config.redirect_dirs if pat.match(redirect_key)]:
                continue

            if redirect_key not in redirects:
                removed.append(entry.key)

        self.changes.delete_redirects(removed)

        for src in redirects:
            self.changes.redirect(self.normalize_key(src), redirects[src])


def do_stage(root: str, staging: Staging) -> None:
    """Drive the main staging process, and print nicer error messages
       for exceptions."""
    try:
        staging.stage(root)
    except MissingSource as err:
        logger.error('No source directory found at %s', str(err))


def main() -> None:
    options = docopt.docopt(__doc__)

    if options.get('--version', False):
        from mut import __version__
        print('mut ' + __version__)
        return

    root = options['<source>']
    bucket = options['<bucket>']
    prefix = options['--prefix']
    deployed_url_prefix = options['--deployed-url-prefix']
    return_json = bool(options.get('--json', False))
    redirect_path = options.get('--redirects', None)
    redirect_prefixes = cast(List[str], options['--redirect-prefix'])
    mode_stage = bool(options.get('--stage', False))
    mode_deploy = bool(options.get('--deploy', False))
    all_subdirectories = bool(options.get('--all-subdirectories', False))
    dry_run = bool(options.get('--dry-run', False))
    verbose = bool(options.get('--verbose', False))

    if verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    config = Config(bucket, prefix)
    config.verbose = verbose
    config.all_subdirectories = all_subdirectories
    config.redirect_path = redirect_path

    if deployed_url_prefix:
        config.deployed_url_prefix = deployed_url_prefix.rstrip('/')

    try:
        config.redirect_dirs += [re.compile(pat) for pat in redirect_prefixes]
    except re.error as err:
        logger.error('Error compiling regular expression: %s', str(err))
        sys.exit(1)

    if mode_stage:
        staging = Staging(config)
    elif mode_deploy:
        staging = DeployStaging(config)

    try:
        do_stage(root, staging)

        summary = staging.changes.print(return_json)

        if summary.suspicious:
            (prompt, confirmation) = (util.color('Commit? (y/n): ', ('red', 'bright')), 'y')
        else:
            (prompt, confirmation) = ('Commit? (y/n): ', 'y')

        if not dry_run:
            if mode_stage:
                staging.changes.commit(staging.s3)
            else:
                if input(prompt) == confirmation:
                    staging.changes.commit(staging.s3)
                else:
                    sys.exit(1)

    except botocore.exceptions.ClientError as err:
        if err.response['ResponseMetadata']['HTTPStatusCode'] == 403:
            logger.error('Failed to upload to S3: Permission denied.')
            logger.info('Check your authentication configuration')
            return

        raise err
    except SyncException as err:
        logger.error('Failed to upload some files:')
        for sub_err in err.errors:
            try:
                raise sub_err from err
            except SyncFileException as sync_err:
                logger.error('%s: %s', sync_err.path, sync_err.reason)


if __name__ == '__main__':
    main()
