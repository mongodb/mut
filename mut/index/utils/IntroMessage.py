'''Print a header summarizing the index arguments.'''
from typing import List


def print_intro_message(root: str, exclude: List[str], output: str,
                        aliases: List[str], url: str, include_in_global_search: bool) -> None:
    '''Print the intro header.'''
    print('\n### Generating Index Manifest\n')
    lines = {
        'file': output,
        'aliases': str(aliases),
        'root': root,
        'exclude': str(exclude),
        'url': url,
        'global': 'True' if include_in_global_search else 'False'
    }
    justify = max([len(key) for key, _ in lines.items()]) + 1

    def format_line(label: str, data: str) -> str:
        '''Return a properly formatted intro message line.'''
        label = '{}:'.format(label).rjust(justify, " ")
        return ' '.join([label, str(data)])
    intro_message = [format_line(label, data)
                     for label, data
                     in lines.items()]
    print('\n'.join(intro_message), '\n')
