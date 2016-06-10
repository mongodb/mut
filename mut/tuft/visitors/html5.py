#!/usr/bin/env python3

import collections
import logging
import os.path

import docutils.nodes
import sphinx.addnodes
import dominate
import dominate.tags
import pygments
import pygments.lexers
import pygments.formatters

from typing import Any, List

import mut.tuft
import mut.tuft.visitors
import mut.tuft.condition
import mut.tuft.linkcache
import mut.tuft.exts

LOGGER = logging.getLogger(__name__)

Backref = collections.namedtuple('Backref', ['i', 'backref_id'])


def adapt_path(path: str) -> str:
    return ''.join((os.path.splitext(path)[0], '/'))


def get_url(src_dirname: str, ref: mut.tuft.linkcache.RefDef) -> str:
    """Get a relative URL pointing to the given ref from the given
       source directory."""
    return os.path.relpath(''.join((os.path.splitext(ref.path)[0], '/#', ref.href)),
                           src_dirname)


def render_viewer(env, root='/contents', parent=None):
    if parent is None:
        parent = dominate.tags.ul()

    try:
        children = env.toc[root]
    except KeyError:
        return parent

    l = dominate.tags.ul()
    for child in children:
        l.add(dominate.tags.li(child))
        render_viewer(env, child, l)

    parent.add(l)
    return parent


class HTML5Visitor(mut.tuft.visitors.WriterDriver):
    CODE_FORMATTER = pygments.formatters.HtmlFormatter()

    TAG_MAPPINGS = {
        docutils.nodes.document:            (None, ''),
        docutils.nodes.paragraph:           (dominate.tags.p, ''),
        docutils.nodes.table:               (dominate.tags.table, ''),
        docutils.nodes.tgroup:              (None, ''),
        docutils.nodes.colspec:             (dominate.tags.col, ''),
        docutils.nodes.thead:               (dominate.tags.thead, ''),
        docutils.nodes.row:                 (dominate.tags.tr, ''),
        docutils.nodes.entry:               (dominate.tags.td, ''),
        docutils.nodes.tbody:               (dominate.tags.tbody, ''),
        docutils.nodes.strong:              (dominate.tags.strong, ''),
        docutils.nodes.emphasis:            (dominate.tags.em, ''),
        docutils.nodes.term:                (None, ''),
        docutils.nodes.definition:          (None, ''),
        docutils.nodes.literal:             (dominate.tags.code, ''),
        docutils.nodes.definition_list:     (dominate.tags.dl, ''),
        docutils.nodes.definition_list_item: (dominate.tags.dt, ''),
        docutils.nodes.enumerated_list:     (dominate.tags.ol, ''),
        docutils.nodes.bullet_list:         (dominate.tags.ul, ''),
        docutils.nodes.list_item:           (dominate.tags.li, ''),
        docutils.nodes.field:               (dominate.tags.tr, ''),
        docutils.nodes.field_body:          (dominate.tags.td, ''),
        docutils.nodes.problematic:         (dominate.tags.span, ''),
        docutils.nodes.inline:              (dominate.tags.span, ''),
        docutils.nodes.raw:                 (dominate.tags.pre, ''),
        docutils.nodes.note:                (dominate.tags.div, 'admonition note'),
        docutils.nodes.important:           (dominate.tags.div, 'admonition'),
        docutils.nodes.admonition:          (dominate.tags.div, 'admonition'),
        docutils.nodes.tip:                 (dominate.tags.div, 'admonition topic'),
        docutils.nodes.topic:                 (dominate.tags.div, 'admonition tip'),
        mut.tuft.exts.Example:               (dominate.tags.div, 'admonition example'),
        mut.tuft.exts.Related:               (dominate.tags.div, 'admonition related'),
        mut.tuft.exts.Optional:              (dominate.tags.div, 'admonition optional'),
        docutils.nodes.warning:             (dominate.tags.div, 'admonition warning'),
        mut.tuft.exts.See:                   (dominate.tags.div, 'admonition see'),
        docutils.nodes.superscript:         (dominate.tags.sup, ''),
        docutils.nodes.subscript:           (dominate.tags.sub, ''),
        docutils.nodes.line_block:          (dominate.tags.div, ''),
        docutils.nodes.figure:              (dominate.tags.div, ''),
        docutils.nodes.block_quote:         (dominate.tags.blockquote, ''),
        sphinx.addnodes.versionmodified:    (dominate.tags.div, ''),
        sphinx.addnodes.desc:               (dominate.tags.dl, ''),
        sphinx.addnodes.desc_signature:     (dominate.tags.dt, ''),
        sphinx.addnodes.glossary:           (None, ''),

        # Meta-nodes we don't care about
        docutils.nodes.pending:             (None, '')
    }

    def __init__(self, path: str, document, links: mut.tuft.linkcache.LinkCache) -> None:
        self.path = os.path.normpath(path)
        self.dirname = adapt_path(self.path)

        self.document = document
        self.links = links

        self.tags = mut.tuft.condition.Tags(('html', 'website', 'cloud'))

        self.title = ''
        self.html = dominate.document(title='')
        self.stack = [self.html]
        self.section_level = 0
        self.substitution_defs = {}  # type: Dict[Any, Any]
        self.pending_substitutions = []  # type: List[Any]

        self.footnote_count = 0
        self.footnotes = {}  # type: Dict[str, Any]

    def astext(self):
        # Fill in substitutions
        for pending_element in self.pending_substitutions:
            try:
                sub = self.substitution_defs[pending_element.children[0]]
                if len(sub.children) == 1:
                    sub = sub.children[0]

                # Replace the pending element outright to avoid stupid <span>
                # XXX Use replace_self
                parent_element = pending_element.parent

                for i in range(len(parent_element.children)):
                    if parent_element.children[i] is pending_element:
                        parent_element.children[i] = sub
                        break

                # Our new element must now be inside the parent
            except KeyError as err:
                LOGGER.error('Failed to substitute value: %s', err)

        self.pending_substitutions.clear()

        # If our stack is still populated, something is awry
        assert len(self.stack) == 1

        return str(self.html)

    def visit_section(self, node):
        self.section_level += 1
        self.push_stack(dominate.tags.section)

    def depart_section(self, node):
        self.section_level -= 1
        self.pop_stack()

    def visit_system_message(self, node): pass

    def depart_system_message(self, node): pass

    def visit_Todo(self, node):
        LOGGER.info('todo: ', node.astext())

    def depart_Todo(self, node): pass

    def visit_comment(self, node): pass

    def depart_comment(self, node): pass

    def visit_Text(self, node): pass

    def depart_Text(self, node):
        if not isinstance(node.parent, docutils.nodes.comment) and \
           '.. include::' in node.astext():
            LOGGER.warning('%s: Include directive not handled. Check your spacing.',
                           self.document.settings.env.current_input_path)

        self.stack[-1].add(node.astext())

    def visit_paragraph(self, node):
        if isinstance(node.parent, docutils.nodes.footnote):
            self.push_stack(dominate.tags.span)
        else:
            self.push_stack(dominate.tags.p)

    def depart_paragraph(self, node):
        self.pop_stack()

    def visit_literal_block(self, node):
        # XXX: Not good enough: also need to check for node['language']
        try:
            language = node['classes'][1] if node['classes'][0] == 'code' else None
        except (IndexError, KeyError):
            language = None

        if node.rawsource != node.astext() or not language:
            # most probably a parsed-literal block -- don't highlight
            self.stack[-1].add(dominate.tags.pre(node.rawsource))
            raise docutils.nodes.SkipNode

        try:
            lexer = pygments.lexers.get_lexer_by_name(language)
        except pygments.util.ClassNotFound:
            lexer = pygments.lexers.guess_lexer(node.rawsource)

        html = pygments.highlight(node.rawsource,
                                  lexer,
                                  self.CODE_FORMATTER)
        self.stack[-1].add_raw_string(html)

        raise docutils.nodes.SkipNode

    def depart_literal_block(self, node):
        pass

    def visit_title(self, node):
        # assert isinstance(node.parent, docutils.nodes.section)
        node_id = docutils.nodes.make_id(node.astext())
        self.stack.append(getattr(dominate.tags, 'h{0}'.format(self.section_level))(id=node_id))

    def depart_title(self, node):
        if not self.html.title:
            self.html.title = node.astext()

        self.pop_stack()

    def visit_target(self, node):
        if node.hasattr('refuri'):
            # visit_reference handles this
            return

        if not node.hasattr('ids'):
            return

        for node_id in node['ids']:
            self.stack[-1].add(dominate.tags.span(id=node_id))

    def depart_target(self, node): pass

    def visit_reference(self, node):
        target = None

        if node.hasattr('href'):
            target = node['href']

        if node.hasattr('refuri'):
            target = node['refuri']

        if not target:
            self.stack.append(dominate.tags.a())
            return

        href = ''
        for protocol in ('http://', 'https://', 'ftp://', 'mailto'):
            if target.startswith(protocol):
                href = target
                break

        if not href:
            try:
                ref_def = self.document.settings.env.links[target]
                href = get_url(self.dirname, ref_def)

                # If we have no good title, infer it
                if len(node.children) == 1 and \
                   isinstance(node.children[0], docutils.nodes.Text) and \
                   node.children[0].astext() == ref_def.href:
                    node.children[0] = docutils.nodes.Text(ref_def.title)
            except KeyError as err:
                LOGGER.error('Failed to resolve reference %s (%s)', err, self.path)
                self.stack.append(dominate.tags.span())
                return

        self.stack.append(dominate.tags.a(href=href))

    def depart_reference(self, node):
        self.pop_stack()

    def visit_image(self, node):
        # Transform the path into one based around a relative root
        uri = os.path.normpath(node['uri'])
        if uri.startswith('/'):
            uri = uri.replace('/', '', 1)
            uri = os.path.relpath(uri, self.dirname)

        atts = {}
        atts['src'] = uri
        atts['alt'] = node.get('alt', uri)

        if 'width' in node:
            atts['width'] = node['width']

        if 'height' in node:
            atts['height'] = node['height']

        self.stack.append(dominate.tags.img(**atts))

    def depart_image(self, node):
        self.pop_stack()

    def visit_only(self, node):
        if not self.tags.eval(mut.tuft.condition.parse(node['expr'])):
            raise docutils.nodes.SkipNode

    def depart_only(self, node):
        pass

    def visit_substitution_reference(self, node):
        # Add a span that contains the requested refname, and add it to a list
        # to be lazily-evaluated once all substitutions have definitions
        tag = dominate.tags.span()
        self.stack.append(tag)
        self.pending_substitutions.append(tag)

    def depart_substitution_reference(self, node):
        self.pop_stack()

    def visit_substitution_definition(self, node):
        self.stack.append(dominate.tags.span())

    def depart_substitution_definition(self, node):
        cur = self.stack.pop()
        for name in node['names']:
            self.substitution_defs[name] = cur

    def visit_line(self, node):
        self.stack.append(dominate.tags.div())
        if not len(node):
            self.stack.append(dominate.tags.br())

    def depart_line(self, node):
        self.pop_stack()

        if not len(node):
            self.pop_stack()

    def visit_footnote_reference(self, node):
        refname = node['refname'].lower()

        self.footnotes[refname] = self.footnotes.get(refname, [])
        self.footnotes[refname].append(Backref(len(self.footnotes), node['ids'][0]))

        href = '#' + refname
        self.stack[-1].add(
            dominate.tags.a(
                dominate.tags.sup('[{0}]'.format(len(self.footnotes))),
                href=href,
                id=node['ids'][0]))

    def depart_footnote_reference(self, node): pass

    def visit_footnote(self, node):
        footnote_name = node['names'][0].lower()
        try:
            backrefs = self.footnotes[footnote_name]
            first_backref = backrefs[0]
        except (KeyError, IndexError) as err:
            # This footnote is not referred to anyplace
            LOGGER.warning('Unused footnote: %s', footnote_name)
            raise docutils.nodes.SkipNode

        row = dominate.tags.tr()

        self.stack[-1].add(dominate.tags.table(
            dominate.tags.colgroup(
                dominate.tags.col(),
                dominate.tags.col()),
            dominate.tags.tbody(row),
            id=footnote_name
        ))

        # Format the footnote number
        prefix_element = None
        first_backref = backrefs[0]
        if len(backrefs) == 1:
            # Just one backref; put it in the footnote number
            row.add(dominate.tags.td(
                dominate.tags.a('[{0}]'.format(first_backref.i),
                                href='#' + first_backref.backref_id)))
        else:
            row.add(dominate.tags.td('[{0}]'.format(first_backref.i)))

            # More than one backref. Iterate and build up a list to put in the payload
            i = 0
            prefix_element = dominate.tags.em('(')
            prefix_element.do_inline = True
            for backref in backrefs:
                i += 1
                prefix_element.add(dominate.tags.a(i, href='#' + backref.backref_id))
                if i < len(backrefs):
                    prefix_element.add(',')

            prefix_element.add(')')

        # Add multi-backref links, and prep for adding contents
        payload = dominate.tags.td()
        if prefix_element is not None:
            payload.add(prefix_element)
        row.add(payload)
        self.stack.append(payload)

    def depart_footnote(self, node):
        # Our corresponding element is already in the DOM
        self.stack.pop()

    def visit_seealso(self, node):
        self.stack.append(dominate.tags.div(_class='admonition seealso'))
        self.stack[-1].add(dominate.tags.p('See Also'))

    def depart_seealso(self, node):
        self.pop_stack()

    def visit_field_list(self, node):
        self.stack.append(
            dominate.tags.table([dominate.tags.col(),
                                 dominate.tags.col(),
                                 dominate.tags.tbody()]))

    def depart_field_list(self, node):
        self.stack.pop()

    def dispatch_visit(self, node):
        handler = getattr(self, 'visit_' + type(node).__name__, None)
        if handler:
            return handler(node)

        try:
            tag, classes = self.TAG_MAPPINGS[type(node)]
            if tag is not None:
                self.stack.append(tag(_class=classes))
        except KeyError:
            LOGGER.error('Unknown node: %s', type(node).__name__)

    def dispatch_departure(self, node):
        handler = getattr(self, 'depart_' + type(node).__name__, None)
        if handler:
            return handler(node)

        try:
            tag, _ = self.TAG_MAPPINGS[type(node)]
            if tag is not None:
                self.pop_stack()
        except KeyError:
            # These exceptions are handled on visit
            pass

    def push_stack(self, tag):
        self.stack.append(tag())

    def pop_stack(self):
        cur = self.stack.pop()
        self.stack[-1].add(cur)
