import logging
import os
import os.path

from typing import *
import rstcloth.rstcloth

import mut
import mut.config
import mut.state
import mut.util

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


def str_or_str_dict(value: Union[str, Dict[str, str]]) -> Union[str, Dict[str, str]]:
    if isinstance(value, str):
        return value

    return mut.util.str_dict(value)


def str_or_dict_to_list(items) -> List[Any]:
    if isinstance(items, str) or isinstance(items, dict):
        return [items]

    return list(items)


class StepsInputError(mut.MutInputError):
    @property
    def plugin_name(self) -> str:
        return 'steps'


class StepsConfig:
    def __init__(self, root_config: mut.config.RootConfig) -> None:
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
        return os.path.join(self.root_config.output_path,
                            'source',
                            'includes',
                            'steps')

    @staticmethod
    def step_global_id(path: str, ref: str) -> str:
        return '{}#{}'.format(path, ref)

    def _register_step(self, step: 'Step') -> None:
        step_id = self.step_global_id(step.path, step.state.ref)
        if step_id in self.steps:
            raise StepsInputError(step.path, step_id, 'Already registered')

        self.steps[step_id] = step


class Action:
    def __init__(self) -> None:
        self.heading = ''
        self.heading_char = None  # type: str

        self.pre = ''
        self.language = None  # type: str
        self.copyable = False
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

        if self.copyable and self.code:
            cloth.directive(name='class', arg='copyable-code', indent=indent)

        if self.code:
            cloth.directive(name='code-block',
                            arg=self.language,
                            indent=indent,
                            wrap=False)
            cloth.newline()
            cloth.content(self.code, wrap=False, indent=indent + 3)

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
        action.copyable = value.get('copyable', False)
        action.language = value.get('language', '')
        action.code = value.get('code', '')
        action.content = value.get('content', '')
        action.post = value.get('post', '')

        # Code and language only make sense when together
        if bool(action.code) != bool(action.language):
            raise ValueError('Step action must have either both "code" and ' +
                             '"language", or neither.')

        return action


class StepState(mut.state.State):
    DEFAULT_LEVEL = 3

    def __init__(self, ref: str) -> None:
        self._replacements = {}  # type: Dict[str, str]
        self._ref = ref

        self._content = None  # type: str
        self._level = None  # type: int
        self._post = None  # type: str
        self._pre = None  # type: str
        self._title = None  # type: str

        self._actions = None  # type: List[Action]

    @property
    def content(self) -> str:
        return self._content or ''

    @content.setter
    def content(self, content: str) -> None:
        self._content = content

    @property
    def level(self) -> int:
        return self._level or self.DEFAULT_LEVEL

    @level.setter
    def level(self, level: int) -> None:
        self._level = level

    @property
    def post(self) -> str:
        return self._post or ''

    @post.setter
    def post(self, post: str) -> None:
        self._post = post

    @property
    def pre(self) -> str:
        return self._pre or ''

    @pre.setter
    def pre(self, pre: str) -> None:
        self._pre = pre

    @property
    def title(self) -> str:
        return self._title or ''

    @title.setter
    def title(self, title: str) -> None:
        self._title = title

    @property
    def actions(self) -> List[Action]:
        return self._actions or []

    @actions.setter
    def actions(self, actions: List[Action]) -> None:
        self._actions = actions

    @property
    def replacements(self) -> Dict[str, str]:
        return self._replacements

    @property
    def ref(self) -> str:
        return self._ref

    @property
    def keys(self):
        return ['_actions', '_content', '_level', '_post', '_pre', '_title']


class Step:
    def __init__(self, ref: str, path: str, config: StepsConfig) -> None:
        self.path = path
        self.config = config

        self.state = StepState(ref)

        self._inherit = None  # type: Tuple[str, str]

    @property
    def parent(self) -> 'Step':
        if self._inherit is None:
            return None

        parent_path, parent_ref = self._inherit
        try:
            return self.config.get_step(parent_path, parent_ref)
        except KeyError:
            msg = 'Could not find Step "{}" to inherit from in "{}"'.format(parent_ref, parent_path)
            raise StepsInputError(self.path, self.state.ref, msg)

    def inherit(self) -> None:
        parent = self.parent
        if parent is None:
            return

        parent.inherit()
        self.state.inherit(parent.state)
        self._inherit = None

    def render(self, indent: int, cloth: rstcloth.rstcloth.RstCloth) -> None:
        """Render this step's contents into the given RstCloth instance."""
        # Apply pre
        if self.state.pre:
            cloth.content(self.state.pre, indent=indent, wrap=False)
            cloth.newline()

        for action in self.state.actions:
            action.render(indent, self.state.level + 1, cloth)
            cloth.newline()

        if self.state.content:
            cloth.content(self.state.content, indent=indent, wrap=False)
            cloth.newline()

        # Apply post
        if self.state.post:
            cloth.content(self.state.post, indent=indent, wrap=False)
            cloth.newline()

    @classmethod
    def load(cls, value: Any, path: str, config: StepsConfig) -> 'Step':
        inherit = mut.util.withdraw(value, 'inherit', mut.util.str_dict) or \
                  mut.util.withdraw(value, 'source', mut.util.str_dict)

        ref = mut.util.withdraw(value, 'ref', str)
        if ref is None:
            ref = inherit.get('ref') if inherit else None
        if ref is None:
            raise KeyError('ref: {}'.format(path))

        step = cls(ref, path, config)  # type: Step
        step.state.pre = mut.util.withdraw(value, 'pre', str)
        step.state.post = mut.util.withdraw(value, 'post', str)

        title = mut.util.withdraw(value, 'title', str_or_str_dict)
        if isinstance(title, str):
            step.state.title = title
        elif title:
            step.state.title = title['text']
            if 'character' in title:
                step.state.level = LEVEL_CHARACTERS[title['character']]

        step.state.level = mut.util.withdraw(value, 'level', int, default=step.state.level)
        step.state.content = mut.util.withdraw(value, 'content', str)
        raw_actions = mut.util.withdraw(value, 'action', str_or_dict_to_list)

        if raw_actions:
            try:
                step.state.actions = [Action.load(raw_action) for raw_action in raw_actions]
            except ValueError as err:
                raise StepsInputError(path, ref, str(err)) from err

        if raw_actions and step.state.content:
            msg = '"action" will replace "content"'
            config.root_config.warn(StepsInputError(path, ref, msg))

        replacements = mut.util.withdraw(value, 'replacement', mut.util.str_dict)
        if replacements:
            for src, dest in replacements.items():
                step.state.replacements[src] = dest

        if inherit:
            step._inherit = (inherit['file'], inherit['ref'])

        if mut.util.withdraw(value, 'stepnum', int):
            msg = 'Deprecated field: "stepnum"'
            config.root_config.warn(StepsInputError(path, ref, msg))

        if value:
            msg = 'Unknown fields "{}"'.format(', '.join(value.keys()))
            config.root_config.warn(StepsInputError(path, ref, msg))

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
        chunks = []  # type: List[str]
        header_html = ('<div class="sequence-block">'
                       '<div class="bullet-block">'
                       '<div class="sequence-step">'
                       '{0}'
                       '</div>'
                       '</div>')

        for step_number, step in enumerate(self.steps):
            step.inherit()
            step_number += 1

            cloth = rstcloth.rstcloth.RstCloth()
            cloth.directive('only', 'html or dirhtml or singlehtml')
            cloth.newline()

            cloth.directive(name='raw',
                            arg='html',
                            content=header_html.format(step_number),
                            indent=3)
            cloth.newline()

            if step.state.title:
                cloth.heading(text=step.state.title,
                              char=CHARACTER_LEVELS[step.state.level],
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

            if step.state.title:
                cloth.heading(text='Step {0}: {1}'.format(step_number, step.state.title),
                              char=CHARACTER_LEVELS[step.state.level],
                              indent=3)
                cloth.newline()
            else:
                cloth.heading(text='Step {0}'.format(step_number),
                              char=CHARACTER_LEVELS[step.state.level],
                              indent=3)
                cloth.newline()

            step.render(3, cloth)

            # XXX This is not the right place to apply substitutions
            try:
                chunk = mut.util.substitute_rstcloth(cloth, step.state.replacements)
            except KeyError as error:
                raise StepsInputError(self.path,
                                      self.ref,
                                      'Failed to substitute {}'.format(str(error))) from error
            chunk = mut.util.substitute(chunk, step.state.replacements)
            chunks.append(chunk)

        mut.util.save_if_changed('\n'.join(chunks), self.output_path)

    @property
    def output_path(self) -> str:
        bare_ref = self.ref.replace('steps-', '', 1)
        return os.path.join(self.config.output_path, bare_ref) + '.rst'

    @classmethod
    def load(cls, values: List[Any], path: str, config: StepsConfig) -> 'StepsList':
        filename = os.path.basename(path)
        steps = [Step.load(v, filename, config) for v in values if v]
        return cls(steps, filename, config)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.ref))


def run(root_config: mut.config.RootConfig, paths: List[str]) -> List[mut.MutInputError]:
    logger.info('Steps')
    config = StepsConfig(root_config)
    for path in paths:
        raw_steps = mut.util.load_yaml(path)
        StepsList.load(raw_steps, path, config)

    config.output()

    return config.root_config.warnings
