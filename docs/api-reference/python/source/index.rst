Python API Reference
====================

This generated reference documents the importable Python core packages used by
the workbench. Astro + Starlight owns the high-level Source-of-Truth
documentation at ``/docs/``; this site provides docstring-level package details
for implementation work.

Quick links
-----------

* `High-level technical docs <../../docs/>`_
* `Julia API Reference <../julia/>`_
* `Python Core contract summary <../../docs/reference/core/python-core/>`_

Package scope
-------------

Sphinx v1 documents the reusable Python package surface:

* ``superconducting_circuits_analysis`` for Python-owned analysis, fitting,
  and trace-normalization helpers.
* ``schemdraw_circuit_library`` for renderer-side reusable Schemdraw visual
  components.

The FastAPI backend remains an application adapter. Its HTTP contracts are
documented in the high-level docs and OpenAPI, not as public Python package API
here.

.. toctree::
   :maxdepth: 2
   :caption: Packages

   packages/analysis
   packages/schemdraw_circuit_library
