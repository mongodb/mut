import concurrent.futures
import logging
import math
import os
import shlex
import shutil
import subprocess
import tempfile

from typing import *
import rstcloth.rstcloth

import mut

PREFIXES = ['images']

logger = logging.getLogger(__name__)


class ImagesConfig:
    def __init__(self, root_config: mut.RootConfig) -> None:
        self.root_config = root_config
        self.images = []  # type: List[Image]

    def register(self, image: 'Image') -> None:
        self.images.append(image)

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for image in self.images:
            image.output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'images')


class ImagesInputError(mut.MutInputError):
    @property
    def plugin_name(self) -> str:
        return 'images'


class Image:
    def __init__(self, name: str, config_path: str, config: ImagesConfig) -> None:
        self.name = name
        self.config_path = config_path
        self.path = config.root_config.get_root_path('/source/images/{}.svg'.format(name))
        self.rendered_path = config.root_config.get_root_path('/source/images/{}-output.svg'.format(name))
        self.config = config

        self.alt = ''
        self.width = 0

        config.register(self)

    def output(self) -> None:
        cloth = rstcloth.rstcloth.RstCloth()

        cloth.directive('only', '(website and slides) or (website and html)', wrap=False)
        cloth.newline()
        cloth.directive(name='figure',
                        arg='/images/' + self.name + '.svg',
                        fields=[('figwidth', '{0}px'.format(self.width))],
                        indent=3)
        output_path_suffix = '/images/{}.svg'.format(self.name)
        shutil.copyfile(self.rendered_path,
                        self.config.root_config.get_output_source_path(output_path_suffix))
        cloth.write(self.output_path)

        return

        for output in self.outputs:
            width = str(output.width) + 'px'

            cloth.newline()

            options = [('alt', self.alt),
                       ('align', 'center'),
                       ('figwidth', output.width)]

            if output.target:
                options.append(('target', (output.target)))

            if output.type == 'target':
                continue
            else:
                cloth.directive('only', '(website and slides) or (website and html)', wrap=False)
                cloth.newline()
                cloth.directive(name='figure',
                                arg=output.filename(self.name),
                                fields=options,
                                indent=3)

            cloth.newline()

    def generate_svg(self, output_path: str):
        """Clean up and minify this SVG file."""
        logger.info('Generating %s', output_path)
        inkscape = None

        for path in ('/usr/bin/inkscape', '/usr/local/bin/inkscape',
                     '/Applications/Inkscape.app/Contents/Resources/bin/inkscape'):
            if os.path.exists(path):
                inkscape = path
                break

        if not inkscape:
            logger.error("dependency INKSCAPE not installed. not building images.")
            return

        cmd = '{cmd} {source} --vacuum-defs --export-text-to-path --export-plain-svg {target}'
        with tempfile.NamedTemporaryFile() as tmp:
            cmd = cmd.format(cmd=inkscape, target=tmp.name, source=self.path)
            r = subprocess.call(shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if r != 0:
                logger.warning('error generating image: ' + output_path)
                logger.error(cmd)

            subprocess.check_call(['scour',
                                   '--enable-comment-stripping',
                                   '--enable-id-stripping',
                                   '--shorten-ids',
                                   '--no-line-breaks',
                                   '-q',
                                   '-i', tmp.name,
                                   '-o', output_path])

    @property
    def output_path(self) -> str:
        return os.path.join(self.config.output_path, self.name) + '.rst'

    @classmethod
    def load(cls, value: Dict[str, Any], path: str, config: ImagesConfig) -> 'Image':
        filename = os.path.basename(path)
        name = mut.withdraw(value, 'name', str)
        if not name:
            msg = 'No "name" field found in {}'.format(path)
            raise ImagesInputError(filename, '<unknown>', msg)

        image = cls(name, filename, config)
        image.alt = mut.withdraw(value, 'alt', str)

        raw_outputs = mut.withdraw(value, 'output', mut.list_str_any_dict)

        try:
            web_output = [int(raw['width']) for raw in raw_outputs if raw['type'] == 'web']
            image.width = web_output[0]
        except (ValueError, IndexError) as err:
            raise ImagesInputError(filename, name, 'No "web" output') from err

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            config.root_config.warn(ImagesInputError(path, name, msg))

        return image

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def run(root_config: mut.RootConfig, paths: List[str]) -> List[mut.MutInputError]:
    logger.info('Images: %d', len(paths))
    config = ImagesConfig(root_config)
    for path in paths:
        raw_images = mut.load_yaml(path)
        [Image.load(raw_image, path, config) for raw_image in raw_images]

    config.output()

    return config.root_config.warnings


def run_build_images(root_config: mut.RootConfig, paths: List[str]) -> List[mut.MutInputError]:
    logger.info('Build Images: %d', len(paths))
    config = ImagesConfig(root_config)
    for path in paths:
        raw_images = mut.load_yaml(path)
        [Image.load(raw_image, path, config) for raw_image in raw_images]

    with concurrent.futures.ProcessPoolExecutor(max_workers=root_config.n_workers) as pool:
        futures = []

        for image in config.images:
            output_filename = os.path.join(os.path.dirname(image.path),
                                           image.name + '-output.svg')
            if not mut.compare_mtimes(output_filename, [image.path] + paths):
                continue

            futures.append(pool.submit(
                image.generate_svg,
                output_filename))

        [f.result() for f in futures]

    return config.root_config.warnings
