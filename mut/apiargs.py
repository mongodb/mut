import copy
import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth
import yaml

import mut
import mut.config
import mut.state
import mut.util

__all__ = ['PREFIXES', 'run']

PREFIXES = ['apiargs']

logger = logging.getLogger(__name__)


class ApiargsInputError(mut.MutInputError):
    @property
    def plugin_name(self) -> str:
        return 'apiargs'


class ApiargsConfig:
    def __init__(self, root_config: mut.config.RootConfig) -> None:
        self.root_config = root_config
        self.apiarg_entries = {}  # type: Dict[str, ApiargEntry]
        self.apiargs = []  # type: List[Apiargs]

    def register(self, apiarg: 'Apiargs') -> None:
        self.apiargs.append(apiarg)

        for entry in apiarg.entries:
            entry_id = entry.ref
            if entry_id in self.apiarg_entries:
                raise ApiargsInputError(apiarg.path, entry_id, 'Already registered')

            self.apiarg_entries[entry_id] = entry

    def get_apiarg_entry(self, ref: str):
        return self.apiarg_entries[ref]

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for apiarg in self.apiargs:
            apiarg.output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'apiargs')


class ApiargEntryState(mut.state.State):
    def __init__(self, name: str, path: str) -> None:
        self.path = os.path.basename(path)
        self._replacements = {}  # type: Dict[str, str]

        self.name = name
        self.type = None  # type: str
        self.arg_name = None  # type: str
        self.description = None  # type: str
        self.interface = None  # type: str
        self.operation = None  # type: str
        self.optional = None  # type: bool
        self.position = None  # type: int
        self.pre = None  # type: str
        self.post = None  # type: str

        self._rendered = ''

    @property
    def replacements(self) -> Dict[str, str]:
        return self._replacements

    @property
    def ref(self) -> str:
        return self.path + '#' + self.name

    @property
    def keys(self) -> List[str]:
        return ['name', 'type', 'arg_name', 'description', 'interface',
                'operation', 'optional', 'position', 'pre', 'post']

    @property
    def contents(self) -> str:
        if self._rendered:
            return self._rendered

        components = []
        if self.optional:
            components.append('Optional. ')

        if self.pre:
            components.append(self.pre + '\n\n')

        if self.description:
            components.append(self.description)

        if self.post:
            components.append(self.post + '\n\n')

        self._rendered = ''.join(components)

        if self.replacements:
            try:
                self._rendered = mut.util.substitute(self._rendered, self.replacements)
            except KeyError as error:
                raise ApiargsInputError(self.path,
                                        self.ref,
                                        'Failed to substitute {}'.format(str(error))) from error

        return self._rendered

    @property
    def type_or_default(self) -> str:
        return self.type if self.type is not None else ''


class ApiargEntry:
    def __init__(self, name: str, path: str, config: ApiargsConfig) -> None:
        self.path = os.path.basename(path)
        self.config = config
        self._inherit = None  # type: str

        self.state = ApiargEntryState(name, path)

    @property
    def ref(self) -> str:
        return self.state.ref

    @property
    def parent(self) -> 'ApiargEntry':
        if self._inherit is None:
            return None

        try:
            return self.config.get_apiarg_entry(self._inherit)
        except KeyError:
            msg = 'Could not inherit "{}" from "{}"'.format(self._inherit, self.path)
            raise ApiargsInputError(self.path, self.ref, msg)

    def inherit(self) -> None:
        parent = self.parent
        if parent is not None:
            parent.inherit()
            self.state.inherit(parent.state)

        self._setup_replacements()
        self._inherit = None

    @classmethod
    def load(cls, value: Any, path: str, config: ApiargsConfig) -> 'ApiargEntry':
        entry_name = mut.util.withdraw(value, 'name', str)
        if entry_name is None:
            try:
                entry_name = value['source']['ref']
            except KeyError as err:
                msg = 'No "name" field found in {}'.format(path)
                raise ApiargsInputError(path, entry_name, msg) from err

        entry = cls(entry_name, path, config)  # type: ApiargEntry
        entry.state.arg_name = mut.util.withdraw(value, 'arg_name', str)
        entry.state.description = mut.util.withdraw(value, 'description', str)
        entry.state.interface = mut.util.withdraw(value, 'interface', str)
        entry.state.operation = mut.util.withdraw(value, 'operation', str)
        entry.state.optional = mut.util.withdraw(value, 'optional', bool)
        entry.state.position = mut.util.withdraw(value, 'position', int)
        entry.state.type = mut.util.withdraw(value, 'type', mut.util.str_or_list)
        entry.state.pre = mut.util.withdraw(value, 'pre', str)
        entry.state.post = mut.util.withdraw(value, 'post', str)

        inherit = mut.util.withdraw(value, 'inherit', mut.util.str_dict) or \
                  mut.util.withdraw(value, 'source', mut.util.str_dict)
        if inherit is not None:
            parent_path = mut.util.withdraw(inherit, 'file', str)
            parent_ref = mut.util.withdraw(inherit, 'ref', str)
            entry._inherit = parent_path + '#' + parent_ref

        replacements = mut.util.withdraw(value, 'replacement', mut.util.str_dict)
        if replacements:
            for src, dest in replacements.items():
                entry.state.replacements[src] = dest

        ref = mut.util.withdraw(value, 'ref', str)
        if ref is not None:
            msg = 'Deprecated field: "ref"'
            config.root_config.warn(ApiargsInputError(path, entry_name, msg))

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            raise ApiargsInputError(path, entry_name, msg)

        return entry

    def _setup_replacements(self) -> None:
        if self.state.interface == 'command':
            role_type = 'dbcommand'
        elif self.state.interface == 'method':
            role_type = 'method'
        else:
            role_type = 'samp'

        if 'role' not in self.state.replacements:
            self.state.replacements['role'] = rstcloth.rstcloth.RstCloth.role(role_type, self.state.operation)

        if 'type' not in self.state.replacements:
            if isinstance(self.state.type, list):
                if len(self.state.type) == 1:
                    self.state.replacements['type'] = self.state.type[0]
                elif len(self.state.type) == 2:
                    self.state.replacements['type'] = 'or'.join(self.state.type)
                else:
                    types = copy.copy(self.state.type)
                    types[-1] = 'and ' + types[-1]
                    self.state.replacements['type'] = ','.join(types)
            else:
                self.state.replacements['type'] = self.state.type

        if 'argname' not in self.state.replacements:
            self.state.replacements['argname'] = self.state.name


class Apiargs:
    def __init__(self, entries: List[ApiargEntry], path: str, config: ApiargsConfig) -> None:
        self.entries = entries
        self.path = os.path.basename(path)

        self.config = config
        self.config.register(self)

    @property
    def ref(self) -> str:
        return self.path

    def output(self) -> None:
        for entry in self.entries:
            entry.inherit()

        cloth = rstcloth.rstcloth.RstCloth()

        cloth.directive('only', '(html or singlehtml or dirhtml)')
        cloth.newline()
        self._render_apiarg_table(cloth)

        cloth.newline()

        cloth.directive('only', '(texinfo or latex or epub)')
        cloth.newline()
        self._render_apiarg_fields(cloth)

        mut.util.save_rstcloth_if_changed(cloth, self.output_path)

    @property
    def output_path(self) -> str:
        bare_ref = os.path.splitext(self.ref.replace('apiargs-', '', 1))[0]
        return os.path.join(self.config.output_path, bare_ref) + '.rst'

    def has_type(self) -> bool:
        """Returns True if an entry within this Apiargs instance contains a
           type field."""
        return len([True for e in self.entries if e.state.type is not None]) > 0

    def field_type(self) -> str:
        self.entries[0].inherit()
        return {'field': 'Field',
                'param': 'Parameter',
                'option': 'Option'}[self.entries[0].state.arg_name]

    @classmethod
    def load(cls, values: List[Any], path: str, config: ApiargsConfig) -> 'Apiargs':
        entries = [ApiargEntry.load(v, path, config) for v in values]
        apiargs = cls(entries, path, config)  # type: Apiargs
        return apiargs

    def _render_apiarg_table(self, cloth: rstcloth.rstcloth.RstCloth) -> None:
        table = rstcloth.table.TableData()

        header = [self.field_type()]

        if self.has_type():
            header.append('Type')

        header.append('Description')

        num_columns = len(header)
        table.add_header(header)

        if num_columns == 2:
            widths = [20, 80]
            for entry in self.entries:
                table.add_row([rstcloth.rstcloth.RstCloth.pre(entry.state.name),
                               rstcloth.rstcloth.fill(string=entry.state.contents, first=0, hanging=3, wrap=False)])
        elif num_columns == 3:
            widths = [20, 20, 80]
            for entry in self.entries:
                table.add_row([rstcloth.rstcloth.RstCloth.pre(entry.state.name),
                               entry.state.type_or_default,
                               rstcloth.rstcloth.fill(string=entry.state.contents, first=0, hanging=3, wrap=False)])

        list_table = rstcloth.table.ListTable(table, widths=widths)
        table_builder = rstcloth.table.TableBuilder(list_table)
        cloth.content(table_builder.output, indent=3)

    def _render_apiarg_fields(self, cloth: rstcloth.rstcloth.RstCloth) -> None:
        for entry in self.entries:
            field_name = [entry.state.arg_name]

            if entry.state.type != '':
                field_name.append(entry.state.type_or_default)

            field_name.append(entry.state.name)

            field_content = rstcloth.rstcloth.fill(string=entry.state.contents,
                                                   first=0,
                                                   hanging=6,
                                                   wrap=False)

            cloth.field(name=' '.join(field_name),
                        value=field_content,
                        indent=3,
                        wrap=False)
            cloth.newline()


def run(root_config: mut.config.RootConfig, paths: List[str]) -> List[mut.MutInputError]:
    logger.info('Apiargs')
    config = ApiargsConfig(root_config)
    for path in paths:
        with open(path, 'r') as f:
            raw_apiargs = yaml.load_all(f)
            Apiargs.load(raw_apiargs, path, config)

    config.output()
    return root_config.warnings
