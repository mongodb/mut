import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth

import mut

__all__ = ['PREFIXES', 'run']

LEVEL_CHARACTERS = {
    '=': 1,
    '-': 2,
    '~': 3,
    '`': 4,
    '^': 5,
    '\'': 6
}

CHARACTER_LEVELS = dict(zip(LEVEL_CHARACTERS.values(),
                            LEVEL_CHARACTERS.keys()))

PREFIXES = ['steps']

logger = logging.getLogger(__name__)


class StepsConfig:
    def __init__(self, root_config: mut.RootConfig) -> None:
        self.root_config = root_config
        self.steps = {}  # type: Dict[str, Step]
        self.final_steps = []  # type: List[StepsList]

    def register_step_list(self, steps: 'StepsList') -> None:
        self.final_steps.append(steps)

        for step in steps.steps:
            self._register_step(step)

    def get_step(self, path: str, ref: str) -> 'Step':
        return self.steps[self.step_global_id(path, ref)]

    def output(self) -> None:
        try:
            os.makedirs(self.output_path)
        except FileExistsError:
            pass

        for step_list in self.final_steps:
            step_list.output()

    @property
    def output_path(self) -> str:
        return os.path.join(self.root_config.output_path, 'source', 'includes', 'steps')

    @staticmethod
    def step_global_id(path: str, ref: str) -> str:
        return '{}#{}'.format(path, ref)

    def _register_step(self, step: 'Step') -> None:
        step_id = self.step_global_id(step.path, step.ref)
        if step_id in self.steps:
            raise ValueError('Already registered')

        self.steps[step_id] = step


class Action:
    def __init__(self):
        self.heading = ''
        self.heading_char = None  # type: str

        self.pre = ''
        self.language = None
        self.code = ''
        self.content = ''
        self.post = ''

    def render(self, indent: int, level: int, cloth: rstcloth.rstcloth.RstCloth) -> None:
        if self.heading:
            heading_char = self.heading_char if self.heading_char is not None \
                                             else CHARACTER_LEVELS[level]

            if level in (0, 1):
                cloth.title(text=self.heading,
                            char=heading_char,
                            indent=indent)
            else:
                cloth.heading(text=self.heading,
                              char=heading_char,
                              indent=indent)
            cloth.newline()

        if self.pre:
            cloth.content(content=self.pre,
                          indent=indent,
                          wrap=False)
            cloth.newline()

        if self.code:
            cloth.directive(name='code-block',
                            arg=self.language,
                            indent=indent,
                            content=self.code,
                            wrap=False)
            cloth.newline()

        if self.content:
            cloth.content(content=self.content,
                          indent=indent,
                          wrap=False)
            cloth.newline()

        if self.post:
            cloth.content(content=self.post,
                          indent=indent,
                          wrap=False)
            cloth.newline()

    @classmethod
    def load(cls, value: Any) -> 'Action':
        action = cls()  # type: Action

        if isinstance(value, str):
            action.content = value
            return action

        raw_heading = value.get('heading', '')
        if isinstance(raw_heading, str):
            action.heading = raw_heading
        else:
            action.heading = raw_heading['text']
            action.heading_char = raw_heading.get('character', None)

        action.pre = value.get('pre', '')
        action.language = value.get('language', '')
        action.code = value.get('code', '')
        action.content = value.get('content', '')
        action.post = value.get('post', '')
        return action


class Step:
    def __init__(self, ref: str, path: str, config: StepsConfig) -> None:
        self.ref = ref
        self.path = path
        self.config = config

        self.pre = ''
        self.orig_content = ''
        self.actions = []  # type: List[Action]
        self.post = ''

        self.inherit = None  # type: Tuple[str, str]
        self.title = ''
        self.level = 2

    def render(self, indent: int, cloth: rstcloth.rstcloth.RstCloth) -> None:
        """Render this step's contents into the given RstCloth instance."""
        # Apply pre
        if self.pre:
            cloth.content(self.pre, indent=indent, wrap=False)
            cloth.newline()

        if self.inherit is not None:
            source_path, source_id = self.inherit
            source = self.config.get_step(source_path, source_id)
            source.render(indent, cloth)

        for action in self.actions:
            action.render(indent, self.level + 1, cloth)
            cloth.newline()

        if self.orig_content:
            cloth.content(self.orig_content, indent=indent, wrap=False)
            cloth.newline()

        # Apply post
        if self.post:
            cloth.content(self.post, indent=indent, wrap=False)
            cloth.newline()

    @classmethod
    def load(cls, value: Any, path: str, config: StepsConfig) -> 'Step':
        inherit = value.get('inherit', None) or value.get('source', None)

        ref = value.get('ref', None)
        if ref is None:
            ref = inherit.get('ref') if inherit else None
        if ref is None:
            raise KeyError('ref: {}'.format(path))

        step = cls(ref, path, config)  # type: Step
        step.pre = value.get('pre', '')
        step.post = value.get('post', '')

        title = value.get('title', '')
        if isinstance(title, str):
            step.title = title
        else:
            step.title = str(title['text'])
            if 'character' in title:
                step.level = LEVEL_CHARACTERS[title['character']]

        step.level = int(value.get('level', step.level))
        step.orig_content = value.get('content', '')
        raw_actions = value.get('action', [])
        if isinstance(raw_actions, str) or isinstance(raw_actions, dict):
            step.actions = [Action.load(raw_actions)]
        else:
            step.actions = [Action.load(raw_action) for raw_action in raw_actions]

        if inherit:
            step.inherit = (inherit['file'], inherit['ref'])

        return step

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


class StepsList:
    def __init__(self, steps: List[Step], path: str, config: StepsConfig) -> None:
        self.ref = os.path.splitext(os.path.basename(path))[0]
        self.path = path
        self.config = config

        self.steps = steps
        config.register_step_list(self)

    def output(self) -> None:
        cloth = rstcloth.rstcloth.RstCloth()
        header_html = ('<div class="sequence-block">'
                       '<div class="bullet-block">'
                       '<div class="sequence-step">'
                       '{0}'
                       '</div>'
                       '</div>')

        for step_number, step in enumerate(self.steps):
            step_number += 1

            cloth.directive('only', 'html or dirhtml or singlehtml')
            cloth.newline()

            cloth.directive(name='raw',
                            arg='html',
                            content=header_html.format(step_number),
                            indent=3)
            cloth.newline()

            if step.title:
                cloth.heading(text=step.title,
                              char=CHARACTER_LEVELS[step.level],
                              indent=3)
                cloth.newline()

            step.render(3, cloth)

            cloth.directive(name='raw',
                            arg='html',
                            content='</div>',
                            indent=3)
            cloth.newline()

            cloth.directive('only', 'latex or epub')
            cloth.newline()

            if step.title:
                cloth.heading(text='Step {0}: {1}'.format(step_number, step.title),
                              char=CHARACTER_LEVELS[step.level],
                              indent=3)
                cloth.newline()
            else:
                cloth.heading(text='Step {0}'.format(step_number),
                              char=CHARACTER_LEVELS[step.level],
                              indent=3)
                cloth.newline()

            step.render(3, cloth)

        cloth.write(self.output_path)

    @property
    def output_path(self) -> str:
        bare_ref = self.ref.replace('steps-', '', 1)
        return os.path.join(self.config.output_path, bare_ref) + '.rst'

    @classmethod
    def load(cls, values: List[Any], path: str, config: StepsConfig) -> 'StepsList':
        filename = os.path.basename(path)
        steps = [Step.load(v, filename, config) for v in values]
        return cls(steps, filename, config)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def run(root_config: mut.RootConfig, paths: List[str]):
    logger.info('Steps')
    config = StepsConfig(root_config)
    for path in paths:
        raw_steps = mut.load_yaml(path)
        StepsList.load(raw_steps, path, config)

    config.output()
