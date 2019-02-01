"""
Usage:
    mut-redirects <source_path> [-o <output>]

    -h, --help             List CLI prototype, arguments, and options.
    <source_path>          Path to the file(s) containing redirect rules.
    -o, --output <output>  File path for the output .htaccess file.
"""

# Spec URL:
# https://docs.google.com/document/d/1oI2boFmtzvbbvt-uQawY9k_gLSLbW7LQO2RjVkvtRgg/edit?ts=57caf48b

import collections
import os
import re
import sys
from typing import List, Optional, Dict, Tuple, Pattern, IO
from docopt import docopt

RuleDefinition = collections.namedtuple(
    'RuleDefinition',
    ('is_temp', 'version', 'old_url', 'new_url', 'is_symlink'))


class RedirectContext:
    def __init__(self, root: Optional[str]) -> None:
        self.root = root
        self.rules = []  # type: List[RuleDefinition]
        self.symlinks = []  # type: List[Tuple[str, str]]
        self.definitions = {}  # type: Dict[str, str]
        self._versions = None  # type: Optional[List[str]]

    @property
    def versions(self) -> List[str]:
        if self._versions is None:
            self._versions = self.definitions['versions'].split(' ')

        return self._versions

    def add_definition(self, key: str, value: str) -> None:
        self.definitions[key] = value

    def generate_rule(self,
                      is_temp: bool,
                      version: str,
                      old_url: str,
                      new_url: str,
                      is_symlink: bool = False) -> None:
        # if url contains {version} - substitute in the correct version
        old_url_sub = self.rule_substitute(old_url, version)
        new_url_sub = self.rule_substitute(new_url, version)

        # reformatting the old url
        if len(old_url_sub) > 0:
            if old_url_sub[0] != '/':
                old_url_sub = '/' + old_url_sub

        new_rule = RuleDefinition(is_temp, version, old_url_sub, new_url_sub, False)

        # check for symlinks
        if len(self.symlinks) > 0 and version is not 'raw':
            for symlink in self.symlinks:
                if version == symlink[1]:
                    self.generate_rule(is_temp, symlink[0], old_url, new_url, True)

        self.rules.append(new_rule)

    def rule_substitute(self, input_string: str, version: str = '') -> str:
        # look for strings between { }
        sub_regex = '{(.*?)}'
        matches = re.findall(sub_regex, input_string, re.DOTALL)
        if (version != ''):
            input_string = input_string.replace('${version}', version)

        input_string = input_string.strip()

        if not matches:
            return input_string

        for match in matches:
            # substitute the definition value for the match
            if match != 'version':
                input_string = input_string.replace('${' + match + '}', self.definitions[match])
        return input_string


def write_to_file(rules: List[RuleDefinition], f: IO[str]) -> None:
    for rule in rules:
        line = 'Redirect '

        if rule.is_temp:
            line += '302 '
        else:
            line += '301 '

        line += str(rule.old_url) + ' ' + str(rule.new_url)
        f.write(line)
        f.write('\n')


def parse_line(line: str,
               rc: RedirectContext,
               line_num: int,
               version_regex: Pattern,
               url_regex: Pattern) -> None:
    # strip \n from line
    line = line.strip()
    # regex to see if we are dealing with a keyword - define, symlink, or raw
    if re.search('^(define|symlink|raw)', line):
        keyword_split = line.split(':', 1)

        # define:
        if keyword_split[0] == 'define':
            value = ''
            type_split = keyword_split[1].split(' ')
            key = type_split[1]

            if len(type_split) > 3:
                for x in range(2, len(type_split)):
                    value = value + type_split[x] + ' '
            else:
                value = type_split[2]

            value = value.strip()
            value = rc.rule_substitute(value)
            rc.add_definition(key, value)

        # grab symlinks:
        if keyword_split[0] == 'symlink' and rc.root is not None:
            type_split = line.split(':', 1)
            sym_split = [sym.strip() for sym in type_split[1].split('->')]
            alias, origin = sym_split
            alias_path = os.path.join(rc.root, alias)

            try:
                os.remove(alias_path)
            except FileNotFoundError:
                pass

            os.symlink(origin, alias_path)
            rc.symlinks.append((alias, origin))

        # raw redirects:
        if keyword_split[0] == 'raw':
            p = re.compile('(?:[ \t\f\v])(.*)(?:[ \t\f\v]->)(.*)')
            match = p.search(line)

            if match:
                old_url = match.group(1)
                new_url = match.group(2)

                # get version from new_url
                rc.generate_rule(False, 'raw', old_url, new_url)

    # for versioning rules:
    else:
        match = version_regex.search(line)
        if match:
            # Syntax check:
            # Make sure there is a colon after the version
            if match.group(5) != ':':
                raise ValueError('ERROR in line {}: Bad rule syntax'.format(line_num))

            # see if we are dealing with a temporary redirect:
            is_temp = False
            if (line.split(' ')[0] == 'temporary'):
                is_temp = True

            # some more regex hieroglyphs to get the old and new redirect urls:
            old_url = ''
            new_url = ''

            url_match = url_regex.search(line)

            assert url_match
            if url_match.group(1):
                old_url = url_match.group(1)
            if url_match.group(2):
                new_url = url_match.group(2)

            # match regex groups:
            # Group 1: Opening container - ( or [
            # Group 2: Left version number
            # Group 3: Right version number
            # Group 4: Closing container - ) or ]
            # Group 5: Char after Group 4. Must be a colon.

            # Error checking:
            # Check if group 2 and/or 3 are '*' or in version array
            # If not, error.
            # Process accordingly based on brackets in groups 1 and 4
            if (match.group(2) not in rc.versions and match.group(2) != '*'):
                raise ValueError('ERROR in line {}: Version {} not present in version list'
                                 .format(line_num, match.group(2)))
            elif match.group(3):
                if (match.group(3) not in rc.versions and match.group(3) != '*'):
                    raise ValueError('ERROR in line {}: Version {} not present in version list'
                                     .format(line_num, match.group(3)))
                if match.group(2) != '*':
                    begin_index = rc.versions.index(match.group(2))
                if match.group(3) != '*':
                    end_index = rc.versions.index(match.group(3))

                if (match.group(1) == '(' and match.group(2) == '*') or \
                   (match.group(3) == '*' and match.group(4)[0] == ')'):
                    # this should throw an error based on the spec
                    raise ValueError('ERROR: Bad formatting in line ' + str(line_num))

                # (v2.0 - *]
                elif match.group(1) == '(' and match.group(2) != '*' and \
                        match.group(3) == '*' and match.group(4)[0] == ']':
                    for x in range(begin_index + 1, len(rc.versions)):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

                # (v2.0 - v3.0) ERROR
                elif match.group(1) == '(' and match.group(2) != '*' and \
                        match.group(3) != '*' and match.group(4)[0] == ')':
                    # make sure we are actually including at least one version:
                    if begin_index == end_index:
                        raise ValueError('ERROR: No versions included in line ' +
                                         str(line_num))

                    for x in range(begin_index + 1, end_index):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

                # (v2.0 - v3.0]
                elif match.group(1) == '(' and match.group(2) != '*' and \
                        match.group(3) != '*' and match.group(4)[0] == ']':
                    for x in range(begin_index + 1, end_index + 1):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

                # [* - *] ERROR
                elif match.group(1) == '[' and match.group(2) == '*' and match.group(3) == '*':
                    # raise an error here because [* - * should be a raw redirect
                    raise ValueError('ERROR: Bad formatting in line ' + str(line_num))

                # [* - v3.0)
                elif match.group(1) == '[' and match.group(2) == '*' and \
                        match.group(3) != '*' and match.group(4)[0] == ')':
                    for x in range(0, end_index):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

                # [* - v3.0]
                elif match.group(1) == '[' and match.group(2) == '*' and \
                        match.group(3) != '*' and match.group(4)[0] == ']':
                    for x in range(0, end_index + 1):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

                # [v2.0 - *]
                elif match.group(1) == '[' and match.group(2) != '*' and \
                        match.group(3) == '*' and match.group(4)[0] == ']':
                    for x in range(begin_index, len(rc.versions)):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

                # [v2.0 - v3.0)
                elif match.group(1) == '[' and match.group(2) != '*' and \
                        match.group(3) != '*' and match.group(4)[0] == ')':
                    for x in range(begin_index, end_index):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

                # [v2.0 - v3.0]
                elif match.group(1) == '[' and match.group(2) != '*' and \
                        match.group(3) != '*' and match.group(4)[0] == ']':
                    for x in range(begin_index, end_index + 1):
                        version = rc.versions[x]
                        rc.generate_rule(is_temp, version, old_url, new_url)

            # only one version number provided
            else:
                version = match.group(2)
                if version == '*':
                    for ver in rc.versions:
                        rc.generate_rule(is_temp, ver, old_url, new_url)
                else:
                    rc.generate_rule(is_temp, version, old_url, new_url)


def parse_source_file(source_path: str, output: Optional[str]) -> None:
    version_regex = re.compile(r'([\[\(])([\w.\*]+)(?:-([\w.\*]+))?([\]\)](.))')
    url_regex = re.compile(r':(?:[ \t\f\v])(.*)(?:[ \t\f\v]->)(.*)')

    root = None
    if output is not None:
        root = os.path.dirname(output) or './'

    rc = RedirectContext(root)
    with open(source_path) as file:
        for line_num, line in enumerate(file, start=1):
            if not line or line.startswith('#'):
                continue
            parse_line(line, rc, line_num, version_regex, url_regex)

    # Remove unknown symlinks
    if root is not None:
        for path in os.listdir(root):
            if not os.path.islink(path):
                continue

            if os.path.basename(path) in rc.symlinks:
                continue

            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    # Write all our rules to the file
    if output is None:
        write_to_file(rc.rules, sys.stdout)
    else:
        with open(output, 'w') as f:
            write_to_file(rc.rules, f)


def main() -> None:
    """Main entry point for mut redirects to create .htaccess file."""
    options = docopt(__doc__)
    source_path = options['<source_path>']
    output = options['--output']

    # Parse source_path and write to file
    parse_source_file(source_path, output)


if __name__ == '__main__':
    main()
