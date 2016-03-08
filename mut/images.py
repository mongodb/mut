import logging
import os

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


class Output:
    def __init__(self, output_type: str, tag: str,
                 dpi: int, width: int, target: str) -> None:
        self.type = output_type
        self.tag = tag
        self.dpi = dpi
        self.width = width
        self.target = target

    @classmethod
    def load(cls, value: Dict[str, Any], name: str, path: str,
             config: ImagesConfig) -> 'Output':
        output_type = mut.withdraw(value, 'type', str)
        tag = mut.withdraw(value, 'tag', str)
        dpi = mut.withdraw(value, 'dpi', int)
        width = mut.withdraw(value, 'width', int)
        target = mut.withdraw(value, 'target', str)

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            config.root_config.warn(ImagesInputError(path, name, msg))

        return cls(output_type, tag, dpi, width, target)


class Image:
    def __init__(self, name: str, path: str, config: ImagesConfig) -> None:
        self.name = name
        self.path = path
        self.config = config

        self.alt = ''
        self.outputs = []  # type: List[Output]

        config.register(self)

    def output(self) -> None:
        cloth = rstcloth.rstcloth.RstCloth()

        for output in self.outputs:
            width = str(output.width) + 'px'

            cloth.newline()

            if output.tag:
                tag = ''.join(['-', output.tag, '.', output.type])
            else:
                tag = '.' + output.type

            options = [('alt', self.alt),
                       ('align', 'center'),
                       ('figwidth', output.width)]

            if output.target:
                options.append(('target', (output.target)))

            if output.type == 'target':
                continue
            elif output.type == 'print':
                cloth.directive('only', 'latex and not offset', wrap=False)
                cloth.newline()

                cloth.directive(name='figure',
                                arg='/images/{0}{1}'.format(self.name, tag),
                                fields=options,
                                indent=3)
            elif output.type == 'offset':
                tex_figure = [
                    r'\begin{figure}[h!]',
                    r'\centering',
                    ''.join([r'\includegraphics[width=', width,
                             ']{', self.name, tag, '}']),
                    r'\end{figure}'
                ]

                cloth.directive('only', 'latex and offset', wrap=False)
                cloth.newline()
                cloth.directive('raw', 'latex', content=tex_figure, indent=3)
            else:
                cloth.directive('only', 'website and slides', wrap=False)
                cloth.newline()
                cloth.directive(name='figure',
                                arg='/images/{0}{1}'.format(self.name, tag),
                                fields=options,
                                indent=3)

                cloth.newline()

                cloth.directive('only', 'website and html', wrap=False)
                cloth.newline()
                cloth.directive(name='figure',
                                arg='/images/{0}{1}'.format(self.name, tag),
                                fields=options,
                                indent=3)

            cloth.newline()

        cloth.write(self.output_path)

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
        image.outputs = [Output.load(raw, name, path, config) for raw in raw_outputs]

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
