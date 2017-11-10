import os.path
import re

import yaml
import rstcloth.rstcloth
from typing import Any, Callable, Dict, List, TypeVar, Union, Iterable

import mut

T = TypeVar('T')
PAT_SUBSTITUTION = re.compile(r'{{(.+?)}}')
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


def substitute(text: str, replacements: Dict[str, str]) -> str:
    """Quick-and-dirty template substitution function."""
    return PAT_SUBSTITUTION.sub(lambda match: replacements[match.group(1)], text)


def substitute_rstcloth(cloth: rstcloth.rstcloth.RstCloth,
                        replacements: Dict[str, str]) -> str:
    return substitute('\n'.join(cloth.data), replacements)


def withdraw(dictionary: Dict[str, Any], key: str, checker: Callable[[Any], T], default: T=None) -> T:
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


def str_or_list(value: Union[List[str], str]) -> str:
    """Coerces a string or list of strings into a string."""
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return ', '.join(value)

    raise TypeError(value)


def string_list(value: Union[List[str], str]) -> List[str]:
    """Coerces a string or list of strings into a list of strings."""
    if isinstance(value, str):
        return [value]

    return [str(x) for x in value]


def str_dict(value: Dict[str, str]) -> Dict[str, str]:
    """Transforms a dictionary into a dictionary mapping strings to strings."""
    return dict([(str(v[0]), str(v[1]) if v[1] is not None else None) for v in value.items()])


def str_any_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a dictionary into a dictionary mapping strings to anything."""
    return dict([(str(v[0]), v[1] if v[1] is not None else None) for v in value.items()])


def list_str_any_dict(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transforms a list of dictionaries into a list of dictionaries
       mapping strings to anything."""
    return [str_any_dict(x) for x in values]


def load_yaml(path: str) -> List[Dict[str, Any]]:
    """Open a file and parse the YAML within."""
    try:
        with open(path, 'r') as f:
            return list(yaml.load_all(f, Loader=yaml.CLoader))
    except yaml.error.YAMLError as error:
        raise mut.MutYAMLError(path, str(error)) from error


def save_if_changed(text: str, path: str) -> bool:
    """Write text to a path only if its contents are not equal to said text."""
    try:
        with open(path, 'r') as f:
            data = f.read()
            if data == text:
                return False
    except FileNotFoundError:
        pass

    with open(path, 'w') as f:
        f.write(text)

    return True


def save_rstcloth_if_changed(cloth, path: str) -> bool:
    return save_if_changed('\n'.join(cloth.data) + '\n', path)


def save_rstcloth_table_if_changed(table_builder, path: str) -> bool:
    return save_if_changed('\n'.join(table_builder.output), path)


def color(message: str, options: Iterable[str]) -> str:
    composite = []
    for option in options:
        composite.append('{0}'.format(VT100[option]))
    return '\x1b[{0}m{1}\x1b[0m'.format(';'.join(composite), message)
