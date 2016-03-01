#!/usr/bin/env python3

import abc
import concurrent.futures
import logging
import urllib.parse

# For Code linting
import json
import shlex
import subprocess
import tempfile

import docutils.nodes
import requests
import requests.exceptions
import certifi
from typing import List, Set, Tuple, Generator

LOGGER = logging.getLogger(__name__)


class Visitor(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def dispatch_visit(self, node: docutils.nodes.Node) -> None: pass

    @abc.abstractmethod
    def dispatch_departure(self, node: docutils.nodes.Node) -> None: pass


class VisitorDriver(Visitor):
    def __init__(self, document: docutils.nodes.document, visitors: List[Visitor]) -> None:
        self.document = document
        self.visitors = visitors

    def dispatch_departure(self, node):
        node.document = self.document

        for visitor in self.visitors:
            visitor.dispatch_departure(node)

    def dispatch_visit(self, node):
        node.document = self.document

        for visitor in self.visitors:
            visitor.dispatch_visit(node)


class WriterDriver(VisitorDriver):
    @abc.abstractmethod
    def astext(self) -> str:
        pass


class LinkLinter(Visitor):
    """Collects external links to check for validity."""

    HEADERS = {'User-Agent': 'mut-tuft'}
    TIMEOUT = 30.0

    def __init__(self):
        self.urls = {}  # type: Dict[str, List[str]]

    def dispatch_visit(self, node):
        if not isinstance(node, docutils.nodes.literal_block):
            return

        if not node.hasattr('refuri'):
            return

        url = node['refuri']
        path = node.document.settings.env.current_input_path
        self.urls[url] = self.urls.get(url, []) + [path]

    def dispatch_departure(self, node): pass

    def test_links(self) -> Generator[Tuple[str, bool, List[str]], None, None]:
        """Yields a list of (URL, okay) pairs representing broken links in this
           file."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = []

            for url, references in self.urls.items():
                parsed_url = urllib.parse.urlparse(url)

                # Without this, we get stuff like mailto:
                if parsed_url.scheme not in ('http', 'https', 'ftp'):
                    continue

                # References to localhost are usually intentional
                if parsed_url.hostname in ('localhost', '127.0.0.1'):
                    continue

                futures.append(pool.submit(self.test_link, url, references))

            for result in concurrent.futures.as_completed(futures):
                yield result.result()

    @classmethod
    def test_link(cls, url: str, references: List[str]) -> Tuple[str, bool, List[str]]:
        headers = cls.HEADERS.copy()

        try:
            r = requests.get(url,
                             headers=headers,
                             timeout=cls.TIMEOUT,
                             verify=True,
                             stream=True)
            if r.status_code >= 400:
                return url, False, references
        except requests.exceptions.RequestException as err:
            return url, False, references

        return url, True, references


class CodeLinter(Visitor):
    def __init__(self):
        self.blocks = []  # type: List[Tuple[str, str, str]]

    def dispatch_visit(self, node):
        if not isinstance(node, docutils.nodes.literal_block):
            return

        try:
            language = node['language']
        except KeyError:
            try:
                language = node['classes'][1] if node['classes'][0] == 'code' else None
            except (IndexError, KeyError):
                return

        path = node.document.settings.env.current_input_path
        if language == 'javascript':
            self.blocks.append((node.rawsource, language, path))

    def dispatch_departure(self, node): pass

    def test_code(self) -> None:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='mut', delete=True) as f:
            for code, language, path in self.blocks:
                # Test code
                pass


class MessageVisitor(Visitor):
    """Logs warnings and errors emitted during parsing."""

    def dispatch_visit(self, node):
        if not isinstance(node, docutils.nodes.system_message):
            return

        if node['level'] == 2:
            LOGGER.warning(node.astext())
        elif node['level'] > 2:
            LOGGER.error(node.astext())
        raise docutils.nodes.SkipNode

    def dispatch_departure(self, node): pass


__all__ = [Visitor, VisitorDriver, LinkLinter, MessageVisitor]
