import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth
import rstcloth.table

import mut
import mut.config
import mut.state
import mut.util

__all__ = ['PREFIXES', 'run']

PREFIXES = ['toc', 'ref-toc', 'toc-spec', 'ref-spec']

logger = logging.getLogger(__name__)


class TocConfig:
    def __init__(self, root_config: mut.config.RootConfig) -> None:
        self.root_config = root_config
        self.toc_entries = {}  # type: Dict[str, TocEntry]
        self.tocs = {}  # type: Dict[str, Toc]

    def register(self, toc: 'Toc') -> None:
        toc_id = self.toc_global_id(toc.path, toc.ref)
        if toc_id in self.tocs:
            raise TocInputError(toc.path, toc_id, 'Already registered')

        self.tocs[toc_id] = toc

        for entry in toc.entries:
            entry_id = entry.ref
            if entry_id in self.toc_entries:
                raise TocInputError(toc.path, entry_id, 'Already registered')

            self.toc_entries[entry_id] = entry

    def get_toc_entry(self, path: str, ref: str) -> 'TocEntry':
        return self.toc_entries[self.toc_global_id(path, ref)]

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for toc in self.tocs.values():
            toc.output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'toc')

    @staticmethod
    def toc_global_id(path: str, ref: str) -> str:
        return '{}#{}'.format(path, ref)


class TocInputError(mut.MutInputError):
    @property
    def plugin_name(self):
        return 'Toc'


class TocState(mut.state.State):
    def __init__(self, target: str) -> None:
        self._replacements = {}  # type: Dict[str, str]
        self.file = target
        self.name = None  # type: str
        self.description = None  # type: str
        self.text_only = None  # type: bool
        self.level = None  # type: int

    @property
    def level_or_default(self) -> int:
        return 1 if self.level is None else self.level

    @property
    def replacements(self) -> Dict[str, str]:
        return self._replacements

    @property
    def ref(self) -> str:
        return self.file

    @property
    def keys(self):
        return ['file', 'name', 'description', 'level', 'text_only']

    @property
    def description_or_default(self) -> str:
        return self.description if self.description is not None else ''


class TocEntry:
    def __init__(self, target: str, path: str, config: TocConfig) -> None:
        self.path = os.path.basename(path)
        self._inherit = None  # type: Tuple[str, str]

        self.target = target
        self.state = TocState(target)
        self.config = config

    @property
    def parent(self) -> 'TocEntry':
        if self._inherit is None:
            return None

        parent_path, parent_ref = self._inherit
        try:
            return self.config.get_toc_entry(parent_path, parent_ref)
        except KeyError:
            msg = 'Could not find Toc "{}" to inherit from in "{}"'.format(parent_ref, parent_path)
            raise TocInputError(self.path, self.ref, msg)

    def inherit(self) -> None:
        parent = self.parent
        if parent is None:
            return

        parent.inherit()
        self.state.inherit(parent.state)
        self._inherit = None

    @property
    def ref(self) -> str:
        return self.path + '#' + self.target

    @classmethod
    def load(cls, value: Any, path: str, config: TocConfig) -> 'TocEntry':
        entry_target = mut.util.withdraw(value, 'file', str)
        if entry_target is None:
            entry_target = mut.util.withdraw(value, 'ref', str)
        if entry_target is None:
            try:
                entry_target = value['source']['ref']
            except KeyError as err:
                raise TocInputError(path, entry_target, '') from err

        entry = cls(entry_target, path, config)  # type: TocEntry
        entry.state.name = mut.util.withdraw(value, 'name', str)
        entry.state.description = mut.util.withdraw(value, 'description', str)
        entry.state.level = mut.util.withdraw(value, 'level', int)
        entry.state.text_only = mut.util.withdraw(value, 'text_only', bool)

        raw_inherit = mut.util.withdraw(value, 'source', mut.util.str_dict)
        try:
            if raw_inherit:
                entry._inherit = (raw_inherit['file'], raw_inherit['ref'])
        except KeyError as err:
            raise TocInputError(path, entry_target, '') from err

        return entry


class Toc:
    def __init__(self,
                 entries: List[TocEntry],
                 path: str,
                 config: TocConfig) -> None:
        self.path = os.path.basename(path)

        self.entries = entries
        self.config = config
        self.config.register(self)

    @property
    def ref(self) -> str:
        return os.path.splitext(self.path)[0]

    @property
    def bare_ref(self) -> str:
        ref = self.ref
        if ref.startswith('ref-toc') or ref.startswith('toc-spec') or ref.startswith('ref-spec'):
            return '-'.join(self.ref.split('-', 2)[2:])

        return '-'.join(self.ref.split('-', 1)[1:])

    @property
    def is_ref(self) -> bool:
        if self.path.startswith('ref-toc-'):
            return True
        elif self.path.startswith('ref-spec-'):
            return True

        return False

    @property
    def is_spec(self) -> bool:
        return self.ref.startswith('toc-spec') or self.ref.startswith('ref-spec')

    def output(self) -> None:
        if self.is_ref:
            bare_ref = '-'.join(self.ref.split('-', 2)[2:]) + '.rst'
        else:
            bare_ref = self.ref.replace('toc-', '', 1) + '.rst'

        if not self.is_spec:
            out_path = os.path.join(self.config.output_path, bare_ref)
            self.output_toctree(out_path)

        if self.path.startswith('ref-toc'):
            table_path = os.path.join(self.config.output_path, 'table-' + bare_ref)
            self.output_table(table_path)
        elif self.path.startswith('ref-spec'):
            out_path = os.path.join(self.config.output_path, 'table-spec-' + bare_ref)
            self.output_table(out_path)
        else:
            out_path = os.path.join(self.config.output_path, 'dfn-list-' + bare_ref)
            self.output_dfn(out_path)

    def output_dfn(self, output_path: str) -> None:
        cloth = rstcloth.rstcloth.RstCloth()

        cloth.directive('class', 'toc')
        cloth.newline()

        for entry in self.entries:
            entry.inherit()

            indent = 3 * entry.state.level_or_default

            if entry.state.text_only is True:
                if entry.state.name is not None:
                    cloth.definition(entry.state.name,
                                     entry.state.description,
                                     indent=indent)
                else:
                    cloth.content(entry.state.description, indent=indent)
                cloth.newline()
            else:
                if entry.state.name is not None:
                    dfn_heading = cloth.role('doc', '{0} <{1}>'.format(entry.state.name, entry.state.file))
                else:
                    dfn_heading = cloth.role('doc', entry.state.file)

                if entry.state.description is not None:
                    description = entry.state.description
                else:
                    description = ''

                cloth.definition(dfn_heading, description, indent=indent)
                cloth.newline()

        mut.util.save_rstcloth_if_changed(cloth, output_path)

    def output_toctree(self, output_path: str) -> None:
        is_ref = self.is_ref
        cloth = rstcloth.rstcloth.RstCloth()

        cloth.directive('class', 'hidden')
        cloth.newline()
        cloth.directive('toctree', fields=[('titlesonly', '')], indent=3)
        cloth.newline()

        for entry in self.entries:
            entry.inherit()

            if is_ref is False and entry.state.name is not None:
                field = '{0} <{1}>'.format(entry.state.name, entry.state.file)
                cloth.content(field, indent=6, wrap=False)
            else:
                cloth.content(entry.state.file, indent=6, wrap=False)

        mut.util.save_rstcloth_if_changed(cloth, output_path)

    def output_table(self, output_path: str) -> None:
        table_data = rstcloth.table.TableData()
        table_data.add_header(['Name', 'Description'])
        for entry in self.entries:
            entry.inherit()

            if entry.state.name is None:
                row = [rstcloth.rstcloth.RstCloth.role('doc', entry.state.file),
                       entry.state.description_or_default]
            else:
                row = [entry.state.name, entry.state.description_or_default]

            table_data.add_row(row)

        table_builder = rstcloth.table.TableBuilder(rstcloth.table.RstTable(table_data))
        mut.util.save_rstcloth_table_if_changed(table_builder, output_path)

    @classmethod
    def load(cls, values: List[Any], path: str, config: TocConfig) -> 'Toc':
        entries = [TocEntry.load(v, path, config) for v in values]

        toc = cls(entries, path, config)  # type: Toc

        return toc

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def run(root_config: mut.config.RootConfig, paths: List[str]):
    logger.info('Tocs')
    config = TocConfig(root_config)
    for path in paths:
        raw_tocs = mut.util.load_yaml(path)
        Toc.load(raw_tocs, path, config)

    config.output()
