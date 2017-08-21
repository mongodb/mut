"""
Usage:
    mut-redirects <source_path> -o <output>

    -h, --help             List CLI prototype, arguments, and options.
    <source_path>          Path to the file(s) containing redirect rules.
    -o, --output <output>  File path for the output .htaccess file.
"""

# Spec URL: https://docs.google.com/document/d/1oI2boFmtzvbbvt-uQawY9k_gLSLbW7LQO2RjVkvtRgg/edit?ts=57caf48b#

import re
from docopt import docopt

rules = []
symlinks = []
definitions = []

class Rule:
    is_temp = None
    version = None
    old_url = None
    new_url = None

def parse_versions(defs):
    for x in range (0, len(defs)):
        if defs[x][0] == 'versions':
            return defs[x][1]

def generate_rule(is_temp, version, old_url, new_url, is_symlink = False):

    global definitions
    global symlinks
    global rules
    
    context_url = ''
    
    for x in range (0, len(definitions)):
        if (definitions[x][0] == 'base'):
            context_url = definitions[x][1]
    
    # if url contains {version} - substitute in the correct version
    old_url_sub = rule_substitue(old_url, version)
    new_url_sub = rule_substitue(new_url, version)
    
    # small reformatting the old url
    if len(old_url_sub) > 0:
        if old_url_sub[0] != '/':
            old_url_sub = '/' + old_url_sub
            
        if not is_symlink:
            if old_url_sub[-1] == '/':
                old_url_sub = old_url_sub[:-1]
            old_url_sub = '/' + context_url + old_url_sub

    new_rule = Rule()
    
    new_rule.is_temp = is_temp
    new_rule.version = version
    new_rule.old_url = old_url_sub
    new_rule.new_url = new_url_sub
    
    # check for symlinks
    if len(symlinks) > 0:
        for x in range (len(symlinks)):
            if version == symlinks[x][1]:
                r = generate_rule(is_temp, symlinks[x][0], old_url, new_url, True)
                rules.append(r)
    
    return new_rule

def rule_substitue(url_string, version):
    
    global definitions
    
    # look for strings between { }
    sub_regex = '{(.*?)}'
    
    matches = re.findall(sub_regex, url_string, re.DOTALL)
    
    if matches:
        # loop through each match
        for x in range(0, len(matches)): 
            # loop through each definition
            for y in range(0, len(definitions)):
                # if the match == the definition key
                if matches[x] == definitions[y][0]:
                    # substitute the definition value for the match
                    if type(definitions[y][1]) is str:
                        url_string = url_string.replace('${' + matches[x] + '}', definitions[y][1])
                    
    url_string = url_string.replace('${version}', version)
    
    url_string = url_string.strip()
    
    return url_string
    
def write_to_file(rules, output):
    
    # I'm not sure how we want to handle the file name - maybe it makes sense to have it as a parameter?
    file = open(output + '/htaccess_test.txt', 'w')
    
    for rule in rules:
        line = 'Redirect '
        
        if rule.is_temp:
            line += '302 '
        else:
            line += '301 '
            
        line += str(rule.old_url) + ' ' + str(rule.new_url)
        
        file.write(line)
        file.write('\n')
        
    file.close()

def parse_source_file(source_path, output):
    
    line_num = 0
    
    with open(source_path) as file:
        for line in file:
            
            line_num += 1
            
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
                        
                        for x in range (2, len(type_split)):
                            value.append(type_split[x])
                            
                    else:
                        value = type_split[2]
                        
                    definition = [key, value]
                    
                    global definitions
                    definitions.append(definition)
                    
                    # see if any definitions have to be substituted with other definitions:
                    for x in range(0, len(definitions)):
                        sub_regex = '{(.*?)}'
                        
                        if type(definitions[x][1]) is str:
                            matches = re.findall(sub_regex, definitions[x][1], re.DOTALL)
    
                            if matches:
                                # loop through each match
                                for y in range(0, len(matches)): 
                                    # loop through each definition
                                    for m in range(0, len(definitions)):
                                        # if the match == the definition key
                                        if matches[y] == definitions[m][0]:
                                            # substitute the definition value for the match
                                            if type(definitions[m][1]) is str:
                                                definitions[x][1] = definitions[x][1].replace('${' + matches[y] + '}', definitions[m][1])
                        
                    
                    versions = parse_versions(definitions)
                    
                # grab symlinks:
                if keyword_split[0] == 'symlink':
                    type_split = line.split(':', 1)
                    sym_split = type_split[1].split('->')
                    
                    for x in range(0, len(sym_split)):
                        sym_split[x] = sym_split[x].strip()
                        
                    global symlinks
                    symlinks.append(sym_split)
    
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
                        
                        r = generate_rule(False, version, old_url, new_url)
                        
                        rules.append(r)
                        
            # for versioning rules:
            else:
                p = re.compile('([\[\(])([\w.\*]+)(?:-([\w.\*]+))?([\]\)])')
                match = p.search(line)
                
                if match:
                    # see if we are dealing with a temporary redirect:
                    is_temp = False
                    if (line.split(' ')[0] == 'temporary'):
                        is_temp = True
                    
                    # some more regex hieroglyphs to get the old and new redirect urls:
                    old_url = None
                    new_url = None
                    
                    url_pat = re.compile(':(?:[ \t\f\v])(.*)(?:[ \t\f\v]->)(.*)')
                    url_match = url_pat.search(line)
                    
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
                                            for x in range (begin_index + 1, len(versions)):
                                                version = versions[x]
                                            
                                                r = generate_rule(is_temp, version, old_url, new_url)
                                            
                                                rules.append(r)
                                    
                                        # right version is a number, not *
                                        # (v2 - v3
                                        else:
                                            end_index = versions.index(match.group(3))
                                        
                                            # non-inclusive end_index
                                            # (v2 - v3)
                                            if match.group(4) == ')':
                                                
                                                # make sure we are actually including at least one version:
                                                if begin_index == end_index:
                                                    raise ValueError('ERROR: No versions included in line ' + str(line_num))
                                                
                                                else:
                                                    for x in range (begin_index + 1, end_index):
                                                        version = versions[x]
                                                
                                                        r = generate_rule(is_temp, version, old_url, new_url)
                                                
                                                        rules.append(r)
                                                
                                            # inclusive end_index
                                            # (v2 - v3]
                                            if match.group(4) == ']':
                                                for x in range (begin_index + 1, end_index + 1):
                                                    version = versions[x]
                                                
                                                    r = generate_rule(is_temp, version, old_url, new_url)
                                                
                                                    rules.append(r)
                                            
                            
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
                                                for x in range (0, end_index):
                                                    version = versions[x]
                                        
                                                    r = generate_rule(is_temp, version, old_url, new_url)
                                        
                                                    rules.append(r)
                                        
                                            # [* - v3]
                                            elif (match.group(4) == ']'):
                                                for x in range (0, end_index + 1):
                                                    version = versions[x]
                                        
                                                    r = generate_rule(is_temp, version, old_url, new_url)
                                        
                                                    rules.append(r)
                                
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
                                                for x in range (begin_index, len(versions)):
                                                    version = versions[x]
                                                
                                                    r = generate_rule(is_temp, version, old_url, new_url)
                                                
                                                    rules.append(r)
                                    
                                        # right version is a number, not *
                                        else:
                                            end_index = versions.index(match.group(3))
                                        
                                            # non-inclusive end_index
                                            # [v2 - v3)
                                            if match.group(4) == ')':
                                                for x in range (begin_index, end_index):
                                                    version = versions[x]
                                                
                                                    r = generate_rule(is_temp, version, old_url, new_url)
                                                
                                                    rules.append(r)
                                            
                                            # inclusive end_index
                                            # [v2 - v3]
                                            elif match.group(4) == ']':
                                                for x in range (begin_index, end_index + 1):
                                                    version = versions[x]
                                                
                                                    r = generate_rule(is_temp, version, old_url, new_url)
                                                
                                                    rules.append(r)
                    
                        # only one version number provided
                        # [v2]                        
                        elif not match.group(3):
                            
                            version = match.group(2)
                        
                            r = generate_rule(is_temp, version, old_url, new_url)
                        
                            rules.append(r)
    
    # write all our rules to the file    
    write_to_file(rules, output)
                                                
def main() -> None:
    """Main entry point for mut redirects to create .htaccess file."""
    options = docopt(__doc__)
    source_path = options['<source_path>']
    output = options['--output']
    
    # Parse source_path and write to file
    parse_source_file(source_path, output)

if __name__ == "__main__":
    main()
