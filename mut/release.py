import logging

from typing import List

import mut

__all__ = ['PREFIXES', 'run']

PREFIXES = []  # type: List[str]

logger = logging.getLogger(__name__)


def run(root_config: mut.RootConfig, paths: List[str]):
    logger.info('Release')
