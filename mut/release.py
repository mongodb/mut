import logging
import os
import os.path

import rstcloth.rstcloth
from typing import Any, Dict, List

import mut

__all__ = ['PREFIXES', 'run']

PREFIXES = ['release']

logger = logging.getLogger(__name__)


class ReleaseInputError(mut.MutInputError):
    @property
    def plugin_name(self) -> str:
        return 'release'


class ReleaseConfig:
    def __init__(self, root_config: mut.RootConfig) -> None:
        self.root_config = root_config
        self.entries = {}  # type: Dict[str, ReleaseEntry]
        self.final_entries = []  # type: List[ReleaseEntry]

    def register(self, entry: 'ReleaseEntry') -> None:
        self.entries[entry.ref] = entry

        if not entry.ref.startswith('_'):
            self.final_entries.append(entry)

    def get(self, ref: str) -> 'ReleaseEntry':
        return self.entries[ref]

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for entry in self.final_entries:
            entry.output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'release')


class ReleaseEntryState(mut.State):
    def __init__(self, ref: str) -> None:
        self._replacements = {
            'version': '1.0',
            'branch': '1.0',
            'stable': '1.0',
        }

        self._ref = ref
        self.pre = ''
        self.language = None  # type: str
        self.code = ''
        self.content = ''
        self.post = ''

    @property
    def replacements(self) -> Dict[str, str]:
        """Return a dictionary mapping template replacements."""
        return self._replacements

    @property
    def ref(self) -> str:
        """Return a string uniquely identifying this element."""
        return self._ref

    @property
    def keys(self) -> List[str]:
        """Return a list of attributes in this Release entry that will inherit
           from a parent object."""
        return ['pre', 'language', 'code', 'content', 'post']


class ReleaseEntry:
    def __init__(self,
                 ref: str,
                 state: ReleaseEntryState,
                 path: str,
                 config: ReleaseConfig) -> None:
        self.path = os.path.splitext(os.path.basename(path))[0]
        self.ref = ref
        self._inherit = None  # type: str

        self.state = state

        self.config = config
        config.register(self)

    def output(self):
        if self._inherit is not None:
            self.inherit()

        indent = 0
        cloth = rstcloth.rstcloth.RstCloth()
        if self.state.pre:
            cloth.content(content=self.state.pre,
                          indent=indent,
                          wrap=False)
            cloth.newline()

        if self.state.code:
            cloth.directive(name='code-block',
                            arg=self.state.language,
                            indent=indent,
                            wrap=False)
            cloth.newline()
            cloth.content(self.state.code, wrap=False, indent=indent + 3)

        if self.state.content:
            cloth.content(content=self.state.content,
                          indent=indent,
                          wrap=False)
            cloth.newline()

        if self.state.post:
            cloth.content(content=self.state.post,
                          indent=indent,
                          wrap=False)
            cloth.newline()

        contents = '\n'.join(cloth.data)
        contents = mut.substitute(contents, self.state.replacements)
        with open(self.output_path, 'w') as f:
            f.write(contents)

    @property
    def parent(self) -> 'ReleaseEntry':
        if self._inherit is None:
            return None

        try:
            return self.config.get(self._inherit)
        except KeyError:
            msg = 'Could not inherit "{}" from "{}"'.format(self._inherit, self.path)
            raise ReleaseInputError(self.path, self.ref, msg)

    def inherit(self) -> None:
        parent = self.parent
        if parent is None:
            return

        parent.inherit()
        self.state.inherit(parent.state)
        self._inherit = None

    @property
    def output_path(self) -> str:
        return os.path.join(self.config.output_path, self.ref) + '.rst'

    @classmethod
    def load(cls, value: Dict[str, Any], path: str, config: ReleaseConfig) -> 'ReleaseEntry':
        ref = mut.withdraw(value, 'ref', str)
        state = ReleaseEntryState(ref)
        entry = cls(ref, state, path, config)  # type: ReleaseEntry

        entry.state.pre = mut.withdraw(value, 'pre', str)
        entry.state.language = mut.withdraw(value, 'language', str)
        entry.state.code = mut.withdraw(value, 'code', str)
        entry.state.content = mut.withdraw(value, 'content', str)
        entry.state.post = mut.withdraw(value, 'post', str)

        if 'source' in value:
            entry._inherit = mut.withdraw(value, 'source', mut.str_dict)['ref']

        replacements = mut.withdraw(value, 'replacement', mut.str_dict)
        if replacements:
            for src, dest in replacements.items():
                entry.state.replacements[src] = dest

        return entry


def run(root_config: mut.RootConfig, paths: List[str]):
    logger.info('Release')
    config = ReleaseConfig(root_config)
    for path in paths:
        raw_entries = mut.load_yaml(path)
        [ReleaseEntry.load(e, path, config) for e in raw_entries]

    config.output()
