#!/usr/bin/env python3

import abc
import os
import os.path
import logging

from typing import Any, Dict, List
import yaml

import mut.tuft.visitors
import mut.tuft.visitors.html5
import mut.tuft.condition
import mut.tuft.exts
import mut.tuft.linkcache
import mut.tuft.environment

logger = logging.getLogger(__name__)


class Driver:
    def __init__(self, src_path: str, config: Dict[str, Any]) -> None:
        self.src_path = src_path
        self.links = mut.tuft.linkcache.LinkCache(src_path)
        self.env = mut.tuft.environment.Environment(self.src_path, self.links, config)

        # Rebuild the link cache
        self.links.update(self.env)

    def parse(self, path: str, handlers: List[mut.tuft.visitors.Visitor]) -> None:
        """Translate a single file into HTML."""
        document = self.env.get_document(path)
        self.env.current_input_path = path

        writer = self.get_writer(path, document, self.links)
        visitors = handlers[:]

        if writer:
            visitors.append(writer)

        visitor = mut.tuft.visitors.VisitorDriver(document, visitors)
        document.walkabout(visitor)

        if writer:
            self.write(writer, path)

    def crawl(self, visitors: List[mut.tuft.visitors.Visitor]) -> None:
        """Translate an entire directory into HTML."""
        for root, _, files in os.walk(self.src_path):
            for filename in files:
                filename = os.path.join(root, filename)

                if not filename.endswith(self.env.config['source_suffix']):
                    continue

                logger.debug('Processing %s', filename)
                self.parse(filename, visitors)

        self.postprocess()

    def write(self, writer: mut.tuft.visitors.WriterDriver, path: str) -> None:
        pass

    def postprocess(self) -> None:
        pass

    @staticmethod
    def get_writer(path: str, document, links) -> mut.tuft.visitors.WriterDriver:
        return None


class HTML5Driver(Driver):
    def __init__(self, src_path: str, output_path: str, config: Dict[str, Any]) -> None:
        super(HTML5Driver, self).__init__(src_path, config)
        self.output_path = output_path

    def write(self, writer: mut.tuft.visitors.WriterDriver, path: str) -> None:
        output_path = os.path.join(self.output_path,
                                   os.path.splitext(path.replace(self.src_path, '', 1))[0],
                                   'index.html')

        # Create containing directory
        try:
            os.makedirs(os.path.dirname(output_path))
        except OSError:
            pass

        with open(output_path, 'w') as f:
            f.write(writer.astext())

    def postprocess(self) -> None:
        with open(os.path.join(self.output_path, 'viewer.html'), 'w') as f:
            f.write(str(mut.tuft.visitors.html5.render_viewer(self.env)))

    @staticmethod
    def get_writer(path: str, document, links) -> mut.tuft.visitors.WriterDriver:
        return mut.tuft.visitors.html5.HTML5Visitor(path, document, links)


def load_config(path: str) -> Dict[str, Any]:
        config = {}  # type: Dict[str, Any]
        try:
            with open('conf.yaml') as f:
                config = dict(yaml.load(f))
        except FileNotFoundError:
            pass

        return config


def build(src_path: str,
          handlers: List[mut.tuft.visitors.Visitor],
          output_path: str) -> None:
    config = load_config('conf.yaml')

    driver = None  # type: mut.tuft.driver.Driver
    if output_path:
        driver = mut.tuft.driver.HTML5Driver(src_path=src_path,
                                             output_path=output_path,
                                             config=config)
    else:
        driver = mut.tuft.driver.Driver(src_path=src_path, config=config)

    driver.crawl(handlers)
