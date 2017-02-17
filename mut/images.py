import logging
import os
import shutil

from typing import *
import rstcloth.rstcloth

import mut
import mut.config

PREFIXES = ['images']

logger = logging.getLogger(__name__)


class ImagesConfig:
    def __init__(self, root_config: mut.config.RootConfig) -> None:
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
        self.rendered_path = config.root_config.get_root_path('/source/images/{}.bakedsvg.svg'.format(name))
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
        try:
            shutil.copyfile(self.rendered_path,
                            self.config.root_config.get_output_source_path(output_path_suffix))
        except FileNotFoundError:
            msg = 'Could not find input SVG file.'
            raise ImagesInputError(self.config_path, self.name, msg)

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

    @property
    def output_path(self) -> str:
        return os.path.join(self.config.output_path, self.name) + '.rst'

    @classmethod
    def load(cls, value: Dict[str, Any], path: str, config: ImagesConfig) -> 'Image':
        filename = os.path.basename(path)
        name = mut.util.withdraw(value, 'name', str)
        if not name:
            msg = 'No "name" field found in {}'.format(path)
            raise ImagesInputError(filename, '<unknown>', msg)

        image = cls(name, filename, config)
        image.alt = mut.util.withdraw(value, 'alt', str)

        raw_outputs = mut.util.withdraw(value, 'output', mut.util.list_str_any_dict)

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


def run(root_config: mut.config.RootConfig, paths: List[str]) -> List[mut.MutInputError]:
    logger.info('Images: %d', len(paths))
    config = ImagesConfig(root_config)
    for path in paths:
        raw_images = mut.util.load_yaml(path)
        [Image.load(raw_image, path, config) for raw_image in raw_images if raw_image]

    config.output()

    return config.root_config.warnings
