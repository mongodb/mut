import abc

__version__ = '0.4.dev0'


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


class MutYAMLError(Exception):
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return self.message
