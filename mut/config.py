import os.path
import libgiza.git
import mut


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

        self.warnings = []  # type: List[mut.MutInputError]
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

    def warn(self, warning: mut.MutInputError) -> None:
        """Report a non-fatal warning."""
        self.warnings.append(warning)
