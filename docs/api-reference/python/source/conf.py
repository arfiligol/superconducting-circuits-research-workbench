from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

for relative_path in (
    "core/sc_core",
    "core/analysis",
    "core/python/sc_data_contracts",
):
    sys.path.insert(0, str(REPO_ROOT / relative_path))

project = "Superconducting Circuits Research Workbench Python API"
author = "Superconducting Circuits Research Workbench contributors"
copyright = "2026, Superconducting Circuits Research Workbench contributors"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

html_theme = "furo"
html_title = "Python API Reference"
html_favicon = str(REPO_ROOT / "site" / "public" / "favicon.svg")
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_baseurl = os.environ.get(
    "PYTHON_API_BASE_URL",
    "https://arfiligol.github.io/superconducting-circuits-research-workbench/api/python/",
)

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "show-inheritance": True,
    "exclude-members": "__weakref__",
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"

autosummary_generate = True
autosummary_imported_members = False
autosummary_ignore_module_all = False

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}
