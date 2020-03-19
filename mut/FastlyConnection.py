import sys
import os
import json
import logging

logger = logging.getLogger(__name__)

from typing import cast, Any, Callable, Dict, List, Set, Tuple, \
    TypeVar, Iterable, Pattern, NamedTuple, Optional

class Fastly:
    """Sets up connection to Fastly"""
    def __init__(self, fastly_token: str) -> None:
        self.fastly_token = fastly_token

    def clear_cache(full_urls: List[str]) -> None:
        """clears cachce for a set of urls"""
        fastly_token = os.environ.get('FASTLY_TOKEN', None)

        if fastly_token == None:
            logger.error('Fastly token is missing.')

        # clear cache in url array here
        # todo