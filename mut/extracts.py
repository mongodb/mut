import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth

import mut
import mut.config
import mut.state
import mut.util

__all__ = ['PREFIXES', 'run']

PREFIXES = ['extracts']

logger = logging.getLogger(__name__)


class ExtractsInputError(mut.MutInputError):
    @property
    def plugin_name(self) -> str:
        return 'extracts'


class ExtractConfig:
    def __init__(self, root_config: mut.config.RootConfig) -> None:
        self.root_config = root_config
        self.extracts = {}  # type: Dict[str, Extract]
        self.final_extracts = set()  # type: Set[str]

    def register(self, extract: 'Extract') -> None:
        extract_id = self.extract_global_id(extract.path, extract.state.ref)
        if extract_id in self.extracts:
            raise ValueError('Already registered')

        self.extracts[extract_id] = extract
        if not extract.state.ref.startswith('_'):
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


class ExtractState(mut.state.State):
    def __init__(self, ref: str) -> None:
        self._ref = ref
        self._replacements = {}  # type: Dict[str, str]

        self._edition = None  # type: str
        self._content = None  # type: str
        self._append = None  # type: List[str]
        self._only = None  # type: str
        self._post = None  # type: str
        self._style = None  # type: str
        self._title = None  # type: str

    @property
    def edition(self) -> str: return self._edition or ''

    @edition.setter
    def edition(self, edition: str) -> None: self._edition = edition

    @property
    def content(self) -> str: return self._content or ''

    @content.setter
    def content(self, content: str) -> None: self._content = content

    @property
    def append(self) -> List[str]: return self._append or []

    @append.setter
    def append(self, append: List[str]) -> None: self._append = append

    @property
    def only(self) -> str: return self._only or ''

    @only.setter
    def only(self, only: str) -> None: self._only = only

    @property
    def post(self) -> str: return self._post or ''

    @post.setter
    def post(self, post: str) -> None: self._post = post

    @property
    def style(self) -> str: return self._style or ''

    @style.setter
    def style(self, style: str) -> None: self._style = style

    @property
    def title(self) -> str: return self._title or ''

    @title.setter
    def title(self, title: str) -> None: self._title = title

    @property
    def replacements(self) -> Dict[str, str]:
        return self._replacements

    @property
    def ref(self) -> str:
        return self._ref

    @property
    def keys(self) -> List[str]:
        return ['_append', '_content', '_only', '_post', '_style', '_title']


class Extract:
    def __init__(self, ref: str, path: str, config: ExtractConfig) -> None:
        self.path = os.path.basename(path)
        self._inherit = None  # type: Tuple[str, str]

        self.state = ExtractState(ref)

        self.config = config
        config.register(self)

    @property
    def parent(self) -> 'Extract':
        if self._inherit is None:
            return None

        parent_path, parent_ref = self._inherit
        try:
            return self.config.get_extract(parent_path, parent_ref)
        except KeyError:
            msg = 'Could not find Extract "{}" to inherit from in "{}"'.format(parent_ref, parent_path)
            raise ExtractsInputError(self.path, self.state.ref, msg)

    def inherit(self) -> None:
        parent = self.parent
        if parent is None:
            return

        parent.inherit()
        self.state.inherit(parent.state)
        self._inherit = None

    def output(self) -> None:
        self.inherit()
        indent = 0
        cloth = rstcloth.rstcloth.RstCloth()

        only = []
        if self.state.only:
            only.append(self.state.only)

        if self.state.edition:
            only.append('({})'.format(self.state.edition))

        if self.state.only:
            cloth.directive('only', ' and '.join(only), indent=indent)
            cloth.newline()
            indent += 3

        if self.state.style:
            cloth.directive('rst-class', self.state.style, indent=indent)
            cloth.newline()

        if self.state.title:
            cloth.h2(self.state.title, indent=indent)
            cloth.newline()

        if self.state.content:
            cloth.content(self.state.content, indent=indent, wrap=False)
            cloth.newline()

        if self.state.post:
            cloth.content(self.state.post, indent=indent)

        try:
            content = mut.util.substitute_rstcloth(cloth, self.state.replacements)
        except KeyError as error:
            raise ExtractsInputError(self.path,
                                     self.state.ref,
                                     'Failed to substitute {}'.format(str(error))) from error

        content = mut.util.substitute_rstcloth(cloth, self.state.replacements)

        mut.util.save_if_changed(content, self.output_path)

        relative_path = self.output_path.replace(self.config.root_config.output_source_path, '', 1)
        include_line = '.. include:: {}'.format(relative_path)
        for append_path in self.state.append:
            append_path = self.config.root_config.get_output_source_path(append_path)
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
        return os.path.join(self.config.output_path, self.state.ref) + '.rst'

    @classmethod
    def load(cls, value: Any, path: str, config: ExtractConfig) -> 'Extract':
        ref = mut.util.withdraw(value, 'ref', str)
        if not ref:
            raise ExtractsInputError(path, '<unknown>', 'Extract with no ref')

        extract = cls(ref, path, config)  # type: Extract
        inherit = mut.util.withdraw(value, 'inherit', mut.util.str_dict, default={})  # type: Dict[str, str]
        if not inherit:
            inherit = mut.util.withdraw(value, 'source', mut.util.str_dict, default={})

        if inherit:
            extract._inherit = (inherit['file'], inherit['ref'])

        replacements = mut.util.withdraw(value, 'replacement', mut.util.str_dict, default={})  # type: Dict[str, str]
        for src, dest in replacements.items():
            extract.state.replacements[src] = dest

        extract.state.edition = mut.util.withdraw(value, 'edition', str)
        extract.state.title = mut.util.withdraw(value, 'title', str)
        extract.state.post = mut.util.withdraw(value, 'post', str)
        extract.state.style = mut.util.withdraw(value, 'style', str)
        extract.state.only = mut.util.withdraw(value, 'only', str)
        extract.state.content = mut.util.withdraw(value, 'content', str)
        append = mut.util.withdraw(value, 'append', mut.util.string_list)
        if append:
            extract.state.append = append

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            raise ExtractsInputError(path, ref, msg)

        return extract

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.state.ref))


def run(root_config: mut.config.RootConfig, paths: List[str]):
    logger.info('Extracts')
    config = ExtractConfig(root_config)
    for path in paths:
        raw_extracts = mut.util.load_yaml(path)
        [Extract.load(e, path, config) for e in raw_extracts if e]

    config.output()
