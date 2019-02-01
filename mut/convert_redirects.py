"""
Usage:
    mut-convert-redirects [-o PATH] <path>

    -h, --help              List CLI prototype, arguments, and options.
    -o PATH                 Output path
    <files>                 Path to the directory containing html files.
"""
import re
from typing import List

from docopt import docopt
import yaml


def transform_version_rule(rule: str) -> str:
    """Transform a giza-style version rule to a mut-style version rule."""
    if rule == 'all':
        return '[*]'

    match = re.match(r'((?:after)|(?:before)|)-?(.*)', rule)
    assert match
    if match.group(1) == 'after':
        return '({}-*]'.format(match.group(2))
    elif match.group(2) == 'before':
        return '(*-{}]'.format(match.group(2))

    return '[{}]'.format(match.group(2))


def convert_file(path: str) -> List[str]:
    """Convert a giza-style redirect file to a list of mut-style rules."""
    with open(path, 'r') as f:
        redirects = list(yaml.safe_load_all(f))

    result = []
    for rule in redirects:
        if not rule:
            continue

        for output in rule['outputs']:
            if isinstance(output, str):
                version = transform_version_rule(output)
                base_component = ''
            elif isinstance(output, dict):
                output = list(output.items())[0]

                if output[0][0] == '/':
                    version = 'raw'
                    base_component = output[0]
                else:
                    version = transform_version_rule(output[0])
                    base_component = output[1] if isinstance(output[1], str) \
                        else list(output[1].keys())[0]

            if version is 'raw':
                rule['from'] = '/'.join((base_component.rstrip('/'), rule['from'].lstrip('/')))
                rule['to'] = '/'.join((base_component.rstrip('/'), rule['to'].lstrip('/')))
            else:
                rule['from'] = '/'.join(
                    (base_component.rstrip('/'), r'${version}', rule['from'].lstrip('/')))
                rule['to'] = '/'.join(
                    (base_component.rstrip('/'), r'${version}', rule['to'].lstrip('/')))

            result.append('{}: {} -> {}'.format(version, rule['from'], rule['to']))

    return result


def main() -> None:
    options = docopt(__doc__)

    result = '\n'.join(convert_file(options['<path>']))
    if options['-o']:
        with open(options['-o'], 'w') as f:
            f.write(result)
    else:
        print(result)


if __name__ == '__main__':
    main()
