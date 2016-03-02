#!/usr/bin/env python3

import abc
import re
import os.path

import docutils.parsers.rst
import docutils.parsers.rst.roles
import docutils.parsers.rst.directives
import docutils.parsers.rst.directives.misc
import docutils.parsers.rst.directives.admonitions

import sphinx.addnodes
import sphinx.directives.code
import sphinx.directives.other
import sphinx.roles

from typing import Any, Dict

import mut.tuft.mongodb_conf

REF_PAT = re.compile(r'(.*)(?:<(.+)>)$', re.M | re.DOTALL)
METHOD_PAT = re.compile(r'^([^(\n]+)')


class Example(docutils.nodes.Admonition, docutils.nodes.Element):
    pass


class Optional(docutils.nodes.Admonition, docutils.nodes.Element):
    pass


class Related(docutils.nodes.Admonition, docutils.nodes.Element):
    pass


class See(docutils.nodes.Admonition, docutils.nodes.Element):
    pass


class Todo(docutils.nodes.Admonition, docutils.nodes.Element):
    pass


def parse_ref(text):
    groups = REF_PAT.findall(text)
    if not groups:
        groups = [(text, text)]

    label, ref = groups[0]
    if not ref:
        ref = label

    return label, ref


def role(name: str):
    def inner(f):
        docutils.parsers.rst.roles.register_local_role(name, f)

    return inner


class RefRole:
    def __call__(self):
        return []


@role('doc')
def doc_role(role, rawsource, text, lineno, inliner):
    label, ref = parse_ref(text)

    if ref.endswith('/'):
        ref = ref[:-1]

    # Relative path
    if not ref.startswith('/'):
        curdir = os.path.dirname(inliner.document.settings.env.current_input_path)
        ref = os.path.normpath('/'.join(('', curdir, ref)))

    node = docutils.nodes.reference(text=label, href=ref)
    node.document = inliner.document
    return [node], []


@role('ref')
def ref_role(role, rawsource, text, lineno, inliner):
    label, ref = parse_ref(text)

    node = docutils.nodes.reference(text=label, href=ref)
    node.document = inliner.document
    return [node], []


@role('mms')
def mms_role(role, rawsource, text, lineno, inliner):
    return [], []


@role('opsmgr')
def opsmgr_role(role, rawsource, text, lineno, inliner):
    return [], []


@role('option')
def products_role(role, rawsource, text, lineno, inliner):
    return [], []


@role('pep')
def indexmarkup_role(role, rawsource, text, lineno, inliner):
    return [], []


@role('rfc')
def rfc_role(role, rawsource, text, lineno, inliner):
    return [], []


@role('term')
def term_role(role, rawsource, text, lineno, inliner):
    label, ref = parse_ref(text)

    href = ':term:' + docutils.nodes.make_id(ref)
    node = docutils.nodes.reference(text=label, href=href)
    node.document = inliner.document
    return [node], []


def register_extlink(name, pattern):
    @role(name)
    def inner(role, rawsource, text, lineno, inliner):
        label, ref = parse_ref(text)

        ref = pattern.format(ref)

        return [docutils.nodes.reference(text=label, href=ref)], []


class BaseDirective(docutils.parsers.rst.Directive, metaclass=abc.ABCMeta):
    def run(self):
        nodes = self.handle(*self.arguments)
        results = []
        for node in nodes:
            if node.source is None:
                node.source, node.line = (self.state_machine.get_source_and_line(self.lineno))
            results.append(node)

        return results

    @abc.abstractmethod
    def handle(self): pass


class IndexDirective(BaseDirective):
    required_arguments = 1
    optional_arguments = 0
    has_content = False
    final_argument_whitespace = True

    def handle(self, *_): return []


class DefaultDomainDirective(BaseDirective):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = False

    def handle(self, *_): return []


class TocTreeDirective(BaseDirective):
    """
    Directive to notify Sphinx about the hierarchical structure of the docs.
    """
    has_content = True
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        'hidden': docutils.parsers.rst.directives.flag,
        'titlesonly': docutils.parsers.rst.directives.flag,
        'maxdepth': docutils.parsers.rst.directives.nonnegative_int,
    }

    def handle(self):
        env = self.state.document.settings.env
        cur_page = env.current_input_page

        ret = []
        for entry in self.content:
            if not entry:
                continue

            # Create a reference node node
            title, ref = parse_ref(entry)
            if not ref.startswith('/'):
                curdir = os.path.dirname(cur_page)
                ref = os.path.normpath('/'.join((curdir, ref)))

            node = docutils.nodes.reference(text=title, href=ref)
            ret.append(node)

            # Register this child document
            env.register_toc(cur_page, ref)

        return ret


class NopDirective(BaseDirective):
    def handle(self, *_):
        return []


class IncludeDirective(docutils.parsers.rst.directives.misc.Include):
    def run(self):
        env = self.state.document.settings.env
        if self.arguments[0].startswith('<') and \
           self.arguments[0].endswith('>'):
            return docutils.parsers.rst.directives.misc.Include.run(self)

        _, filename = env.relfn2path(self.arguments[0])
        self.arguments[0] = filename
        return docutils.parsers.rst.directives.misc.Include.run(self)


class OnlyDirective(BaseDirective):
    """
    Directive to only include text if the given tag(s) are enabled.
    """
    has_content = True
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    def handle(self, expr):
        node = sphinx.addnodes.only()
        node.document = self.state.document
        node['expr'] = expr

        # Same as util.nested_parse_with_titles but try to handle nested
        # sections which should be raised higher up the doctree.
        surrounding_title_styles = self.state.memo.title_styles
        surrounding_section_level = self.state.memo.section_level
        self.state.memo.title_styles = []
        self.state.memo.section_level = 0
        try:
            self.state.nested_parse(self.content, self.content_offset,
                                    node, match_titles=1)
            title_styles = self.state.memo.title_styles
            if not surrounding_title_styles or \
               not title_styles or \
               title_styles[0] not in surrounding_title_styles or \
               not self.state.parent:
                # No nested sections so no special handling needed.
                return [node]
            # Calculate the depths of the current and nested sections.
            current_depth = 0
            parent = self.state.parent
            while parent:
                current_depth += 1
                parent = parent.parent
            current_depth -= 2
            title_style = title_styles[0]
            nested_depth = len(surrounding_title_styles)
            if title_style in surrounding_title_styles:
                nested_depth = surrounding_title_styles.index(title_style)
            # Use these depths to determine where the nested sections should
            # be placed in the doctree.
            n_sects_to_raise = current_depth - nested_depth + 1
            parent = self.state.parent
            for i in range(n_sects_to_raise):
                if parent.parent:
                    parent = parent.parent
            parent.append(node)

            # This whole behavior is incredibly naughty. We duplicate it for
            # compatibility reasons, but need to yell at the user.
            return [self.state.document.reporter.warning('Titles within an '
                    '"only" directive may yield surprising reordering.')]
        finally:
            self.state.memo.title_styles = surrounding_title_styles
            self.state.memo.section_level = surrounding_section_level


class SeeAlsoDirective(docutils.parsers.rst.directives.admonitions.BaseAdmonition):
    node_class = sphinx.addnodes.seealso


class ExampleDirective(docutils.parsers.rst.directives.admonitions.BaseAdmonition):
    node_class = Example


class OptionalDirective(docutils.parsers.rst.directives.admonitions.BaseAdmonition):
    node_class = Optional


class RelatedDirective(docutils.parsers.rst.directives.admonitions.BaseAdmonition):
    node_class = Related


class TodoDirective(docutils.parsers.rst.directives.admonitions.BaseAdmonition):
    node_class = Todo


class SeeDirective(docutils.parsers.rst.directives.admonitions.BaseAdmonition):
    node_class = See


class VersionChange(BaseDirective):
    has_content = True
    required_arguments = 1
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {}  # type: Dict[str, Any]

    def handle(self, version, *args):
        node = sphinx.addnodes.versionmodified()
        node.document = self.state.document
        node['version'] = version
        node['type'] = self.name

        messages = []
        if args:
            text = args[0]
            inodes, new_messages = self.state.inline_text(text, self.lineno+1)
            messages.extend(new_messages)
            para = docutils.nodes.paragraph(text, '', *inodes)
            para.document = self.state.document
            node.append(para)

        if self.content:
            self.state.nested_parse(self.content, self.content_offset, node)

        return [node] + messages


def make_object_directive(name, can_call):
    class RefDirective(BaseDirective):
        has_content = True
        final_argument_whitespace = True
        required_arguments = 1
        optional_arguments = 100
        callable = can_call

        def handle(self, *args):
            # XXX Handle multiple prototypes (sphinx uses comma as a delimiter)
            name = ' '.join(args)
            parsed = METHOD_PAT.findall(name)
            if not parsed:
                return []

            suffix = '()' if (self.callable and not parsed[0].endswith(')')) else ''
            mangled_name = '{0}:{1}{2}'.format(self.name, parsed[0], suffix)

            node = sphinx.addnodes.desc()
            node.document = self.state.document

            node_signature = sphinx.addnodes.desc_signature()
            node_signature.document = self.state.document
            node_signature.append(docutils.nodes.literal(text=name))
            node.append(node_signature)

            if self.content:
                self.state.nested_parse(self.content, self.content_offset, node)

            return [docutils.nodes.target(ids=[mangled_name]), node]

    docutils.parsers.rst.directives.register_directive(name, RefDirective)

for directive_info in mut.tuft.mongodb_conf.conf['directives']:
    make_object_directive(directive_info['name'], directive_info['callable'])

    @role(directive_info['name'])
    def r(role, rawsource, text, lineno, inliner):
        label, ref = parse_ref(text)

        abbreviate = False
        if ref.startswith('~'):
            abbreviate = True
            ref = ref[1:]

        ref_name = ':'.join((role, ref))

        # These elements should be code-block'd
        wrapper_node = docutils.nodes.literal()
        wrapper_node.document = inliner.document
        wrapper_node.append(docutils.nodes.reference(text=label, href=ref_name))
        return [wrapper_node], []

docutils.parsers.rst.directives.register_directive('include', IncludeDirective)

docutils.parsers.rst.directives.register_directive('rst-class', docutils.parsers.rst.directives.misc.Class)
docutils.parsers.rst.directives.register_directive('default-domain', DefaultDomainDirective)
docutils.parsers.rst.directives.register_directive('toctree', TocTreeDirective)
docutils.parsers.rst.directives.register_directive('index', IndexDirective)
docutils.parsers.rst.directives.register_directive('versionadded', VersionChange)
docutils.parsers.rst.directives.register_directive('versionchanged', VersionChange)
docutils.parsers.rst.directives.register_directive('deprecated', VersionChange)
docutils.parsers.rst.directives.register_directive('only', OnlyDirective)

docutils.parsers.rst.directives.register_directive('seealso', SeeAlsoDirective)
docutils.parsers.rst.directives.register_directive('optional', OptionalDirective)
docutils.parsers.rst.directives.register_directive('example', ExampleDirective)
docutils.parsers.rst.directives.register_directive('see', SeeDirective)
docutils.parsers.rst.directives.register_directive('related', RelatedDirective)
docutils.parsers.rst.directives.register_directive('todo', TodoDirective)
