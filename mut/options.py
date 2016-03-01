import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth

import mut

__all__ = ['PREFIXES', 'run']

PREFIXES = ['options']

logger = logging.getLogger(__name__)


class OptionsConfig:
    def __init__(self, root_config: mut.RootConfig) -> None:
        self.root_config = root_config
        self.options = {}  # type: Dict[str, Option]
        self.final_options = []  # type: List[str]

    def register(self, option: 'Option') -> None:
        option_id = self.option_global_id(option.path, option.ref)
        if option_id in self.options:
            raise ValueError('Already registered')

        self.options[option_id] = option

        if not option.state.program.startswith('_'):
            self.final_options.append(option_id)

    def get_option(self, path: str, ref: str) -> 'Option':
        return self.options[self.option_global_id(path, ref)]

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for option_id in self.final_options:
            self.options[option_id].output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'option')

    @staticmethod
    def option_global_id(path: str, ref: str) -> str:
        return '{}#{}'.format(path, ref)


class OptionInputError(mut.MutInputError):
    @property
    def plugin_name(self):
        return 'option'


class OptionState(mut.State):
    def __init__(self, program: str, name: str) -> None:
        self._replacements = {}  # type: Dict[str, str]

        self.program = program
        self.name = name
        self.aliases = None  # type: str
        self.args = None  # type: str
        self.default = None  # type: str
        self.description = None  # type: str
        self.directive = None  # type: str
        self.optional = False
        self.type = None  # type: str

        self.pre = None  # type: str
        self.post = None  # type: str

    @property
    def replacements(self) -> Dict[str, str]:
        return self._replacements

    @property
    def ref(self) -> str:
        return '{}-{}'.format(self.program, self.name)

    @property
    def keys(self):
        return ['program', 'name', 'directive', 'type', 'default',
                'args', 'description', 'aliases', 'optional', 'pre',
                'post']


class Option:
    def __init__(self,
                 program: str,
                 name: str,
                 path: str,
                 config: OptionsConfig) -> None:
        self.path = os.path.basename(path)
        self._inherit = None  # type: Tuple[str, str]
        self.replacements = {}  # type: Dict[str, str]

        self.state = OptionState(program, name)

        self.config = config
        self.config.register(self)

    @property
    def ref(self) -> str:
        return self.state.ref

    @property
    def parent(self) -> 'Option':
        if self._inherit is None:
            return None

        parent_path, parent_ref = self._inherit
        try:
            return self.config.get_option(parent_path, parent_ref)
        except KeyError:
            msg = 'Could not find Option "{}" to inherit from in "{}"'.format(parent_ref, parent_path)
            raise OptionInputError(self.path, self.ref, msg)

    def inherit(self) -> None:
        parent = self.parent
        if parent is None:
            return

        parent.inherit()
        self.state.inherit(parent.state)
        self._inherit = None

    def output(self) -> None:
        self.inherit()

        # Preconditions
        if not self.state.directive:
            raise OptionInputError(self.path, self.ref, 'Missing "directive"')

        cloth = rstcloth.rstcloth.RstCloth()

        if 'program' not in self.replacements:
            self.replacements['program'] = rstcloth.rstcloth.RstCloth.role('program', self.state.program)

        if self.state.directive == 'option':
            if self.state.name.startswith('<'):
                prefix = ''
            else:
                prefix = '--'

            directive_str = '{prefix}{name}'

            if self.state.args:
                directive_str += ' {args}'

            if self.state.aliases:
                directive_str += ', {0}'.format(self.state.aliases)

                if self.state.args:
                    directive_str += ' {args}'

            if self.state.args:
                directive_str = directive_str.format(prefix=prefix,
                                                     name=self.state.name,
                                                     args=self.state.args)
            else:
                directive_str = directive_str.format(prefix=prefix,
                                                     name=self.state.name)
        else:
            prefix = ''
            directive_str = self.state.name

        if 'role' not in self.replacements:
            self.replacements['role'] = ':{0}:`{1}{2}`'.format(self.state.directive, prefix, self.state.name)

        cloth.directive(self.state.directive, directive_str)
        cloth.newline()

        indent = 3
        if self.state.type:
            cloth.content('*Type*: {0}'.format(self.state.type), indent=indent)
            cloth.newline()

        if self.state.default:
            cloth.content('*Default*: {0}'.format(self.state.default), indent=indent)
            cloth.newline()

        for field in ('pre', 'description', 'post'):
            value = getattr(self.state, field)

            if not value:
                continue

            cloth.content(value.split('\n'), indent=indent, wrap=False)
            cloth.newline()

        content = mut.substitute('\n'.join(cloth.data), self.replacements)
        with open(self.output_path, 'w') as f:
            f.write(content)

    @property
    def output_path(self) -> str:
        self.inherit()
        return os.path.join(self.config.output_path, self.state.directive + '-' + self.ref) + '.rst'

    @classmethod
    def load(cls, value: Any, path: str, config: OptionsConfig) -> 'Option':
        program = mut.withdraw(value, 'program', str)
        if not program:
            raise OptionInputError(path, '<unknown>', 'Missing field "name')

        name = mut.withdraw(value, 'name', str)
        if not name:
            raise OptionInputError(path, 'program', 'Missing field "name')

        option = cls(program, name, path, config)  # type: Option
        option.state.aliases = mut.withdraw(value, 'aliases', str, default='')
        option.state.args = mut.withdraw(value, 'args', str, default='')
        option.state.default = mut.withdraw(value, 'default', str)
        option.state.description = mut.withdraw(value, 'description', str, default='')
        option.state.directive = mut.withdraw(value, 'directive', str)
        option.state.optional = mut.withdraw(value, 'optional', bool, default=False)
        option.state.type = mut.withdraw(value, 'type', str, default='')

        option.state.pre = mut.withdraw(value, 'pre', str, default='')
        option.state.post = mut.withdraw(value, 'post', str, default='')

        replacements = mut.withdraw(value, 'replacement', mut.str_dict)
        if replacements:
            for src, dest in replacements.items():
                option.state.replacements[src] = dest

        raw_inherit = mut.withdraw(value, 'inherit', mut.str_dict, default={})  # type: Dict[str, str]
        if raw_inherit:
            option._inherit = (raw_inherit['file'],
                               '{}-{}'.format(raw_inherit['program'], raw_inherit['name']))

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            raise OptionInputError(path, option.state.ref, msg)

        return option

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def run(root_config: mut.RootConfig, paths: List[str]):
    logger.info('Options')
    config = OptionsConfig(root_config)
    for path in paths:
        raw_options = mut.load_yaml(path)
        [Option.load(o, path, config) for o in raw_options]

    config.output()
