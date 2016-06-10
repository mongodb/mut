import importlib.util


class Config:
    def __init__(self, path: str) -> None:
        spec = importlib.util.spec_from_file_location('conf', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    @property
    def rst_epilog(self) -> str:
        """A string that is appended to the end of every rst file. Useful for
           replacements. Defaults to an empty string."""
        return str(self.get('rst_epilog', ''))

    @property
    def source_suffix(self) -> str:
        """The file extension used for source files. Defaults to ".txt"."""
        return str(self.get('source_suffix', '.txt'))

    def get(self, key: str, default: object) -> object:
        try:
            return self[key]
        except AttributeError:
            return default

    def __getitem__(self, key: str) -> object:
        return getattr(self.module, key)
