"""
Usage:
    mut-convert-redirects --config CONFIG [-o PATH <files> -f NAME...]

    -h, --help              List CLI prototype, arguments, and options.
    --config CONFIG         Config file for redirect transformation.
    -f NAME...              Runs only configs that have `name` equal to NAME.
    -o PATH                 Output path
    <files>                 Path to the directory containing html files.
"""
import re
from typing import List, NamedTuple
from collections import defaultdict

from docopt import docopt
import yaml

REDIRECTS_DIR = '/Users/nick/mongodb/mut/mut/convert_redirects/htaccess/'

Output = NamedTuple('Output', [
    ('version', str),
    ('branch', str),
    ('old_prefix', str),
    ('new_prefix', str)
])
Pragma = NamedTuple('Pragma', [
    ('type', str),
    ('key', str),
    ('value', str)
])


def is_version_number(s):
    try:
        int(s[0])
        return True
    except ValueError:
        return False


def transform_version_rule(rule: str, pragmas) -> str:
    """Transform a giza-style version rule to a mut-style version rule."""
    symlinks = [tuple(''.join(p.split(' ')[1:]).split('->'))
                for p in pragmas
                if p.split(' ')[0] == 'symlink:']
    symlinks = {link: original for (link, original) in symlinks}
    if rule == 'all':
        return '[*]'
    else:
        match = re.match(r'((?:after)|(?:before)|)-?(.*)', rule)
        if match:
            predicate = match.group(1)
            version = match.group(2)
            templates = {
                'before': '[*-{}]',
                'after': '({}-*]',
            }
            template = templates[predicate] if predicate in templates else '[{}]'
            if version in symlinks:
                version = 'v'+symlinks[version].lstrip('v')
            return template.format(version)
        else:
            return False


def parse_output(output, property_name, pragmas, versions) -> List[Output]:
    """Return the output prefixes and version, if specified."""
    version = 'raw'
    old_prefix = ''
    new_prefix = ''
    branch = ''
    if isinstance(output, str) and versions:
        version = transform_version_rule(output, pragmas)
    elif isinstance(output, dict):
        output = list(output.items())[0]  # Converts dict to tuple
        if isinstance(output[1], dict):
            if versions:
                version = transform_version_rule(output[0], pragmas)
            output = list(output[1].items())[0]
        if isinstance(output[1], str):
            old_prefix = output[0].lstrip('/')
            new_prefix = output[1].lstrip('/')
            if len(old_prefix):
                parts = old_prefix.split('/')
                p = [pragma for pragma in pragmas if re.match(r'symlink.*', pragma)]
                syms = [re.match(r'(?:symlink:\s)(.*)(?:\s->.*)', s).group(1)
                        for s in p]
                if parts[0] == property_name and property_name not in syms:
                    branch = parts[0]
                    del parts[0]
                if parts and re.match(r'(v.*)', parts[-1]):
                    version = transform_version_rule(parts[-1], pragmas)
                    del parts[-1]
                if len(parts):
                    parts[0] = '/' + parts[0].lstrip('/')
                old_prefix = '/'.join(parts)

    return Output(version, branch, old_prefix, new_prefix)


def create_pragmas(base: str, versions: [str], symlinks: [str]) -> List[str]:
    """Create defines and symlink expressions."""
    # Defines
    defines = [Pragma(type='define', key='base', value=base)]
    if versions:
        for i, v in enumerate(versions):
            if isinstance(v, str) and is_version_number(v):
                versions[i] = 'v' + v
        ver = ' '.join(
            sorted(['v' + str(v) for v in versions if isinstance(v, float)]) +
            sorted([v for v in versions if isinstance(v, str)])
        )
        defines.append(Pragma('define', 'versions', ver))

    # Symlinks
    symlinks = [] if not symlinks else [Pragma(type='symlink', key='', value=s)
                                        for s in symlinks]

    # Pragma assembly
    def format_pragma(pragma):
        template = ''
        if pragma.type == 'define':
            template = '{type}: {key} {value}'
        elif pragma.type == 'symlink':
            template = '{type}: {value}'
        return template.format(type=pragma.type,
                               key=pragma.key,
                               value=pragma.value)

    pragmas = defines + symlinks
    return [format_pragma(p) for p in pragmas]


def get_rule_versions(cfg):
    try:
        rule_versions = cfg['versions'].copy()
        rule_versions.extend([
            sym.split(' -> ')[0] for sym in cfg.get('symlinks')])
        return rule_versions
    except KeyError:
        return []


def filter_rules(rules: list):
    def not_only_classic(rule: dict):
        if rule.get('edition'):
            r = rule.get('edition')
            if not isinstance(r, list):
                r = [r]
            if not [x for x in r if x in ['cloud', 'onprem']]:
                return False
        return True
    return [x for x in rules if not_only_classic(x)]


def tidy_output_versions(otp, rule_versions):
    if not isinstance(otp, list):
        outs = [otp]
    else:
        outs = [op for op in otp]
    if len(outs) > 1:
        print('\n\nmultiple outs!!!', otp, '\n')
    dict_style_rule = all([isinstance(o, dict) and len(o) == 1 for o in outs])

    if dict_style_rule:
        outputs = [list(o.items())[0] for o in outs]




        def only_versions(verlist, versions):
            return [v for v in verlist if v in versions]

        def output_match(v):
            v = str(v)
            is_all_versions = v == 'all'
            version = re.match(r'((?:after)|(?:before)|)-?(.*)', v)
            return any([is_all_versions, version.group(0)])

        version_outputs = [v for v in rule_versions if output_match(v)]
            # v is 'all' or re.match(r'((?:after)|(?:before)|)-?(.*)', v)
            # for v in rule_versions



        # return (outputs == [
        #         {
        #     'after-v2.0'
        #         },
        #         { ... }
        # ])
    return None



def process_rule(rule: dict, base: str, cfg: dict, pragmas: List[str]):
    rule["from"] = '/' + rule["from"].lstrip('/')
    isTemporary = str(rule.get("code")) in ['302', '303']
    rules = []
    rule_versions = get_rule_versions(cfg) # Specified version and symlink names
    # new_outputs = tidy_output_versions(rule['outputs'], rule_versions)

    for output in rule['outputs']:
        o = parse_output(output, cfg["name"], pragmas, rule_versions)

        # Detect if rule applies to many contiguous versions
        #if o.version not in output_versions:
            #output_versions.append(o.version)
        # todo: make this actually work

        if re.match(re.escape(base) + r"*", o.new_prefix):
            o = o._replace(new_prefix=o.new_prefix[len(base):])
        if o.version == 'raw':
            f = '' if not o.branch else o.branch
            t = '${base}' if not re.match(r'http*', o.new_prefix) else ''
        else:
            f = '/${version}'if not o.branch else o.branch + '/${version}'
            t = '${base}/${version}' if not re.match(
                r'http*', o.old_prefix) else ''

        f += '/'.join([o.old_prefix, rule['from'].lstrip('/')]
                      ) if o.old_prefix else rule['from']
        t = t if not re.match(r'https://.*', rule['to']) else ''
        t += o.new_prefix + rule['to'] if o.new_prefix else rule['to']
        #if re.match(r'https://docs.mongodb.com', base):
            # rules.append('{}/{}: {} -> {}'.format(cfg.get('name'),
            #                                       o.version, f, t))

            # For adding the property name back to the start of the from base
            # print('{}: {}{} -> {}'.format(o.version,
            #                               '/'+cfg.get('name')+'/',
            #                               f.lstrip('/'), t))
        #else:
        rules.append('{}: {} -> {}'.format(o.version, f, t))
    return '\n'.join(rules)


def convert_files(base: str, **cfg) -> List[str]:
    """Convert a giza-style redirect file to a list of mut-style rules."""
    files = [f for f in cfg['file']] if isinstance(cfg['file'], list) else [cfg.get('file')]
    redirects = []
    for file in files:
        with open(REDIRECTS_DIR + file, 'r') as f:
            redirects.extend(filter_rules(list(yaml.safe_load_all(f))))
    pragmas = create_pragmas(base, cfg.get('versions'), cfg.get('symlinks'))
    rules = [process_rule(rule=rule, base=base, cfg=cfg, pragmas=pragmas)
             for rule in redirects if rule]
    result = '\n'.join(pragmas + [''] + rules)
    return result


def main() -> None:
    options = docopt(__doc__)
    with open(options['--config'], 'r') as f:
        config = list(yaml.safe_load_all(f))
        if options['-f']:
            config = [cfg for cfg in config if cfg['name'] in options['-f']]
    for cfg in config:
        print(cfg.get('name'))
        cfg['base'] = cfg.get('base').rstrip('/')
        result = convert_files(**cfg)
        if cfg['output']:
            with open('/Users/nick/mongodb/mut/mut/convert_redirects/results/'+cfg['output'], 'w') as f:
                f.write(result)
        else:
            print(result)


if __name__ == '__main__':
    main()
