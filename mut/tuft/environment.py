import os.path
import sys

import docutils.parsers.rst
import docutils.frontend
import docutils.utils
import docutils.nodes
from typing import *

import mut.tuft.linkcache


class Environment:
    DEFAULT_CONFIG = {
        'source_suffix': '.txt',
        'rst_epilog': ''
    }

    def __init__(self,
                 srcdir: str,
                 links: mut.tuft.linkcache.LinkCache,
                 config: Dict[str, Any]) -> None:
        self.srcdir = srcdir
        self.links = links

        self.current_input_path = ''
        self.document_cache = {}  # type: Dict[str, Any]
        self.parser = docutils.parsers.rst.Parser()

        self.temp_data = {}  # type: Dict[str, Any]
        self.config = self.DEFAULT_CONFIG.copy()
        self.config.update(config)
        self.toc = {}  # type: Dict[str, Any]

    @property
    def current_input_page(self):
        return '/' + os.path.normpath(os.path.splitext(self.current_input_path)[0])

    def relfn2path(self, filename: str, docname: str=None) -> Tuple[str, str]:
        """Return paths to a file referenced from a document, relative to
        documentation root and absolute.

        In the input "filename", absolute filenames are taken as relative to the
        source dir, while relative filenames are relative to the dir of the
        containing document.
        """
        if filename.startswith('/') or filename.startswith(os.sep):
            rel_fn = filename[1:]
        else:
            docdir = os.path.dirname(self.doc2path(docname or self.docname,
                                                   base=None))
            rel_fn = os.path.join(docdir, filename)
        try:
            # the os.path.abspath() might seem redundant, but otherwise artifacts
            # such as ".." will remain in the path
            return rel_fn, os.path.abspath(os.path.join(self.srcdir, rel_fn))
        except UnicodeDecodeError:
            # the source directory is a bytestring with non-ASCII characters;
            # let's try to encode the rel_fn in the file system encoding
            enc_rel_fn = rel_fn.encode(sys.getfilesystemencoding())
            return rel_fn, os.path.abspath(os.path.join(self.srcdir, enc_rel_fn))

    def doc2path(self, docname: str, base: Union[bool, str]=True, suffix: str=None) -> str:
        """Return the filename for the document name.

        If *base* is True, return absolute path under self.srcdir.
        If *base* is None, return relative path to self.srcdir.
        If *base* is a path string, return absolute path under that.
        If *suffix* is not None, add it instead of config.source_suffix.
        """
        docname = docname.replace('/', os.path.sep)
        suffix = suffix or self.config['source_suffix']
        if base is True:
            return os.path.join(self.srcdir, docname) + suffix
        elif base is None:
            return docname + suffix
        elif isinstance(base, str):
            return os.path.join(base, docname) + suffix
        else:
            assert('Unreachable')

    def get_document(self, path: str):
        """Parse a given .rst file, with a caching layer."""
        try:
            return self.document_cache[path]
        except KeyError:
            pass

        self.current_input_path = path

        settings = docutils.frontend.OptionParser(
            components=(docutils.parsers.rst.Parser,)
            ).get_default_values()
        settings.report_level = 1000
        settings.keep_warnings = False
        settings.syntax_highlight = 'none'
        settings.env = self

        document = docutils.utils.new_document(None, settings)
        document.current_source = path
        document.source = path

        with open(path, 'r') as input_file:
            text = '\n'.join((input_file.read(), self.config['rst_epilog']))
            self.parser.parse(text, document)

        self.document_cache[path] = document

        return document

    def register_toc(self, parent, child):
        if parent not in self.toc:
            self.toc[parent] = []

        self.toc[parent].append(child)
