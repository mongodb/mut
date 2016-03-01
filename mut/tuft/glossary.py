import unicodedata

import docutils.parsers.rst
import docutils.parsers.rst.directives
import docutils.statemachine
import sphinx.addnodes


def make_termnodes_from_paragraph_node(env, node, new_id=None):
    gloss_entries = env.temp_data.setdefault('gloss_entries', set())
    # objects = env.domaindata['std']['objects']

    termtext = node.astext()
    if new_id is None:
        new_id = ':term:' + docutils.nodes.make_id(termtext)
    if new_id in gloss_entries:
        new_id = ':term:' + str(len(gloss_entries))
    gloss_entries.add(new_id)
    # objects['term', termtext.lower()] = env.docname, new_id

    new_termnodes = []
    new_termnodes.extend(node.children)
    new_termnodes.append(sphinx.addnodes.termsep())
    for termnode in new_termnodes:
        termnode.source, termnode.line = node.source, node.line

    return new_id, termtext, new_termnodes


def make_term_from_paragraph_node(termnodes, ids):
    # make a single "term" node with all the terms, separated by termsep
    # nodes (remove the dangling trailing separator)
    term = docutils.nodes.target(ids=ids, *termnodes[:-1])
    term.source, term.line = termnodes[0].source, termnodes[0].line
    term.rawsource = term.astext()
    return term


class Glossary(docutils.parsers.rst.Directive):
    has_content = True
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        'sorted': docutils.parsers.rst.directives.flag
    }

    def run(self):
        env = self.state.document.settings.env
        node = sphinx.addnodes.glossary()
        node.document = self.state.document

        # This directive implements a custom format of the reST definition list
        # that allows multiple lines of terms before the definition.  This is
        # easy to parse since we know that the contents of the glossary *must
        # be* a definition list.

        # first, collect single entries
        entries = []
        in_definition = True
        was_empty = True
        messages = []
        for line, (source, lineno) in zip(self.content, self.content.items):
            # empty line -> add to last definition
            if not line:
                if in_definition and entries:
                    entries[-1][1].append('', source, lineno)
                was_empty = True
                continue
            # unindented line -> a term
            if line and not line[0].isspace():
                # enable comments
                if line.startswith('.. '):
                    continue
                # first term of definition
                if in_definition:
                    if not was_empty:
                        messages.append(self.state.reporter.system_message(
                            2, 'glossary term must be preceded by empty line',
                            source=source, line=lineno))
                    entries.append(([(line, source, lineno)], docutils.statemachine.ViewList()))
                    in_definition = False
                # second term and following
                else:
                    if was_empty:
                        messages.append(self.state.reporter.system_message(
                            2, 'glossary terms must not be separated by empty '
                            'lines', source=source, line=lineno))
                    if entries:
                        entries[-1][0].append((line, source, lineno))
                    else:
                        messages.append(self.state.reporter.system_message(
                            2, 'glossary seems to be misformatted, check '
                            'indentation', source=source, line=lineno))
            else:
                if not in_definition:
                    # first line of definition, determines indentation
                    in_definition = True
                    indent_len = len(line) - len(line.lstrip())
                if entries:
                    entries[-1][1].append(line[indent_len:], source, lineno)
                else:
                    messages.append(self.state.reporter.system_message(
                        2, 'glossary seems to be misformatted, check '
                        'indentation', source=source, line=lineno))
            was_empty = False

        # now, parse all the entries into a big definition list
        items = []
        for terms, definition in entries:
            termtexts = []
            termnodes = []
            system_messages = []
            ids = []
            for line, source, lineno in terms:
                # parse the term with inline markup
                res = self.state.inline_text(line, lineno)
                system_messages.extend(res[1])

                # get a text-only representation of the term and register it
                # as a cross-reference target
                tmp = docutils.nodes.paragraph('', '', *res[0])
                tmp.source = source
                tmp.line = lineno
                new_id, termtext, new_termnodes = \
                    make_termnodes_from_paragraph_node(env, tmp)
                ids.append(new_id)
                termtexts.append(termtext)
                termnodes.extend(new_termnodes)

            term = make_term_from_paragraph_node(termnodes, ids)
            term += system_messages

            defnode = docutils.nodes.definition()
            if definition:
                self.state.nested_parse(definition, definition.items[0][1],
                                        defnode)

            items.append((termtexts,
                          docutils.nodes.definition_list_item('', term, defnode)))

        if 'sorted' in self.options:
            items.sort(key=lambda x:
                       unicodedata.normalize('NFD', x[0][0].lower()))

        dlist = docutils.nodes.definition_list()
        dlist['classes'].append('glossary')
        dlist.extend(item[1] for item in items)
        node += dlist
        return messages + [node]

docutils.parsers.rst.directives.register_directive('glossary', Glossary)
