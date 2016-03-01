#!/usr/bin/env python3

import collections
import os
import os.path
import re
import sys

import docutils.nodes
from typing import List

DIRECTIVE_PAT = re.compile(r'\s*\.\. (\S+)::\s*([^\n]*)\n?$')
REF_DEF_PAT = re.compile(r'\s*\.\. _([^:\s]+):')
ROLE_PAT = re.compile(r'(?::(\S+):)`(?:[^<`]+\s*<)?([^\s>]+)>?`', re.M)

RefDef = collections.namedtuple('Link', ['title', 'href', 'path', 'intersphinx'])


class LinkAnalyzerVisitor:
    def __init__(self, path: str, document) -> None:
        self.path = os.path.normpath(path)
        self.document = document
        self.pending_ref_defs = []  # type: List[RefDef]
        self.ref_defs = []  # type: List[RefDef]

        # Anything that needs to link to this document directly needs to know
        # its title
        self.title = ''

        doc_ref = os.path.normpath(self.path)
        doc_ref = '/' + os.path.splitext(doc_ref)[0]
        self.ref_defs.append(RefDef(self.title, doc_ref, self.path, False))

    def dispatch_visit(self, node):
        if isinstance(node, docutils.nodes.system_message):
            return

        if isinstance(node, docutils.nodes.target):
            if not node.hasattr('ids'):
                return

            if node.hasattr('refuri'):
                # This is a link, not a reference definition
                return

            ids = [RefDef(node_id, node_id, self.path, False) for node_id in node['ids']]
            if node.hasattr('names'):
                ids.extend([RefDef(name, name, self.path, False) for name in node['names']])

            if ids:
                self.pending_ref_defs.extend(ids)
                return

        if isinstance(node, docutils.nodes.title):
            title = node.astext()
            if not self.title:
                self.title = title

            self.ref_defs.extend([ref_def._replace(title=title) for ref_def in self.pending_ref_defs])
            self.pending_ref_defs.clear()
            return

        if isinstance(node, docutils.nodes.section):
            return

        self.ref_defs.extend(self.pending_ref_defs)
        self.pending_ref_defs.clear()

    def dispatch_departure(self, node):
        # At the end of the document, finalize our title and pending ref_defs
        if isinstance(node, docutils.nodes.document):
            self.ref_defs[0] = self.ref_defs[0]._replace(title=self.title)
            self.ref_defs.extend(self.pending_ref_defs)
            self.pending_ref_defs.clear()


class LinkCache:
    def __init__(self, root: str) -> None:
        self.root = root

        # Used for quick link resolution
        self.paths = {}  # type: Dict[str, List[RefDef]]
        self.node_ids = {}  # type: Dict[str, List[RefDef]]

        # Used for incremental builds
        self.dependencies = {}

    def update(self, env):
        for root, _, files in os.walk(self.root):
            for filename in files:
                filename = os.path.join(root, filename)

                if not filename.endswith('.txt'):
                    continue

                rel_filename = filename.replace(self.root, '')

                document = env.get_document(filename)
                visitor = LinkAnalyzerVisitor(filename, document)
                document.walkabout(visitor)

                for ref_def in visitor.ref_defs:
                    self.add(ref_def)

        # for ref_id in self.node_ids:
        #     print(ref_id)

    def add(self, ref_def: RefDef):
        if ref_def.path not in self.paths:
            self.paths[ref_def.path] = []

        self.paths[ref_def.path].append(ref_def)
        self.node_ids[ref_def.href] = ref_def

    def __getitem__(self, node_id: str) -> RefDef:
        node_id = self.__normalize_node_id(node_id)

        # Unfortunately, docutils throws away case information for target nodes,
        # requiring us to check both the "proper" case (for case-sensitive nodes
        # that we construct), and the lower case.
        try:
            return self.node_ids[node_id]
        except KeyError:
            return self.node_ids[node_id.lower()]

    def get_dependencies(self, path: str):
        if path not in self.paths:
            return []

        closed_list = set()
        open_list = self.paths[path][:]

        while open_list:
            cur = open_list.pop().path
            if cur in closed_list:
                continue

            open_list.extend(self.paths[cur])

        return closed_list

    def __parse(self, path):
        pass

    def __normalize_node_id(self, node_id: str) -> str:
        """Sanity-process a node id; handle newlines, etc."""
        return node_id.replace('\n', ' ')
