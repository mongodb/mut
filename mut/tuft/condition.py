#!/usr/bin/env python3

import collections
import re

from typing import Sequence, Iterator, Union, Tuple, Any

CONDITION_PAT = re.compile(r'([\w\-]+|[()])')

BinaryType = Tuple[str, Any]
TernaryType = Tuple[str, Any, Any]
Operator = Union[BinaryType, TernaryType, str]


class Tags:
    def __init__(self, tags: Sequence[str]=()) -> None:
        self.tags = set(tags)

    def has(self, tag: str) -> bool:
        return tag in self.tags

    __contains__ = has

    def __iter__(self) -> Iterator[str]:
        return iter(self.tags)

    def add(self, tag: str) -> None:
        self.tags.add(tag)

    def remove(self, tag: str) -> None:
        self.tags.remove(tag)

    def eval(self, condition: Operator) -> bool:
        """Check if this tag set satisfies the given expression obtained from
           parse()."""
        if isinstance(condition, str):
            return condition in self

        if condition[0] == 'not':
            return not self.eval(condition[1])
        elif condition[0] == 'or':
            return self.eval(condition[1]) or self.eval(condition[2])
        elif condition[0] == 'and':
            return self.eval(condition[1]) and self.eval(condition[2])


def __parse_paren(tokens: collections.deque) -> collections.deque:
    """Given a token stream, extract a pair of matched parenthesis into a new
       token stream."""
    buf = collections.deque()  # type: collections.deque[str]
    depth = 0

    if tokens[0] != '(':
        raise ValueError(tokens)

    # Chew up to the matching closing paren
    while tokens:
        token = tokens.popleft()
        if token == '(':
            if depth > 0:
                buf.append(token)

            depth += 1
        elif token == ')':
            depth -= 1
            if depth > 0:
                buf.append(token)
            else:
                return buf
        else:
            buf.append(token)

    return buf


def __parse(tokens: collections.deque, max_tokens: int=-1) -> Operator:
    i = 0

    lhs = None  # type: Operator
    op = None  # type: str

    if max_tokens < 0:
        max_tokens = len(tokens)

    while tokens and (i < max_tokens):
        i += 1

        cur = tokens.popleft()
        if cur in ('and', 'or'):
            assert op is None
            assert lhs is not None
            op = cur
        elif cur == 'not':
            assert (not op and not lhs) or (op and lhs)
            if not op:
                lhs = (cur, __parse(tokens, max_tokens=1))
            else:
                lhs = (op, lhs, (cur, __parse(tokens, max_tokens=1)))
                op = None
        elif cur == '(':
            tokens.appendleft(cur)
            sub = __parse(__parse_paren(tokens))
            if not lhs:
                lhs = sub
            else:
                lhs = tuple(list(lhs) + list(sub))
        else:
            if not lhs and not op:
                lhs = cur
            elif lhs and op:
                lhs = (op, lhs, cur)
                op = None
            else:
                raise AssertionError()

    return lhs


def parse(text: str) -> Operator:
    """Parse an english logic expression into an S-expression suitable for
       evaluation."""
    lexed = collections.deque(CONDITION_PAT.findall(text))

    try:
        return __parse(lexed)
    except AssertionError as err:
        raise ValueError(text) from err
