import abc
import os.path

import rstcloth.rstcloth
import libgiza.git
import yaml
from typing import Any, Callable, Dict, List, TypeVar, Union

__all__ = ['substitute', 'withdraw', 'str_or_list', 'str_dict', 'load_yaml',
           'State', 'MutInputError', 'RootConfig']

T = TypeVar('T')


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
    for src, dest in replacements.items():
        text = text.replace('{{{{{}}}}}'.format(src), dest)

    return text


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
    with open(path, 'r') as f:
        return list(yaml.load_all(f, Loader=yaml.CLoader))


class State(metaclass=abc.ABCMeta):
    """Base class for inheritable state objects, such as would represent an
       input element's attributes."""
    @abc.abstractproperty
    def replacements(self) -> Dict[str, str]:
        """Return a dictionary mapping template replacements."""
        pass

    @abc.abstractproperty
    def ref(self) -> str:
        """Return a string uniquely identifying this element."""
        pass

    @abc.abstractproperty
    def keys(self) -> List[str]:
        """Return a list of attributes in this State class that will inherit
           from a parent object."""
        pass

    def inherit(self, other: 'State') -> None:
        """Inherit properties from a parent State instance."""
        for key in [k for k in other.keys if getattr(self, k) is None]:
            setattr(self, key, getattr(other, key))

        for src, dest in other.replacements.items():
            if src not in self.replacements:
                self.replacements[src] = dest

    def __str__(self) -> str:
        d = {}
        for k in self.keys:
            d[k] = getattr(self, k)

        return str(d)


class MutInputError(Exception, metaclass=abc.ABCMeta):
    """Base class for reporting malformed input files."""
    def __init__(self, path: str, ref: str, message: str, verbose: str='') -> None:
        self._path = path
        self._ref = ref
        self._message = message
        self.verbose = verbose

    @abc.abstractproperty
    def plugin_name(self) -> str:
        """Return the name of the transform plugin that reported this error."""
        pass

    @property
    def path(self) -> str:
        """Return the filename in which this error occurred."""
        return self._path

    @property
    def ref(self) -> str:
        """Return a plugin-defined item reference in which this error occurred."""
        return self._ref

    def __str__(self) -> str:
        """Return a human-readable message."""
        return self._message


class RootConfig:
    """The root configuration giving project-wide configuration details."""
    def __init__(self, root: str, edition: str) -> None:
        self.repo = libgiza.git.GitRepo()
        self.branch = self.repo.current_branch()
        self.commit = self.repo.sha()

        self.root_path = os.path.abspath(root)
        self.source_path = os.path.join(self.root_path, 'source')
        self.includes_path = os.path.join(self.source_path, 'includes')

        output_suffix = '' if not edition else '-' + edition
        self.output_path = os.path.join(self.root_path, 'build', self.branch + output_suffix)
        self.output_source_path = os.path.join(self.output_path, 'source')

        self.warnings = []  # type: List[MutInputError]
        self.n_workers = 1

    def get_absolute_path(self, root: str, relative_path: str) -> str:
        """Transform a path rooted at the start of a directory into a
           real filesystem path."""
        if relative_path.startswith('/'):
            relative_path = relative_path[1:]

        return os.path.join(root, relative_path)

    def get_root_path(self, relative_path: str) -> str:
        """Transform a path rooted at the start of the project root
           directory into a real filesystem path."""
        return self.get_absolute_path(self.root_path, relative_path)

    def get_output_source_path(self, relative_path: str) -> str:
        """Transform a path rooted at the start of the output source
           directory into a real filesystem path."""
        return self.get_absolute_path(self.output_source_path, relative_path)

    def warn(self, warning: MutInputError) -> None:
        """Report a non-fatal warning."""
        self.warnings.append(warning)
