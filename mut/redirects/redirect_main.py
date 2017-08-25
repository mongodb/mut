"""
Usage:
    mut-redirects <source_path> -o <output>

    -h, --help             List CLI prototype, arguments, and options.
    <source_path>          Path to the file(s) containing redirect rules.
    -o, --output <output>  File path for the output .htaccess file.
"""

# Spec URL: https://docs.google.com/document/d/1oI2boFmtzvbbvt-uQawY9k_gLSLbW7LQO2RjVkvtRgg/edit?ts=57caf48b#

import re
import collections
from typing import List
from docopt import docopt

RuleDefinition = collections.namedtuple('RuleDefinition', ('is_temp', 'version', 'old_url', 'new_url', 'is_symlink'))


class RedirectContext:
    def __init__(self, rules: List = [], symlinks: List = [], definitions: List = []):
        self.rules = []
        self.symlinks = []
        self.definitions = []

        return None

    def add_definition(self, key: str, value: str):
        d = [key, value]
        self.definitions.append(d)

    def generate_rule(self, is_temp: bool, version: str, old_url: str, new_url: str, is_symlink: bool = False):
        context_url = ''

        for x in range(0, len(self.definitions)):
            if (self.definitions[x][0] == 'base'):
                context_url = self.definitions[x][1]

        # if url contains {version} - substitute in the correct version
        old_url_sub = self.rule_substitute(old_url, version)
        new_url_sub = self.rule_substitute(new_url, version)

        # reformatting the old url
        if len(old_url_sub) > 0:
            if old_url_sub[0] != '/':
                old_url_sub = '/' + old_url_sub

            if not is_symlink:
                if old_url_sub[-1] == '/':
                    old_url_sub = old_url_sub[:-1]
                old_url_sub = '/' + context_url + old_url_sub

        new_rule = RuleDefinition._make([is_temp, version, old_url_sub, new_url_sub, False])

        # check for symlinks
        if len(self.symlinks) > 0:
            for x in range(len(self.symlinks)):
                if version == self.symlinks[x][1]:
                    self.generate_rule(is_temp, self.symlinks[x][0], old_url, new_url, True)

        self.rules.append(new_rule)

    def rule_substitute(self, url_string: str, version: str):
        # look for strings between { }
        sub_regex = '{(.*?)}'
        matches = re.findall(sub_regex, url_string, re.DOTALL)
        url_string = url_string.replace('${version}', version)
        url_string = url_string.strip()

        if not matches:
            return url_string

        # loop through each match
        for match in matches:
            # loop through each definition
            for definition in self.definitions:
                # if the match == the definition key
                if match == definition[0]:
                    # substitute the definition value for the match
                    if isinstance(definition[1], str):
                        url_string = url_string.replace('${' + match + '}', definition[1])

        return url_string


def parse_versions(defs: List):
    for x in range(0, len(defs)):
        if defs[x][0] == 'versions':
            return defs[x][1]


def write_to_file(rules: List[RuleDefinition], output_path: str) -> None:
    with open(output_path + '/.htaccess', 'w') as f:

        for rule in rules:
            line = 'Redirect '

            if rule.is_temp:
                line += '302 '
            else:
                line += '301 '

            line += str(rule.old_url) + ' ' + str(rule.new_url)
            f.write(line)
            f.write('\n')
        f.close()


def parse_source_file(source_path: str, output: str):
    version_regex = re.compile('([\[\(])([\w.\*]+)(?:-([\w.\*]+))?([\]\)])')
    url_regex = re.compile(':(?:[ \t\f\v])(.*)(?:[ \t\f\v]->)(.*)')
    rc = RedirectContext()

    with open(source_path) as file:
        for line_num, line in enumerate(file):
            # strip \n from line
            line = line.strip()

            # regex to see if we are dealing with a keyword - define, symlink, or raw
            if re.search('(define|symlink|raw)', line):
                keyword_split = line.split(':', 1)

                # define:
                if keyword_split[0] == 'define':
                    type_split = keyword_split[1].split(' ')
                    key = type_split[1]

                    if len(type_split) > 3:
                        value = []
                        for x in range(2, len(type_split)):
                            value.append(type_split[x])
                    else:
                        value = type_split[2]

                    rc.add_definition(key, value)
                    # see if any definitions have to be substituted with other definitions:
                    for x in range(0, len(rc.definitions)):
                        sub_regex = '{(.*?)}'
                        # This goes pretty deep and can probably be refactored.
                        # Maybe move this logic to a function?
                        if isinstance(rc.definitions[x][1], str):
                            matches = re.findall(sub_regex, rc.definitions[x][1], re.DOTALL)
                            if matches:
                                # loop through each match
                                for y in range(0, len(matches)):
                                    # loop through each definition
                                    for m in range(0, len(rc.definitions)):
                                        # if the match == the definition key
                                        if matches[y] == rc.definitions[m][0]:
                                            # substitute the definition value for the match
                                            if isinstance(rc.definitions[m][1], str):
                                                rc.definitions[x][1] = \
                                                    rc.definitions[x][1].replace(
                                                        '${' + matches[y] + '}', rc.definitions[m][1])

                    versions = parse_versions(rc.definitions)

                # grab symlinks:
                if keyword_split[0] == 'symlink':
                    type_split = line.split(':', 1)
                    sym_split = [sym.strip() for sym in type_split[1].split('->')]

                    rc.symlinks.append(sym_split)

                # raw redirects:
                if keyword_split[0] == 'raw':
                    p = re.compile('(?:[ \t\f\v])(.*)(?:[ \t\f\v]->)(.*)')
                    match = p.search(line)

                    if match:
                        old_url = match.group(1)
                        new_url = match.group(2)

                        # get version from new_url
                        new_url_s = new_url.split('/')
                        version = new_url_s[1]
                        rc.generate_rule(False, version, old_url, new_url)

            # for versioning rules:
            else:
                match = version_regex.search(line)
                if match:
                    # see if we are dealing with a temporary redirect:
                    is_temp = False
                    if (line.split(' ')[0] == 'temporary'):
                        is_temp = True

                    # some more regex hieroglyphs to get the old and new redirect urls:
                    old_url = None
                    new_url = None

                    url_match = url_regex.search(line)

                    if url_match:
                        if url_match.group(1):
                            old_url = url_match.group(1)
                        if url_match.group(2):
                            new_url = url_match.group(2)

                        # match regex groups:
                        # Group 1: Opening container - ( or [
                        # Group 2: Left version number
                        # Group 3: Right version number
                        # Group 4: Closing container - ) or ]

                        # Error checking:
                        # Check if group 2 and/or 3 are '*' or in version array
                        # If not, error.
                        # Process accordingly based on brackets in groups 1 and 4
                        if (match.group(2) not in versions and match.group(2) != '*'):
                            raise ValueError('ERROR: Bad version in line ' + str(line_num))
                        elif match.group(3):
                            if (match.group(3) not in versions and match.group(3) != '*'):
                                raise ValueError('ERROR: Bad version in line ' + str(line_num))

                            # if we've made it this far, there are two versions provided and they are both valid
                            else:
                                # non-inclusive begin_index
                                if match.group(1) == '(':
                                    # left version is *
                                    if match.group(2) == '*':
                                        # this should throw an error based on the spec
                                        raise ValueError('ERROR: Bad formatting in line ' + str(line_num))

                                    # left version is a number, not *
                                    else:
                                        begin_index = versions.index(match.group(2))
                                        # right version is *
                                        # (v2 - *]
                                        if (match.group(3) == '*'):
                                            for x in range(begin_index + 1, len(versions)):
                                                version = versions[x]
                                                rc.generate_rule(is_temp, version, old_url, new_url)

                                        # right version is a number, not *
                                        # (v2 - v3
                                        else:
                                            end_index = versions.index(match.group(3))
                                            # non-inclusive end_index
                                            # (v2 - v3)
                                            if match.group(4) == ')':
                                                # make sure we are actually including at least one version:
                                                if begin_index == end_index:
                                                    raise ValueError('ERROR: No versions included in line ' +
                                                                     str(line_num))
                                                else:
                                                    for x in range(begin_index + 1, end_index):
                                                        version = versions[x]
                                                        rc.generate_rule(is_temp, version, old_url, new_url)

                                            # inclusive end_index
                                            # (v2 - v3]
                                            if match.group(4) == ']':
                                                for x in range(begin_index + 1, end_index + 1):
                                                    version = versions[x]
                                                    rc.generate_rule(is_temp, version, old_url, new_url)

                                # inclusive begin_index
                                elif match.group(1) == '[':
                                    # left version is *
                                    # [* -
                                    if match.group(2) == '*':
                                        end_index = versions.index(match.group(3))

                                        # raise an error here because [* - * should be a raw redirect
                                        if match.group(3) == '*':
                                            raise ValueError('ERROR: Bad formatting in line ' + str(line_num))

                                        else:
                                            # [* - v3)
                                            if (match.group(4) == ')'):
                                                for x in range(0, end_index):
                                                    version = versions[x]
                                                    rc.generate_rule(is_temp, version, old_url, new_url)

                                            # [* - v3]
                                            elif (match.group(4) == ']'):
                                                for x in range(0, end_index + 1):
                                                    version = versions[x]
                                                    rc.generate_rule(is_temp, version, old_url, new_url)
                                    # left version is a number, not *
                                    # [v2 -
                                    else:
                                        begin_index = versions.index(match.group(2))

                                        if match.group(3) == '*':
                                            # right version is *
                                            # [v2 - *]
                                            if (match.group(4) == ')'):
                                                raise ValueError('ERROR: Bad formatting in line ' + str(line_num))

                                            elif (match.group(4) == ']'):
                                                for x in range(begin_index, len(versions)):
                                                    version = versions[x]
                                                    rc.generate_rule(is_temp, version, old_url, new_url)

                                        # right version is a number, not *
                                        else:
                                            end_index = versions.index(match.group(3))

                                            # non-inclusive end_index
                                            # [v2 - v3)
                                            if match.group(4) == ')':
                                                for x in range(begin_index, end_index):
                                                    version = versions[x]
                                                    rc.generate_rule(is_temp, version, old_url, new_url)

                                            # inclusive end_index
                                            # [v2 - v3]
                                            elif match.group(4) == ']':
                                                for x in range(begin_index, end_index + 1):
                                                    version = versions[x]
                                                    rc.generate_rule(is_temp, version, old_url, new_url)

                        # only one version number provided
                        # [v2]
                        elif not match.group(3):
                            version = match.group(2)
                            rc.generate_rule(is_temp, version, old_url, new_url)

    # write all our rules to the file
    write_to_file(rc.rules, output)


def main() -> None:
    """Main entry point for mut redirects to create .htaccess file."""
    options = docopt(__doc__)
    source_path = options['<source_path>']
    output = options['--output']

    # Parse source_path and write to file
    parse_source_file(source_path, output)

if __name__ == '__main__':
    main()
