#!/usr/bin/env python3

from typing import List

import mut.tuft.visitors


def build(src_path: str,
          handlers: List['mut.tuft.visitors.Visitor'],
          output_path: str) -> None:
    import mut.tuft.driver
    mut.tuft.driver.build(src_path, handlers, output_path)
