"""A source transformation that renders and tests blocks of source code for
   various languages.

   Takes YAML files with the 'exercise' prefix, and outputs codeblocks into
   files at source/includes/exercise/<ref>-<language>.rst."""
import logging
import os
import os.path
import subprocess

from typing import *
import rstcloth.rstcloth

import mut

__all__ = ['PREFIXES', 'run']

PREFIXES = ['exercise']

logger = logging.getLogger(__name__)


class ExerciseInputError(mut.MutInputError):
    @property
    def plugin_name(self) -> str:
        return 'exercise'


class ExerciseConfig:
    def __init__(self, root_config: mut.RootConfig) -> None:
        self.root_config = root_config
        self.exercises = []  # type: List['Exercise']

    def register(self, exercise: 'Exercise') -> None:
        self.exercises.append(exercise)

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for exercise in self.exercises:
            exercise.output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'exercise')


class Exercise:
    def __init__(self, ref: str, path: str, config: ExerciseConfig) -> None:
        self.ref = ref
        self.root = os.path.dirname(path)
        self.path = os.path.basename(path)

        self.language = ''
        self.src_path = ''
        self.test_command = ''

        self.config = config
        self.config.register(self)

    def run_test(self) -> None:
        if not self.test_command:
            return

        subprocess.check_output(self.test_command,
                                stderr=subprocess.STDOUT,
                                shell=True,
                                cwd=self.root)

    def output(self) -> None:
        try:
            self.run_test()
        except subprocess.CalledProcessError as err:
            warning = ExerciseInputError(self.path, self.ref, 'Failed Test')
            warning.verbose = str(err.output, 'utf-8')
            self.config.root_config.warn(warning)

        try:
            with open(self.src_path) as f:
                code = f.read().strip()
        except OSError as err:
            msg = 'Could not open ' + self.src_path
            raise ExerciseInputError(self.path, self.ref, msg)

        cloth = rstcloth.rstcloth.RstCloth()
        cloth.directive(name='code-block',
                        arg=self.language,
                        wrap=False)
        cloth.newline()
        cloth.content(code, wrap=False, indent=3)

        cloth.write(self.output_path)

    @property
    def output_path(self) -> str:
        return os.path.join(self.config.output_path, self.ref) + '.rst'

    @classmethod
    def load(cls,
             ref: str,
             language: str,
             value: Dict[str, Any],
             path: str,
             config: ExerciseConfig) -> 'Exercise':
        exercise = cls(ref, path, config)  # type: Exercise

        exercise.language = language
        src_path = mut.withdraw(value, 'src', str)
        exercise.test_command = mut.withdraw(value, 'test-command', str)

        if not src_path:
            raise ExerciseInputError(path, ref, 'Missing "src"')

        exercise.src_path = config.root_config.get_root_path(src_path)

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            raise ExerciseInputError(path, ref, msg)

        return exercise

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def str_dict_dict(value: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """Verifies dictionaries of string dictionaries."""
    return dict([(str(v[0]), mut.str_dict(v[1])) for v in value.items()])


def load_exercises(value: Dict[str, Any], path: str, config: ExerciseConfig) -> List['Exercise']:
    ref = mut.withdraw(value, 'ref', str)
    if not ref:
        raise ExerciseInputError(path, ref, 'Missing "ref"')

    languages = mut.withdraw(value, 'languages', str_dict_dict)
    return [Exercise.load('{}-{}'.format(ref, language), language, value, path, config) for
                         (language, value) in languages.items()]


def run(root_config: mut.RootConfig, paths: List[str]) -> List[mut.MutInputError]:
    logger.info('Exercises')
    config = ExerciseConfig(root_config)
    for path in paths:
        with open(path, 'r') as f:
            raw_exercises = mut.load_yaml(path)
            [load_exercises(raw, path, config) for raw in raw_exercises]

    config.output()
    return root_config.warnings
