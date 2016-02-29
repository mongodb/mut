import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth

import mut

__all__ = ['PREFIXES', 'run']

PREFIXES = ['extracts']

logger = logging.getLogger(__name__)


class ExtractsInputError(mut.MutInputError):
    @property
    def plugin_name(self) -> str:
        return 'extracts'


class ExtractConfig:
    def __init__(self, root_config: mut.RootConfig) -> None:
        self.root_config = root_config
        self.extracts = {}  # type: Dict[str, Extract]
        self.final_extracts = set()  # type: Set[str]

    def register(self, extract: 'Extract') -> None:
        extract_id = self.extract_global_id(extract.path, extract.ref)
        if extract_id in self.extracts:
            raise ValueError('Already registered')

        self.extracts[extract_id] = extract
        if not extract.ref.startswith('_'):
            self.final_extracts.add(extract_id)

    def get_extract(self, path: str, ref: str) -> 'Extract':
        return self.extracts[self.extract_global_id(path, ref)]

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for extract_id in self.final_extracts:
            self.extracts[extract_id].output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'extracts')

    @staticmethod
    def extract_global_id(path: str, ref: str) -> str:
        return '{}#{}'.format(path, ref)


class Extract:
    def __init__(self, ref: str, path: str, config: ExtractConfig) -> None:
        self.ref = ref
        self.path = os.path.basename(path)
        self.inherit = None  # type: Tuple[str, str]
        self.replacements = {}  # type: Dict[str, str]

        self.only = ''  # type: str
        self.post = ''  # type: str
        self.append = []  # type: List[str]
        self.title = None  # type: str
        self.style = ''  # type: str
        self._content = None  # type: str

        self.config = config
        config.register(self)

    @property
    def content(self) -> str:
        if self._content is not None:
            return self._content

        self._content = ''

        if self.inherit is not None:
            source_path, source_id = self.inherit
            source = self.config.get_extract(source_path, source_id)
            self._content = source.content

        # Apply replacements
        self._content = mut.substitute(self._content, self.replacements)

        # Apply post
        if self.post:
            self._content = '\n'.join([self._content, self.post])

        return self._content

    def output(self) -> None:
        indent = 0
        cloth = rstcloth.rstcloth.RstCloth()

        if self.only:
            cloth.directive('only', self.only, indent=indent)
            cloth.newline()
            indent += 3

        if self.style:
            cloth.directive('rst-class', self.style, indent=indent)
            cloth.newline()

        if self.title:
            cloth.h2(self.title, indent=indent)
            cloth.newline()

        for block in self.content.split('\n\n'):
            cloth.content(block, indent=indent, wrap=False)
            cloth.newline()

        cloth.write(self.output_path)

        relative_path = self.output_path.replace(self.config.root_config.output_source_path, '', 1)
        include_line = '.. include:: {}'.format(relative_path)
        for append_path in self.append:
            append_path = self.config.root_config.get_absolute_path(append_path)
            with open(append_path, 'a+') as f:
                found = False
                f.seek(0)
                lines = f.readlines()[::-1]
                while lines:
                    if lines[0].startswith(include_line):
                        found = True
                        break

                    if not lines[0].startswith('..include::') or lines[0].strip():
                        break

                    lines.pop()

                if not found:
                    f.write('\n\n' + include_line + '\n')

    @property
    def output_path(self) -> str:
        return os.path.join(self.config.output_path, self.ref) + '.rst'

    @classmethod
    def load(cls, value: Any, path: str, config: ExtractConfig) -> 'Extract':
        ref = mut.withdraw(value, 'ref', str)
        if not ref:
            raise ExtractsInputError(path, '<unknown>', 'Extract with no ref')

        extract = cls(ref, path, config)  # type: Extract
        inherit = mut.withdraw(value, 'inherit', mut.str_dict, default={})  # type: Dict[str, str]
        if not inherit:
            inherit = mut.withdraw(value, 'source', mut.str_dict, default={})

        if inherit:
            extract.inherit = (inherit['file'], inherit['ref'])

        replacements = mut.withdraw(value, 'replacement', mut.str_dict, default={})  # type: Dict[str, str]
        for src, dest in replacements.items():
            extract.replacements[src] = dest

        extract.title = mut.withdraw(value, 'title', str)
        extract.post = mut.withdraw(value, 'post', str)
        extract.style = mut.withdraw(value, 'style', str)
        extract.only = mut.withdraw(value, 'only', str)
        extract._content = mut.withdraw(value, 'content', str)
        append = mut.withdraw(value, 'append', mut.string_list)
        if append:
            extract.append = append

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            raise ExtractsInputError(path, ref, msg)

        return extract

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def run(root_config: mut.RootConfig, paths: List[str]):
    logger.info('Extracts')
    config = ExtractConfig(root_config)
    for path in paths:
        raw_extracts = mut.load_yaml(path)
        [Extract.load(e, path, config) for e in raw_extracts]

    config.output()
