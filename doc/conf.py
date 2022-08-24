# -*- coding: utf-8 -*-
#
# MongoDB documentation build configuration file, created by
# sphinx-quickstart on Mon Oct  3 09:58:40 2011.
#
# This file is execfile()d with the current directory set to its containing dir.

import sys
import os
import datetime

from sphinx.errors import SphinxError

try:
    tags
except NameError:

    class Tags(object):
        def has(self, *args):
            return False

    tags = Tags()

# -- General configuration ----------------------------------------------------

needs_sphinx = "1.0"

extensions = [
    "sphinx.ext.extlinks",
    "sphinx.ext.todo",
]

locale_dirs = []
gettext_compact = False

templates_path = [".templates"]
exclude_patterns = []

source_suffix = ".txt"

master_doc = "index"
language = "en"
project = "mut"
copyright = "2008-{0}".format(datetime.date.today().year)
version = "0.1"
release = "0.1"

rst_epilog = "\n".join(
    [
        ".. |copy| unicode:: U+000A9",
        ".. |ent-build| replace:: MongoDB Enterprise",
        ".. |year| replace:: {0}".format(datetime.date.today().year),
    ]
)

pygments_style = "sphinx"

extlinks = {
    "issue": ("https://jira.mongodb.org/browse/%s", ""),
    "wiki": ("http://www.mongodb.org/display/DOCS/%s", ""),
    "api": ("https://api.mongodb.org/%s", ""),
    "manual": ("https://docs.mongodb.org/manual%s", ""),
    "gettingstarted": ("https://docs.mongodb.org/getting-started%s", ""),
    "ecosystem": ("https://docs.mongodb.org/ecosystem%s", ""),
    "meta-driver": ("http://docs.mongodb.org/meta-driver/latest%s", ""),
    "mms-docs": ("https://docs.cloud.mongodb.com%s", ""),
    "mms-home": ("https://cloud.mongodb.com%s", ""),
    "opsmgr": ("https://docs.opsmanager.mongodb.com/current%s", ""),
    "about": ("https://www.mongodb.org/about%s", ""),
    "products": ("https://www.mongodb.com/products%s", ""),
}

languages = [
    ("ar", "Arabic"),
    ("cn", "Chinese"),
    ("cs", "Czech"),
    ("de", "German"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("hu", "Hungarian"),
    ("id", "Indonesian"),
    ("it", "Italian"),
    ("jp", "Japanese"),
    ("ko", "Korean"),
    ("lt", "Lithuanian"),
    ("pl", "Polish"),
    ("pt", "Portuguese"),
    ("ro", "Romanian"),
    ("ru", "Russian"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian"),
]

# -- Options for HTML output ---------------------------------------------------

html_theme = "nature"
html_title = "Mut"
htmlhelp_basename = "MongoDBdoc"

# html_logo = sconf.logo
html_static_path = ["_static"]

html_copy_source = False
html_use_smartypants = True
html_domain_indices = True
html_use_index = True
html_split_index = False
html_show_sourcelink = False
html_show_sphinx = True
html_show_copyright = True

html_sidebars = {}

# put it into your conf.py
def setup(app):
    # disable versioning for speed
    from sphinx.builders.gettext import I18nBuilder

    I18nBuilder.versioning_method = "none"

    def doctree_read(app, doctree):
        if not isinstance(app.builder, I18nBuilder):
            return
        from docutils import nodes
        from sphinx.versioning import add_uids

        list(add_uids(doctree, nodes.TextElement))

    app.connect("doctree-read", doctree_read)
