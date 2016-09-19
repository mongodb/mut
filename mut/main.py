"""Usage: mut-build [--use-builder=(sphinx|tuft)] [--source=<path>]
                    [--tags=<tags>] [--serial] [--no-update-submodules]
                    [--verbose]

-h --help                    show this
--use-builder=(sphinx|tuft)  call sphinx-build [default: sphinx]
--source=<path>              specify the project root path. [default: .]
-t --tags=<tags>             specify a list of comma-delimited sphinx
                             tags to use. [default: website]
--serial                     only execute one transform stage at a time
--no-update-submodules       do not update submodules in the current repository
--verbose                    print more verbose error information

"""

import concurrent.futures
import logging
import multiprocessing
import os
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Tuple, TypeVar, Union

import docopt
import libgiza.git

import mut
import mut.apiargs
import mut.exercise
import mut.extracts
import mut.hash
import mut.images
import mut.options
import mut.release
import mut.steps
import mut.tables
import mut.toc
import mut.tuft

logger = logging.getLogger(__name__)


class FileCollector:
    """Collects and indexes source files."""

    MIGRATE = ('.txt', '.rst', '.png')

    def __init__(self) -> None:
        self.files = {}  # type: Dict[str, List[str]]

    def walk(self, root: str, listening: List[str]) -> None:
        """Crawl the given path, watching for YAML files with the given
           prefixes."""
        for root, _, filenames in os.walk(root):
            for filename in filenames:
                path = os.path.join(root, filename)

                # Hack to copy over plain source files
                splitext = os.path.splitext(filename)
                if len(splitext) == 2 and splitext[1] in self.MIGRATE:
                    self.files['migrate'] = self.files.get('migrate', []) + [path]

                if not filename.endswith('.yaml'):
                    continue

                # Plugin IDs can be either one or two segments in length.
                # Try to find a plugin that matches
                plugin_1 = filename.split('-', 1)[0]
                plugin_2 = '-'.join(filename.split('-', 2)[:2])

                if plugin_2 in listening:
                    plugin = plugin_2
                elif plugin_1 in listening:
                    plugin = plugin_1
                else:
                    continue

                self.files[plugin] = self.files.get(plugin, []) + [path]

    def get_prefixes(self, prefixes: List[str]) -> List[str]:
        """Returns a list of paths matching any of the given prefixes."""
        files = []
        for prefix in prefixes:
            files.extend(self.files.get(prefix, []))

        return files


class PluginSet:
    """Tracks a set of transformation plugins."""
    PLUGINS = [mut.apiargs, mut.extracts, mut.options, mut.release,
               mut.steps, mut.tables, mut.toc, mut.exercise, mut.hash,
               mut.images]  # type: List[Any]

    @property
    def prefixes(self) -> List[str]:
        """Return a list of all prefixes registered by the plugin set."""
        lists = [p.PREFIXES for p in self.PLUGINS]
        return [item for sublist in lists for item in sublist]

    @property
    def plugins(self) -> List[Any]:
        """Returns a list of transformation plugin modules."""
        return [p for p in self.PLUGINS]


def update_submodules() -> None:
    """Update any submodules in this repository."""
    repo = libgiza.git.GitRepo()
    try:
        repo.cmd('submodule', 'update', '--remote')
    except libgiza.git.GitError as err:
        logger.error('Failed to update submodules: %s', str(err))


def migrate(config: mut.RootConfig, paths: List[str]) -> None:
    """Copy plain restructured text files to our output directory."""
    logger.info('Migrating')
    for path in paths:
        dest_path = config.get_output_source_path(path.replace(config.source_path, '', 1))
        src_mtime = os.path.getmtime(path)
        dest_mtime = -1
        try:
            dest_mtime = os.path.getmtime(dest_path)
        except FileNotFoundError:
            pass

        if dest_mtime > src_mtime:
            continue

        dest_dir = os.path.dirname(dest_path)
        try:
            os.makedirs(dest_dir)
        except FileExistsError:
            pass

        shutil.copyfile(path, dest_path)


def main() -> None:
    """Main program entry point."""
    options = docopt.docopt(__doc__)

    builder = str(options['--use-builder'])
    source_path = str(options['--source'])
    tags = [t.strip() for t in str(options['--tags']).split(',')]
    verbose = bool(options['--verbose'])
    serial = bool(options['--serial'])
    no_update_submodules = bool(options['--no-update-submodules'])

    if verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Check to see if PyYAML will work at full speed
    try:
        from yaml import CLoader
    except ImportError:
        logging.warning('PyYAML is missing libyaml')

    config = mut.RootConfig(source_path)
    plugins = PluginSet()
    collected = FileCollector()
    collected.walk(config.source_path, plugins.prefixes)

    warnings = []  # type: List[mut.MutInputError]
    try:
        config.n_workers = 1 if serial else multiprocessing.cpu_count()
        logger.info('Using %s workers', config.n_workers)

        # Migration needs to happen first, because some transformations
        # might depend on the output files.
        migrate(config, collected.get_prefixes(['migrate']))
        with concurrent.futures.ProcessPoolExecutor(max_workers=config.n_workers) as pool:
            futures = []

            for plugin in plugins.plugins:
                futures.append(pool.submit(plugin.run, config, collected.get_prefixes(plugin.PREFIXES)))

            if not no_update_submodules:
                pull = pool.submit(update_submodules)
                pull.result()

            # Collect warnings together into one list
            warnings_lists = [r for r in [f.result() for f in futures] if r is not None]
            warnings = [item for s in warnings_lists for item in s]
    except mut.MutInputError as err:
        if not verbose:
            logger.error('Error in plugin "%s": %s', err.plugin_name, str(err))
            logger.error('    %s: %s', err.path, err.ref)
        else:
            logger.exception(str(err))

    # Log warnings
    for warning in warnings:
        logger.warning('Warning in plugin "%s": %s', warning.plugin_name, str(warning))
        logger.warning('    %s: %s', warning.path, warning.ref)

        if warning.verbose:
            logger.warning(warning.verbose)

    # Call sphinx-build
    output_path = os.path.join(config.output_path, 'html')
    if builder == 'sphinx':
        cmd = ['sphinx-build',
               '-j{}'.format(config.n_workers),
               '-c', config.root_path,
               '-d', os.path.join(config.output_path, '.doctree')]

        # Create tag flags
        cmd.extend([item for sublist in [('-t', tag) for tag in tags]
                    for item in sublist])

        cmd.append(config.output_source_path)
        cmd.append(output_path)
        logger.info('%s', ' '.join(cmd))
        subprocess.check_call(cmd)
    elif builder == 'tuft':
        mut.tuft.build(config.output_source_path, [], output_path)
    elif builder != 'none':
        logger.error('Unknown builder: %s', builder)

if __name__ == '__main__':
    main()
