import re
import urllib.parse
from html5_parser import html_parser
from lxml import etree

from typing import Any, Callable, Dict, List, Optional, IO


def node_to_text(node) -> str:
    '''Convert an lxml node to text.'''
    return ' '.join(node.itertext())


def return_text_from_node(func) -> Callable[[Any], str]:
    '''Wraps node_to_text around a function that returns an lxml node.'''
    def textify(*args, **kwargs):
        output = func(*args, **kwargs)
        if isinstance(output, str):
            return output
        elif is_element_of_type(output, '_any'):
            return node_to_text(output)
    return textify


def is_element_of_type(candidate, element_type: str) -> bool:
    '''Return True if the candidate element is an element of the given type.'''
    is_element = isinstance(candidate, etree._Element)
    if element_type == '_any':
        return is_element
    return bool(is_element and candidate.tag == element_type)


class Document:
    '''Return indexing data from an html document.'''
    def __init__(self, base_url: str, root_dir: str, fh: IO) -> None:
        # Paths
        self._base_url = base_url
        self._root_dir = root_dir

        # Document Trees
        self.html = self.parse_html(fh)

        # Properties
        self.slug = self.get_url_slug(fh)
        self.title = self.get_page_title()
        self.headings = self.get_page_headings()
        self.text = self.get_page_text()
        self.preview = self.get_page_preview()
        self.tags = self.get_page_tags()
        self.links = self.get_page_links()

        self.noindex = self.get_noindex()

    def parse_html(self, fh: IO) -> Dict[str, Any]:
        '''Return head and content elements of the document.'''
        capsule = html_parser.parse(fh.read(), maybe_xhtml=True)
        doc = etree.adopt_external_document(capsule).getroot()

        # Remove <style> tags
        for style in list(doc.iter("style")):
            style.getparent().remove(style)

        result = {}
        result['head'] = doc.cssselect('head')[0]

        for candidate in ('.main-column .section', '.main-column section', '.main__content'):
            elements = doc.cssselect(candidate)
            if elements:
                result['main_content'] = elements[0]
                break

        if 'main_content' not in result:
            raise ValueError('No main content element found')

        return result

    def get_url_slug(self, fh: IO) -> str:
        '''Return the slug after the base url.'''
        url_slug = str(fh.name)[len(self._root_dir):]
        return url_slug

    @return_text_from_node
    def get_page_title(self):
        '''Return the title of the page.'''
        return self.html['head'].cssselect('title')[0]

    def get_page_headings(self) -> List[str]:
        '''Return all headings (<h1>, <h2>, <h3>).'''
        all_headings = []
        for heading in self.html['main_content'].iter('h1', 'h2', 'h3'):
            heading = node_to_text(heading)
            if not heading or heading[:1] == "<":
                continue
            all_headings.append(heading.rstrip('\u00b6'))
        return all_headings

    @return_text_from_node
    def get_page_text(self):
        '''Return the text inside the <body> tag.'''
        return self.html['main_content']

    def get_page_preview(self) -> str:
        '''Return a summary of the page.'''

        def test_page_preview(preview: str) -> bool:
            '''Return False if bad preview.'''
            def blacklisted(slug: str) -> bool:
                '''Return True if the file should not have a preview.'''
                blacklist = [
                    '/reference/api.',
                    '/reference.html',
                ]
                matches = [re.compile(item).match(slug) for item in blacklist]
                return any(matches)

            return len(preview) > 30 and not blacklisted(self.slug)

        def set_to_meta_description() -> Optional[str]:
            '''Set preview to the page's meta description.'''
            selector = 'meta[name="description"]'
            candidate_list = self.html['head'].cssselect(selector)
            if candidate_list:
                candidate_preview = candidate_list[0]
                if is_element_of_type(candidate_preview, 'meta'):
                    candidate_preview = candidate_preview.get('content')
                is_good_preview = test_page_preview(candidate_preview)
                if is_good_preview:
                    return candidate_preview
            return None

        def set_to_first_paragraph() -> Optional[str]:
            '''Set preview to the first descriptive paragraph on the page.'''
            candidate_list = self.html['main_content'].cssselect('p')
            for candidate_preview in candidate_list:
                if 'admonition' in (candidate_preview.getparent().get('class') or ''):
                    continue

                if is_element_of_type(candidate_preview, 'p'):
                    candidate_preview = node_to_text(candidate_preview)
                is_good_preview = test_page_preview(candidate_preview)
                if is_good_preview:
                    return candidate_preview
            return None

        page_preview = set_to_meta_description() or set_to_first_paragraph()
        page_preview = ' '.join(page_preview.split()) if page_preview else ''
        return page_preview

    def get_page_tags(self) -> str:
        '''Return the tags for the page.'''
        meta_keywords = self.html['head'].cssselect('meta[name="keywords"]')
        if not meta_keywords:
            return ''
        return meta_keywords[0].get('content')

    def get_page_links(self) -> List[str]:
        '''Return all links to other pages in the documentation.'''
        links = set()
        for link in self.html['main_content'].cssselect('a'):
            href = link.get('href')
            if not href or href.startswith('#'):
                continue
            base = self._base_url.rstrip('/') + '/' + self.slug
            href = urllib.parse.urljoin(base, href)
            if href and not href.startswith('#'):
                links.add(re.sub('#.*$', '', href))
        return list(links)

    def get_noindex(self) -> bool:
        meta_robots = self.html['head'].cssselect('meta[name="robots"]')
        if not meta_robots:
            return False

        return any("noindex" in meta.get("content") for meta in meta_robots)

    def export(self) -> Optional[Dict[str, Any]]:
        '''Generate the manifest dictionary for an html page.'''
        if self.noindex:
            return None

        document = {
            "slug": self.slug,
            "title": self.title,
            "headings": self.headings,
            "text": self.text,
            "preview": self.preview,
            "tags": self.tags,
            "links": self.links
        }
        return document
