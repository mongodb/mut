"""
Usage:
    rdr-test [-f NAME...]

    -f NAME...  Runs only configs that have `name` equal to NAME.
"""
import os
import subprocess
from functools import namedtuple
from termcolor import colored
import re
from docopt import docopt

Uniques = namedtuple('Uniques', ['new', 'old'])
mutdir = os.path.expanduser('~/mongodb/mut/mut/')
rdr = 'python3 ~/mongodb/mut/mut/redirects/redirect_main.py'
directory = {
    "atlas": "cloud-docs",
    "compass": "docs-compass",
    "ecosystem": "docs-ecosystem",
    "manual": "docs",
    "spark-connector": "docs-spark-connector",
    "stitch": "baas-docs",
    "bi-connector": "docs-bi-connector",
    "cloud-manager": "mms-docs",
    "ops-manager": "mms-docs",
}
options = docopt(__doc__)
current_properties = options['-f'] if options['-f'] else [k for k in directory.keys()]
filename_regex = re.compile(r'(?P<name>.*)(?:-results.txt)')

def convert_yaml_redirects():
    print(heading('Converting yaml redirects to new arrow syntax'))
    call = [
        'python3 ~/mongodb/mut/mut/convert_redirects/convert_redirects.py',
        '--config ~/mongodb/mut/mut/convert_redirects/redirect_config.yaml'
    ]
    if options['-f']:
        call.extend([' '.join(['-f', p]) for p in current_properties])
    os.system(' '.join(call))


def mutpath(p='', c=None):
    return '/'.join([mutdir.rstrip('/'), p.lstrip('/')])


def term(*args, pwd=None, name=None):
    call = ' '.join(['cd', pwd + ';',
                     'giza generate redirects -p >',
                     mutpath('/convert_redirects/tests/old/{}').format(name)+';',
                     ' '.join([str(part) for part in list(args)])
                    ])
    proc = subprocess.Popen(call, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    def _report(msgtype, std):
        t = {
            'Error': 'red',
            'Output': 'green'
        }
        x = ['{}:\n',
             '\n'.join(['\t' + l for l in std.decode('ascii').split('\n')])]
        print(colored(''.join(x).format(msgtype), color=t[msgtype]))
    if err:
        if re.match(r'INFO:giza.content.post.redirects:generating', err.decode('ascii')):
            print(colored(err.decode('ascii'), 'blue'))
        else:
            _report('Error', err)
    if out:
        _report('Output', out)


def heading(h):
    return '\n'.join(['', '-' * len(h), h, '-' * len(h), ''])


def generate_redirects(dirpath):
    print(heading('Generating new and old redirects'))
    def full_path(filepath):
        return '/'.join([dirpath.rstrip('/'), filepath])
    # print([f for f in os.listdir(dirpath)])
    for arrow_syntax_file in [full_path(f) for f in os.listdir(dirpath)
                              if filename_regex.match(f).group('name')
                              in current_properties]:
        name = re.sub(r'-results.txt', '',
                      arrow_syntax_file.split('/')[-1])
        print(name)
        term(rdr, arrow_syntax_file,
             '-o', mutpath('convert_redirects/tests/new/'+name),
             pwd='/Users/nick/mongodb/'+directory.get(name),
             name=name
             )
        with open(mutpath('convert_redirects/tests/old/' + name), 'r') as f:
            redirects = f.readlines()
            prettified_redirects = [line.rstrip() for line in redirects]
        with open(mutpath('convert_redirects/tests/old/' + name), 'w') as f:
            f.write('\n'.join(prettified_redirects))


def compare_redirects(testdir):
    print(heading('Comparing new and old redirects'))
    new_dir = '/'.join([testdir.rstrip('/'), 'new/'])
    old_dir = '/'.join([testdir.rstrip('/'), 'old/'])
    new_redirects = [new_dir+filename for filename in os.listdir(new_dir)
                     if filename in current_properties]
    old_redirects = [old_dir+filename for filename in os.listdir(old_dir)
                     if filename in current_properties]
    new_redirects.sort()
    old_redirects.sort()

    def get_file_content(f):
        with open(f, 'r') as file:
            return file.readlines()

    def tidy_redirect_line(line):
        try:
            old, new = tuple(line.strip().split(' '))
            old = old.rstrip('/') if old is not '/' else old
            new = new.rstrip('/') if new is not '/' else new
            return ' '.join([old, new])
        except:
            pass
        # if line != ' '.join([n.strip().rstrip('/') for n in line.split(' ')]) + '\n':
        #     if line.strip().rstrip('/')+'\n' != ' '.join([n.strip().rstrip('/') for n in line.split(' ')]) + '\n':
        #         print(line)
        #         print(' '.join([n.strip().rstrip('/')
        #                         for n in line.split(' ')]) + '\n')
        # print(' '.join([n.strip().rstrip('/')
        #                 for n in line.split(' ')]) + '\n' + '_')
        return ' '.join([n.strip().rstrip('/') for n in line.split(' ')]) + '\n'

    redirects = list(zip(new_redirects, old_redirects))
    redirects = [r for r in redirects
                 if r[0].split('/')[-1][0] is not '.']
    for rdr_files in redirects:
        name = rdr_files[0].split('/')[-1]
        n, o = tuple([get_file_content(file)
                      for file in rdr_files if file[0] is not '.'])
        new = set([tidy_redirect_line(line[13:])
                   for line in n
                   if line.startswith("Redirect")])
        old = set([tidy_redirect_line(line[13:])
                   for line in o
                   if line.startswith("Redirect")])

        print(colored('\n' + name, 'red' if len(new) != len(old) else 'green'))
        print(colored(' '.join([
            'new:', str(len(new)), 'old:', str(len(old)), 'differences:', str(len(old - new))
        ]), 'blue' if len(old-new) else 'green'))
        # print(colored('\n'.join(list(old-new)), 'blue'))
        if name in ['ops-manager']:
            with open(mutpath('convert_redirects/'+name+'-diff.txt'), 'w') as f:
                lines = '\n'.join([line for line in old-new])
                f.write(lines)


if __name__ == "__main__":
    convert_yaml_redirects()
    generate_redirects(mutpath('convert_redirects/results'))
    compare_redirects(mutpath('convert_redirects/tests'))
