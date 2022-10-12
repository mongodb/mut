from zipfile import ZipFile, ZipInfo
from bson import decode_all
from jsonpath_ng.ext import parse
from os.path import join
from pathlib import Path
from json import dumps

import logging

from typing import Optional, List, Tuple, TypedDict

logger = logging.getLogger(__name__)


class ManifestEntry(TypedDict):
    slug: str
    title: Optional[str]
    headings: Optional[List[str]]
    paragraphs: str
    code: dict
    preview: Optional[str]
    tags: list[str]


class Document:
    """Return indexing data from a page's AST for search purposes."""

    def __init__(self, data) -> None:

        self.tree = data[0]

        self.robots, self.keywords, self.description = self.find_metadata()

        self.paragraphs = self.find_paragraphs()
        self.code = self.find_code()
        self.title, self.headings = self.find_headings()
        self.slug = self.derive_slug()
        self.preview = self.derive_preview()

        self.noindex, self.reasons = self.get_noindex()

    def find_paragraphs(self) -> str:
        logger.debug("Finding paragraphs")
        # NB: paragraphs include "paragraph" nodes within tables
        jsonpath_expr = parse("$..children[?(@.type=='paragraph')]..value")
        results = jsonpath_expr.find(self.tree)

        # Appending to then joining an array is faster than repeatedly concatenating strings
        str_list = []
        for r in results:
            str_list.append(r.value)

        return " ".join(str_list)

    def find_code(self):
        logger.debug("Finding code")
        jsonpath_expr = parse("$..children[?(@.type=='code')]")
        results = jsonpath_expr.find(self.tree)
        code_contents = []
        for r in results:
            lang = r.value.get("lang", None)
            code_contents.append({"lang": lang, "value": r.value["value"]})

        return code_contents

    def find_headings(self) -> Tuple[Optional[str], Optional[List[str]]]:
        logger.debug("Finding headings and title")
        # Get all headings nodes
        jsonpath_expr = parse("$..children[?(@.type=='heading')].children")
        results = jsonpath_expr.find(self.tree)
        if len(results) == 0:
            return None, None
        headings = []
        limiting_expr = parse("$..value")
        # Some headings consist of multiple text nodes, so we need to glue them together
        for r in results:
            heading = []
            parts = limiting_expr.find(r.value)
            for part in parts:
                heading.append(part.value)
            headings.append("".join(heading))
        title = headings[0]
        headings.pop(0)
        return title, headings

    def derive_slug(self):
        logger.debug("Deriving slug")
        page_id = self.tree["page_id"]
        return page_id

    def derive_preview(self) -> Optional[str]:
        logger.debug("Deriving document search preview")
        # Set preview to the meta description if one is specified.
        if self.description:
            return self.description

        # Set preview to the paragraph value that's a child of a 'target' element
        # (for reference pages that lead with a target definition)
        jsonpath_expr_ref = parse(
            "$..children[?(@.type=='target')].children[?(@.type=='paragraph')]"
        )
        results = jsonpath_expr_ref.find(self.tree)

        if not len(results):
            # Otherwise attempt to set preview to the first content paragraph on the page,
            # excluding admonitions.
            jsonpath_expr = parse(
                "$..children[?(@.type=='section')].children[?(@.type=='paragraph')]"
            )
            results = jsonpath_expr.find(self.tree)

        if len(results) > 0:
            limiting_expr = parse("$..value")
            first = limiting_expr.find(results[0].value)
            str_list = []
            for f in first:
                str_list.append(f.value)
            return " ".join(str_list)
        # Give up and just don't provide a preview.
        else:
            return None

    def find_metadata(self):
        logger.debug("Finding metadata")
        robots: str = True
        keywords: List[str] = None
        description: str = None

        jsonpath_expr = parse("$..children[?(@.name=='meta')]..options")
        results = jsonpath_expr.find(self.tree)
        if results:
            results = results[0].value
            if "robots" in results and results["robots"] == "None":
                robots = False
            if "keywords" in results:
                keywords = results["keywords"]
            if "description" in results:
                description = results["description"]

        return robots, keywords, description

    def get_noindex(self) -> Tuple[bool, List[str]]:
        # TODO: determine what the index / noindex rules should be
        # with Product (DOP-)
        logger.debug("Determining indexability")
        noindex = False
        reasons: List[str] = []
        # If :robots: None in metadata, do not index
        if not self.robots:
            noindex = True
            reasons.append("robots=None in meta directive")

        # If page has no title, do not index.
        if self.title is None:
            noindex = True
            reasons.append("This page has 0 headings, not even the H1")

        logger.debug("noindex: {}".format(noindex))
        return noindex, reasons

    def export(self) -> Optional[ManifestEntry]:
        """Generate the manifest dictionary entry from the AST source."""

        if self.noindex:
            logger.info(
                "Refusing to index {} because: {}".format(
                    self.slug, " ".join(self.reasons)
                )
            )
            return None

        document = ManifestEntry(
            slug=self.slug,
            title=self.title,
            headings=self.headings,
            paragraphs=self.paragraphs,
            code=self.code,
            preview=self.preview,
            tags=self.keywords,
        )
        return document


class Manifest:
    """Manifest to provide to Atlas search."""

    def __init__(self, url: str, includeInGlobalSearch: bool) -> None:
        self.url = url
        self.globally = includeInGlobalSearch
        self.documents: List[ManifestEntry] = []

    def add_document(self, document: ManifestEntry) -> None:
        """Add a document to the manifest"""
        if document:
            self.documents.append(document)

    def export(self) -> str:
        """Return the manifest as json."""
        manifest = {
            "url": self.url,
            "includeInGlobalSearch": self.globally,
            "documents": self.documents,
        }
        return dumps(manifest, indent=4)


def process_snooty_manifest_bson(data) -> Optional[ManifestEntry]:
    """Generates manifest info for a BSON document."""
    document = Document(data).export()
    return document


def check_entry(ast_entry: ZipInfo) -> Optional[ZipInfo]:
    filepath = Path(join(ast_entry.filename))
    if "documents" in filepath.parts and not set(
        ["images", "includes", "sharedinclude"]
    ).intersection(filepath.parts):
        return ast_entry
    return None


def generate_manifest(archive: str, url: str, includeInGlobalSearch: bool) -> Manifest:
    """Process BSON files and compile a manifest."""
    manifest = Manifest(url, includeInGlobalSearch)

    with ZipFile(archive, "r") as astfile:
        for entry in astfile.infolist():
            if check_entry(entry):
                doc_to_add = process_snooty_manifest_bson(
                    decode_all(astfile.read(entry))
                )
                if doc_to_add:
                    manifest.add_document(doc_to_add)

    return manifest
