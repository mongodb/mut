import os.path
import subprocess

from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, Iterable, NamedTuple

_T = TypeVar('_T')
VT100 = {
    'red': '31',
    'green': '32',
    'yellow': '33',
    'bright': '1'
}


def compare_mtimes(target: str, dependencies: List[str]) -> bool:
    """Return True if any of the dependency paths are newer than the target
       path. Otherwise returns False."""
    try:
        target_mtime = os.path.getmtime(target)
    except FileNotFoundError:
        return True

    dependencies_mtime = max([os.path.getmtime(dep) for dep in dependencies])
    return dependencies_mtime > target_mtime


def withdraw(dictionary: Dict[str, Any],
             key: str,
             checker: Callable[[Any], _T],
             default: Optional[_T] = None) -> Optional[_T]:
    """Removes a value from a dictionary, after transforming it with a given
       checker function. Returns either the value, or None if it does
       not exist."""
    try:
        value = dictionary[key]
    except KeyError:
        return default

    del dictionary[key]
    if value is None:
        return None

    return checker(value)


def str_any_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a dictionary into a dictionary mapping strings to anything."""
    return dict([(str(v[0]), v[1] if v[1] is not None else None) for v in value.items()])


def list_str_any_dict(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transforms a list of dictionaries into a list of dictionaries
       mapping strings to anything."""
    return [str_any_dict(x) for x in values]


def color(message: str, options: Iterable[str]) -> str:
    composite = []
    for option in options:
        composite.append('{0}'.format(VT100[option]))
    return '\x1b[{0}m{1}\x1b[0m'.format(';'.join(composite), message)


GitInfo = NamedTuple('GitInfo', (
    ('current_branch', str),
    ('sha', str),
    ('top_level', str)))


def git_learn() -> GitInfo:
    def run(args: List[str]) -> str:
        return subprocess.check_output(['git'] + args, universal_newlines=True).strip()

    current_branch = run(['rev-parse', '--abbrev-ref', 'HEAD'])
    sha = run(['rev-parse', '--verify', 'HEAD'])
    top_level = run(['rev-parse', '--show-toplevel'])
    return GitInfo(current_branch, sha, top_level)
