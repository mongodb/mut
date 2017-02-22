import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth
import rstcloth.table

import mut.config

__all__ = ['PREFIXES', 'run']

PREFIXES = ['table']

logger = logging.getLogger(__name__)


class TableConfig:
    def __init__(self, root_config: mut.config.RootConfig) -> None:
        self.root_config = root_config
        self.tables = []  # type: List['Table']

    def register(self, table: 'Table') -> None:
        self.tables.append(table)

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for table in self.tables:
            table.output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'table')


class Table:
    def __init__(self, path: str, config: TableConfig) -> None:
        self.path = os.path.basename(path)

        self.table_data = rstcloth.table.YamlTable(path)

        self.config = config
        self.config.register(self)

    @property
    def ref(self) -> str:
        return os.path.splitext(self.path.replace('table-', '', 1))[0]

    def output(self) -> None:
        list_table = rstcloth.table.ListTable(self.table_data)
        builder = rstcloth.table.TableBuilder(list_table)
        mut.util.save_rstcloth_table_if_changed(builder, self.output_path)

    @property
    def output_path(self) -> str:
        return os.path.join(self.config.output_path, self.ref) + '.rst'

    @classmethod
    def load(cls, path: str, config: TableConfig) -> 'Table':
        table = cls(path, config)  # type: Table

        return table

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def run(root_config: mut.config.RootConfig, paths: List[str]):
    logger.info('Tables')
    config = TableConfig(root_config)
    for path in paths:
        with open(path, 'r') as f:
            Table.load(path, config)

    config.output()
