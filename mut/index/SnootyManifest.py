from unittest.result import STDERR_LINE
from bson import decode_all
from jsonpath_ng.ext import parse
from os import walk
from os.path import join
from json import dumps
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor

from typing import Any, Dict, Optional, List

class Document:
    '''Return indexing data from a page's AST for search purposes.'''
    def __init__(self, data) -> None:

        self.tree = data[0]

        self.robots, self.keywords, self.description = self.findMetadata()

        self.paragraphs = self.findParagraphs()
        self.code = self.findCode()
        self.title, self.headings = self.findHeadings()
        self.slug = self.deriveSlug()
        self.preview = self.derivePreview()

        self.noindex, self.reasons = self.get_noindex()

    def findParagraphs(self) -> str:
        logger("\tFinding paragraphs")
        # NB: paragraphs include "paragraph" nodes within tables
        jsonpath_expr = parse('$..children[?(@.type==\'paragraph\')]..value')
        results = jsonpath_expr.find(self.tree)
        
        # Appending to then joining an array is faster than repeatedly concatenating strings
        str_list = []
        for r in results:
            str_list.append(r.value)
            
        return ' '.join(str_list)

    def findCode(self):
        logger("\tFinding code")
        jsonpath_expr = parse('$..children[?(@.type==\'code\')]')
        results = jsonpath_expr.find(self.tree)
        code_contents = []
        for r in results:
            lang = r.value.get("lang", None)
            code_contents.append({"lang": lang, "value": r.value["value"]})
        
        return code_contents

    def findHeadings(self):
        logger("\tFinding headings and title")
        # Get all headings nodes
        jsonpath_expr = parse('$..children[?(@.type==\'heading\')].children')
        results = jsonpath_expr.find(self.tree)
        if len(results) == 0:
            return None, None
        headings = []
        limiting_expr = parse('$..value')
        # Some headings consist of multiple text nodes, so we need to glue them together
        for r in results:
            heading = []
            parts = limiting_expr.find(r.value)
            for part in parts:
                heading.append(part.value)
            headings.append(''.join(heading))
        title = headings[0]
        headings.pop(0)
        return title, headings

    def deriveSlug(self):
        logger("\t Deriving slug")
        page_id = self.tree["page_id"]
        return page_id

    def derivePreview(self):
        logger("\tDeriving document search preview")
        # Set preview to the meta description if one is specified.
        if self.description: 
            return self.description
        
        # Set preview to the first content paragraph on the page, excluding admonitions.
        jsonpath_expr = parse('$..children[?(@.type==\'section\')].children[?(@.type==\'paragraph\')]')
        results = jsonpath_expr.find(self.tree)
        if len(results) > 0:
            limiting_expr = parse('$..value')
            first = limiting_expr.find(results[0].value)
            str_list = []
            for f in first:
                str_list.append(f.value)
            return ' '.join(str_list)
        # Cowardly give up and just don't provide a preview.
        else:
            return None

        
    def findMetadata(self):
        logger("\tFinding metadata")
        robots = True
        keywords = None
        description = None

        jsonpath_expr = parse('$..children[?(@.name==\'meta\')]..options')
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

    def get_noindex(self) -> bool:
        # TODO: determine what the index / noindex rules should be
        # with Product (DOP-)
        logger("\tDetermining indexability")
        noindex = False
        reasons: List[str] = []
        # If :robots: None in metadata, do not index
        if self.robots == False:
            noindex = True
            reasons.append("robots=None in meta directive")

        # If page has no title, do not index.
        if self.title == None:
            noindex = True
            reasons.append("This page has 0 headings, not even the H1")

        logger("\tnoindex: {}".format(noindex))
        return noindex, reasons

    def export(self) -> Optional[Dict[str, Any]]:
        '''Generate the manifest dictionary entry from the AST source.'''

        if self.noindex:
            logger("\tRefusing to index {} because: {}".format(self.slug, ' '.join(self.reasons)))
            return

        document = {
            "slug": self.slug,
            "title": self.title,
            "headings": self.headings,
            "paragraphs": self.paragraphs,
            "code": self.code,
            "preview": self.preview,
            "tags": self.keywords,
        }

        return document

class Manifest:
    '''Manifest to provide to Atlas search.'''
    def __init__(self, url: str, includeInGlobalSearch: bool) -> None:
        self.url = url
        self.globally = includeInGlobalSearch
        self.documents: List[Dict[str, Any]] = [] 

    def add_document(self, document: Dict[str, Any]) -> None:
        '''Add a document to the manifest'''
        if not document == None:
            self.documents.append(document)
    
    def export(self) -> str:
        '''Return the manifest as json.'''
        manifest = {
            "url": self.url,
            "includeInGlobalSearch": self.globally,
            "documents": self.documents
        }
        return dumps(manifest, indent=4)

def process_snooty_manifest_bson(path: str) -> Any:
    '''Generates manifest info for a BSON document.'''
    with open(path, 'rb') as f:
        logger(path)
        data = decode_all(f.read())
        document = Document(data).export()
    return document

def generate_manifest(ast_source: str, url: str, includeInGlobalSearch: bool) -> str:
    '''Process BSON files and compile a manifest.'''
    manifest = Manifest(url, includeInGlobalSearch)
    print("Building manifests for {} documents".format(len(ast_source)))

    with ProcessPoolExecutor() as executor:
        for bson_doc in executor.map(process_snooty_manifest_bson, ast_source):
            manifest.add_document(bson_doc)
        return manifest

def get_ast_list(walk_dir: str) -> List[str]:
    '''Get full list of BSON paths that need to be processed,
       get rid of files that don't need to be indexed, but exist as AST.'''
    ast_source_paths: List[str] = []

    for root, dirs, files in walk(walk_dir):
        if 'images' in dirs:
            dirs.remove('images')
        if 'includes' in dirs:
            dirs.remove('includes')
        if 'sharedinclude' in dirs:
            dirs.remove('sharedinclude')
        if '.DS_Store' in files:
            files.remove('.DS_Store')
        for filename in files:
            ast_source_paths.append(join(root, filename))
    return ast_source_paths

def logger(message: str) -> None:
    return
    print(f"{datetime.now()} {message}")
    return
