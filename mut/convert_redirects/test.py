import os
import subprocess
from termcolor import colored
import re

mutdir = os.path.expanduser('~/mongodb/mut/mut/')
rdr = 'python3 ~/mongodb/mut/mut/redirects/redirect_main.py'
directory = {
    "atlas": "cloud-docs",
    "compass": "docs-compass",
    "ecosystem": "docs-ecosystem",
    "server": "docs",
    "spark": "docs-spark-connector",
    "stitch": "baas-docs",
    "bi-connector": "docs-bi-connector",
    "cloud-manager": "mms-docs",
    "ops-manager": "mms-docs",
}


def mutpath(p='', c=None):
    return '/'.join([mutdir.rstrip('/'), p.lstrip('/')])


def term(*args, pwd=None, name=None):
    def _report(msgtype, std):
        t = {
            'Error': 'red',
            'Output': 'green'
        }
        x = ['{}:\n',
             '\n'.join(['\t' + l for l in std.decode('ascii').split('\n')])]
        print(colored(''.join(x).format(msgtype), color=t[msgtype]))

    call = ' '.join(['cd', pwd + ';',
                     'giza generate redirects -p >',
                     mutpath('/convert_redirects/tests/old/{}').format(name)+';',
                     ' '.join([str(part) for part in list(args)])
                    ])
    proc = subprocess.Popen(call, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    if err:
        _report('Error', err)
    if out:
        _report('Output', out)


def heading(h):
    return '\n'.join(['', '-' * len(h), h, '-' * len(h), ''])


def generate_redirects(dirpath):
    def full_path(filepath):
        return '/'.join([dirpath.rstrip('/'), filepath])

    for arrow_syntax_file in [full_path(f) for f in os.listdir(dirpath)]:
        name = re.sub(r'-results.txt', '',
                      arrow_syntax_file.split('/')[-1])
        print(heading(name))
        term(rdr, arrow_syntax_file,
             '-o', mutpath('convert_redirects/tests/new/'+name),
             pwd='/Users/nick/mongodb/'+directory.get(name),
             name=name
             )


def compare_redirects(testdir):
    new_dir = '/'.join([testdir.rstrip('/'), 'new/'])
    old_dir = '/'.join([testdir.rstrip('/'), 'old/'])
    new_redirects = [new_dir+filename for filename in os.listdir(new_dir)]
    old_redirects = [old_dir+filename for filename in os.listdir(old_dir)]
    new_redirects.sort()
    old_redirects.sort()

    redirects = zip(new_redirects, old_redirects)
    print(list(redirects))



if __name__ == "__main__":
    #generate_redirects(mutpath('convert_redirects/results'))
    compare_redirects(mutpath('convert_redirects/tests'))
