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

"""Usage: mut-publish <source> <bucket>
                 --prefix=prefix
                 (--stage|--deploy|--destage)
                 [--all-subdirectories]
                 [--redirects=htaccess]
                 [--redirect-prefixes=prefixes]...
                 [--dry-run] [--verbose]

-h --help               show this help message

--prefix=prefix         the prefix under which to upload in the given bucket

--stage                 apply staging behavior: upload under a prefix

--deploy                apply deploy behavior: upload into the bucket root

--destage               remove all staged files

--all-subdirectories    recurse into all subdirectories under <source>.
                        By default, mut-publish will only sync the top-level
                        files, as well as the subdirectory given by the current
                        git branch.

--redirects=htaccess    use the redirects from the given .htaccess file

--redirect-prefix=<re>  regular expression specifying a prefix under which
                        mut-publish may remove redirects. You may provide this
                        option multiple times.

--dry-run               do not actually do anything

--verbose               print more verbose debugging information
"""

import collections
import concurrent.futures
import configparser
import functools
import hashlib
import logging
import os
import os.path
import re
import stat
import sys

import boto.s3.bucket
import boto.s3.connection
import boto.s3.key
import docopt
import libgiza.git

from typing import cast, Callable, Dict, List, Set, Tuple, Pattern

logger = logging.getLogger(__name__)
REDIRECT_PAT = re.compile('^Redirect 30[1|2|3] (\S+)\s+(\S+)', re.M)
FileUpdate = collections.namedtuple('FileUpdate', ['path', 'file_hash'])

CONFIG_PATH = '~/.config/giza-aws-authentication.conf'
SAMPLE_CONFIG = '''[authentication]
accesskey=<AWS access key>
secretkey=<AWS secret key>
'''


class AuthenticationInfo:
    """Stores S3 authentication information."""
    def __init__(self, access_key: str, secret_key: str, username: str) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.username = username


class Config:
    """Staging and deployment runtime configuration."""
    def __init__(self, bucket: str, prefix: str) -> None:
        repo = libgiza.git.GitRepo()
        self.builder = 'html'
        self.branch = repo.current_branch()
        self.bucket = bucket
        self.prefix = prefix

        self.root_path = repo.top_level()
        self.build_path = os.path.join(self.root_path, 'build', self.branch, self.builder)
        self.all_subdirectories = False
        self.redirect_dirs = []  # type: List[Pattern]

        if prefix:
            self.redirect_dirs.append(re.compile(prefix))

        self.verbose = False

        self._authentication = None  # type: AuthenticationInfo

    @property
    def authentication(self) -> AuthenticationInfo:
        """Returns an AuthenticationInfo instance giving any necessary S3 login
           information."""
        if self._authentication:
            return self._authentication

        cfg_path = os.path.expanduser(CONFIG_PATH)
        cfg = configparser.ConfigParser()
        cfg.read(cfg_path)

        # Warn the user if config permissions are too lax
        try:
            if os.name == 'posix' and stat.S_IMODE(os.stat(cfg_path).st_mode) != 0o600:
                logger.warn('Your AWS authentication file is poorly protected! You should run')
                logger.warn('    chmod 600 %s', cfg_path)
        except OSError:
            pass

        # Load S3 authentication information
        try:
            access_key = cfg.get('authentication', 'accesskey')
            secret_key = cfg.get('authentication', 'secretkey')
        except (configparser.NoSectionError, configparser.NoOptionError):
            print('No staging authentication found. Create a file at {0} with '
                  'contents like the following:\n'.format(cfg_path))
            print(SAMPLE_CONFIG)
            create_config_framework(cfg_path)
            raise ValueError('Missing authentication information')

        # Get the user's preferred name; we use this as part of our S3 namespaces
        try:
            username = cfg.get('personal', 'username')
        except (configparser.NoSectionError, configparser.NoOptionError):
            username = os.getlogin()

        self._authentication = AuthenticationInfo(access_key, secret_key, username)
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

        return Path('/'.join((prefix, cur)))

    def __str__(self) -> str:
        """Format this path as a Unix-style path string."""
        return '/'.join(self.segments)


class BulletProofS3:
    """An S3 API that wraps boto to work around Amazon's 100-request limit."""
    THRESHOLD = 20

    def __init__(self, access_key: str, secret_key: str, bucket_name: str) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.name = bucket_name

        # For "dry" runs; only pretend to do anything.
        self.dry_run = False

        self.times_used = 0
        self._conn = None  # type: boto.s3.bucket.Bucket

    def get_connection(self) -> boto.s3.connection.S3Connection:
        """Return a connection to S3. Not idempotent: will create a new connection
           after some number of calls."""
        if not self._conn or self.times_used > self.THRESHOLD:
            conn = boto.s3.connection.S3Connection(self.access_key, self.secret_key)
            self._conn = conn.get_bucket(self.name)
            self.times_used = 0

        self.times_used += 1
        return self._conn

    def list(self, prefix: str=None) -> boto.s3.bucketlistresultset.BucketListResultSet:
        """Returns a list of keys in this S3 bucket."""
        return self.get_connection().list(prefix=prefix)

    def get_redirect(self, name: str) -> str:
        """Return the destination redirect associated with a given source path."""
        k = boto.s3.key.Key(self.get_connection(), name)
        return k.get_redirect()

    def set_redirect(self, key: boto.s3.key.Key, dest: str) -> None:
        """Redirect a given key to a destination."""
        if not self.dry_run:
            key.set_redirect(dest)

    def delete_keys(self, keys: boto.s3.key.Key) -> boto.s3.multidelete.MultiDeleteResult:
        """Delete the given list of keys."""
        if self.dry_run:
            keys = []

        return self.get_connection().delete_keys(keys)

    def copy(self, src_path: str, dest_name: str, **options) -> None:
        """Copy a given key to the given path."""
        if self.dry_run:
            return

        key = boto.s3.key.Key(self.get_connection())
        key.key = src_path
        key.copy(self.name, dest_name, **options)

    def upload_path(self, src: str, dest: str, **options) -> boto.s3.key.Key:
        key = boto.s3.key.Key(self.get_connection())
        key.key = dest

        if self.dry_run:
            return key

        key.set_contents_from_filename(src, **options)
        return key


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
    def __init__(self, errors: List[Exception]) -> None:
        StagingException.__init__(self, 'Errors syncing data')
        self.errors = errors


class Redirects(dict):
    def __init__(self, data: List[Tuple[str, str]], exists: bool) -> None:
        dict.__init__(self, data)
        self.htaccess_exists = exists


def run_pool(tasks: List[Callable[[None], None]], n_workers: int=10, retries: int=1) -> None:
    """Run a list of tasks using a pool of threads. Return non-None results or
       exceptions as a list of (task, result) pairs in an arbitrary order."""
    assert retries >= 0

    results = []  # type: List[Tuple[Callable[[None], None], Exception]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = []

        for task in tasks:
            futures.append(pool.submit(task))

        results = [(task, f.exception()) for f, task in zip(futures, tasks) if f.exception()]

    if not results:
        return

    if retries == 0:
        raise SyncException([result[1] for result in results])

    run_pool([r[0] for r in results], n_workers, retries-1)


def translate_htaccess(path: str) -> Redirects:
    """Read a .htaccess file, and transform redirects into a mapping of redirects."""
    try:
        with open(path, 'r') as f:
            data = f.read()
            raw_redirects = [(x.lstrip('/'), y) for x, y in REDIRECT_PAT.findall(data)]
            return Redirects(raw_redirects, exists=True)
    except IOError:
        return Redirects([], exists=False)


class StagingCollector:
    """A dummy file collector interface that always reports files as having
       changed. Yields files and all symlinks.

       Obtain all_subdirectories from StagingTargetConfig. If it is True,
       StagingCollector will only recurse into the directory given by branch."""
    def __init__(self, branch: str, all_subdirectories: bool, namespace: str) -> None:
        self.removed_files = []  # type: List[str]
        self.branch = branch
        self.all_subdirectories = all_subdirectories
        self.namespace = namespace

    def get_upload_set(self, root: str) -> Set[str]:
        return set(os.listdir(root))

    def collect(self, root: str, remote_keys):
        self.removed_files = []
        remote_hashes = {}
        whitelist = self.get_upload_set(root)

        logger.info('Publishing %s', ', '.join(whitelist))

        # List all current redirects
        for key in remote_keys:
            local_key = key.key.replace(self.namespace, '', 1)
            local_key = local_key.lstrip('/')

            # Don't register redirects for deletion in this stage
            if key.size == 0:
                continue

            # Check if we want to skip this path
            if local_key.split('/', 1)[0] not in whitelist:
                continue

            # Store its MD5 hash. Might be useless if encryption or multi-part
            # uploads are used.
            remote_hashes[local_key] = key.etag.strip('"')

            if not os.path.exists(os.path.join(root, local_key)):
                logger.warn('Removing %s', os.path.join(root, local_key))
                self.removed_files.append(key.key)

        logger.info('Done. Scanning local filesystem')

        for basedir, dirs, files in os.walk(root, followlinks=True):
            # Skip branches we wish not to publish
            if basedir == root:
                dirs[:] = [d for d in dirs if d in whitelist]

            for filename in files:
                # Skip dotfiles
                if filename.startswith('.'):
                    continue

                path = os.path.join(basedir, filename)

                try:
                    local_hash = self.hash(path)
                except IOError:
                    continue

                remote_path = path.replace(root, '')
                if remote_hashes.get(remote_path, None) == local_hash:
                    continue

                yield FileUpdate(path, local_hash)

    @staticmethod
    def hash(path: str) -> str:
        """Return the cryptographic hash of the given file path as a hex
           string."""
        hasher = hashlib.md5()

        with open(path, 'rb') as input_file:
            while True:
                data = input_file.read(2**13)
                if not data:
                    break

                hasher.update(data)

        return hasher.hexdigest()


class DeployCollector(StagingCollector):
    def get_upload_set(self, root):
        if not self.all_subdirectories:
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
    S3_OPTIONS = {'reduced_redundancy': True}
    PAGE_SUFFIX = ''

    def __init__(self, config: Config) -> None:
        self.config = config

        self.s3 = BulletProofS3(config.authentication.access_key,
                                config.authentication.secret_key,
                                config.bucket)
        self.collector = self.get_file_collector()

    def get_file_collector(self) -> StagingCollector:
        """Return the file collector to use for instances of this Staging object."""
        return StagingCollector(self.config.branch, self.config.all_subdirectories, self.namespace)

    @property
    def namespace(self) -> str:
        """Staging places each stage under a unique namespace computed from an
           arbitrary username and branch This helper returns such a
           namespace, appropriate for constructing a new Staging instance."""
        # The S3 prefix for this staging site
        return '/'.join([x for x in (self.config.prefix,
                                     self.config.authentication.username,
                                     self.config.branch) if x])

    def purge(self) -> None:
        """Remove all files associated with this prefix."""
        # Remove files from the index first; if the system dies in an
        # inconsistent state, we want to err on the side of reuploading too much
        prefix = '' if not self.namespace else '/'.join((self.namespace, ''))

        keys = [k.key for k in self.s3.list(prefix=prefix)]
        logging.info('Removing the following files: %s', ', '.join(keys))
        result = self.s3.delete_keys(keys)
        if result.errors:
            raise SyncException(result.errors)

    def stage(self, root: str) -> None:
        """Synchronize the build directory with the staging bucket under
           the namespace [username]/[branch]/"""
        tasks = []  # type: List[Callable[[None], None]]

        redirects = Redirects([], exists=False)
        htaccess_path = os.path.join(root, '.htaccess')
        if self.config.branch == 'master':
            redirects = translate_htaccess(htaccess_path)

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
            if os.path.isfile(src_path) and os.path.basename(src_path) in os.listdir(os.path.dirname(src_path)):
                logger.warn('Would ignore redirect that will mask file: %s', src)
#                del redirects[src]

        # Collect files that need to be uploaded
        for entry in self.collector.collect(root, self.s3.list(prefix=self.namespace)):
            src = entry.path.replace(root, '', 1)

            if os.path.islink(entry.path):
                # If redirecting from a directory, make sure we end it with a '/'
                suffix = self.PAGE_SUFFIX if os.path.isdir(entry.path) and not entry.path.endswith('/') else ''

                resolved = os.path.join(os.path.dirname(entry.path), os.readlink(entry.path))
                if os.path.islink(resolved):
                    logger.warn('Multiple layers of symbolic link: %s', resolved)

                if not os.path.exists(resolved):
                    logger.warn('Dead link: %s -> %s', entry.path, resolved)

                if not resolved.startswith(root):
                    logger.warn('Skipping symbolic link %s: outside of root %s', resolved, root)

                redirects[str(Path(src + suffix).ensure_prefix(self.namespace))] = resolved.replace(root, '/', 1)
                continue

            task = functools.partial(self.__upload, src, os.path.join(root, src))
            tasks.append(cast(Callable[[None], None], task))

        # Run our actual staging operations in a thread pool. This would be
        # better with async IO, but this will do for now.
        logger.info('Running %s tasks', len(tasks))
        run_pool(tasks)

        # XXX Right now we only sync redirects on master.
        #     Why: Master has the "canonical" .htaccess, and we'd need to attach
        #          metadata to each redirect on S3 to differentiate .htaccess
        #          redirects from symbolic links.
        #     Ramifications: Symbolic link redirects for non-master branches
        #                    will never be published.
        if self.config.branch == 'master':
            self.sync_redirects(redirects)

        # Remove from staging any files that our FileCollector thinks have been
        # deleted locally.
        remove_keys = [str(path.replace_prefix(root, '').ensure_prefix(self.namespace))
                       for path in [Path(p) for p in self.collector.removed_files]]

        if remove_keys:
            logger.warn('Removing %s', remove_keys)
            remove_result = self.s3.delete_keys(remove_keys)
            if remove_result.errors:
                raise SyncException(remove_result.errors)

    def sync_redirects(self, redirects: Redirects) -> None:
        """Upload the given path->url redirect mapping to the remote bucket."""
        if not redirects.htaccess_exists:
            logger.info('No .htaccess scanned; skipping all redirects')
            return

        if not self.config.redirect_dirs:
            logger.warn('No "redirect_dirs" listed for this project.')
            logger.warn('Not removing any redirects.')

        logger.info('Finding redirects to remove')
        removed = []
        remote_redirects = self.s3.list()
        for key in remote_redirects:
            # Make sure this is a redirect
            if key.size != 0:
                continue

            # Redirects are written /foo/bar/, not /foo/bar/index.html
            redirect_key = key.key.rsplit(self.PAGE_SUFFIX, 1)[0]

            # If it doesn't start with our namespace, ignore it
            if not redirect_key.startswith(self.namespace):
                continue

            # If it doesn't match one of our "owned" directories, ignore it
            if not [True for pat in self.config.redirect_dirs if pat.match(redirect_key)]:
                continue

            if redirect_key not in redirects:
                removed.append(key.key)

        logger.warn('Removing %s redirects', len(removed))
        for remove in removed:
            logger.warn('Removing redirect %s', remove)

        self.s3.delete_keys(removed)

        logger.info('Creating %s redirects', len(redirects))
        tasks = []
        for src in redirects:
            task = functools.partial(self.__redirect_task,
                                     src,
                                     redirects[src],
                                     self.PAGE_SUFFIX)
            tasks.append(cast(Callable[[None], None], task))
        run_pool(tasks)

    def __upload(self, local_path: str, src_path: str) -> None:
        full_name = '/'.join((self.namespace, local_path))

        try:
            logger.info('Uploading %s to %s', src_path, full_name)
            self.s3.upload_path(src_path, full_name, **self.S3_OPTIONS)
        except boto.exception.S3ResponseError as err:
            raise SyncFileException(local_path, err.message)
        except IOError as err:
            logger.exception('IOError while uploading file "%s": %s', local_path, err)

    def __redirect_task(self, src: str, dest: str, suffix: str) -> None:
        self.__redirect(src + suffix, dest)

    def __redirect(self, src: str, dest: str) -> None:
        key = boto.s3.key.Key(self.s3.get_connection(), src)
        try:
            if key.get_redirect() == dest:
                logger.debug('Skipping redirect %s', src)
                return
        except boto.exception.S3ResponseError as err:
            if err.status != 404:
                logger.exception('S3 error creating redirect from %s to %s', src, dest)

        logger.info('Redirecting %s to %s', src, dest)
        self.s3.set_redirect(key, dest)


class DeployStaging(Staging):
    PAGE_SUFFIX = '/index.html'

    def get_file_collector(self) -> StagingCollector:
        return DeployCollector(self.config.branch, self.config.all_subdirectories, self.namespace)

    @property
    def namespace(self) -> str:
        return self.config.prefix


def do_stage(root: str, staging: Staging) -> None:
    """Drive the main staging process, and print nicer error messages
       for exceptions."""
    try:
        staging.stage(root)
    except SyncException as err:
        logger.error('Failed to upload some files:')
        for sub_err in err.errors:
            try:
                raise sub_err
            except SyncFileException as sync_err:
                logger.error('%s: %s', sync_err.path, sync_err.reason)
    except MissingSource as err:
        logger.error('No source directory found at %s', err.message)


def create_config_framework(path: str) -> None:
    """Create a skeleton configuration file with appropriately locked-down
       permissions."""
    try:
        os.mkdir(os.path.dirname(path), 0o751)
    except OSError:
        pass

    # Make sure we don't write the framework if it already exists.
    try:
        with os.fdopen(os.open(path,
                               os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                               0o600), 'wx') as conf_file:
            conf_file.write('[authentication]\n')
    except IOError:
        pass


def main() -> None:
    app = os.path.basename(sys.argv[0])
    options = docopt.docopt(__doc__.format(name=app))

    root = str(options['<source>'])
    bucket = str(options['<bucket>'])
    prefix = str(options['--prefix'])
    redirect_prefixes = cast(List[str], options['--redirect-prefixes'])
    mode_stage = bool(options.get('--stage', False))
    mode_deploy = bool(options.get('--deploy', False))
    mode_destage = bool(options.get('--destage', False))
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

    try:
        config.redirect_dirs += [re.compile(pat) for pat in redirect_prefixes]
    except re.error as err:
        logger.error('Error compiling regular expression: %s', err.message)
        sys.exit(1)

    # --destage requires that we create a Staging context
    if mode_destage:
        mode_stage = True

    if mode_stage:
        staging = Staging(config)
    elif mode_deploy:
        staging = DeployStaging(config)

    staging.s3.dry_run = dry_run

    if mode_destage:
        staging.purge()
        return

    staging.s3.dry_run = dry_run

    try:
        do_stage(root, staging)
    except boto.exception.S3ResponseError as err:
        if err.status == 403:
            logger.error('Failed to upload to S3: Permission denied.')
            logger.info('Check your authentication configuration at %s.',
                        CONFIG_PATH)
            return

        raise err

if __name__ == '__main__':
    main()
