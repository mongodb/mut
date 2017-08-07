'''Print a header summarizing the index arguments.'''


def print_intro_message(root, output, url, include_in_global_search):
    '''Print the intro header.'''
    print('\n### Generating Index Manifest\n')
    lines = {
        "file": output,
        "root": root,
        "url": url,
        "global": 'True' if include_in_global_search else 'False'
    }
    justify = max([len(key) for key, _ in lines.items()]) + 1

    def format_line(label, data):
        '''Return a properly formatted intro message line.'''
        label = '{}:'.format(label).rjust(justify, " ")
        return ' '.join([label, str(data)])
    output = [format_line(label, data)
              for label, data
              in lines.items()]
    print('\n'.join(output), '\n')
