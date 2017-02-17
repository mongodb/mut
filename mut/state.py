import abc
from typing import Dict


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
