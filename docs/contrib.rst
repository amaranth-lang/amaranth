Contributing
############

The Amaranth project is a collective work of many people collaborating over the years, and it would not be the same without everyone's unique perspectives and contributions. We're glad that you are considering joining us! This page will guide you through some of the ways to contribute.

.. warning::

   This page is a work in progress!


Working with the codebase
=========================


Preparing the environment
-------------------------

The Amaranth codebase uses PDM_ to structure the development workflow. Please `install PDM`_ first. Once you have done so, run:

.. _PDM: https://pdm.fming.dev/
.. _install PDM: https://pdm.fming.dev/latest/#recommended-installation-method

.. code-block:: console

   $ pdm install --dev

This command creates a :ref:`virtual environment <python:tut-venv>` located at ``./.venv/`` and installs the runtime dependencies of Amaranth as well as the necessary development tools in it.

Amaranth itself is installed in the *editable mode*, meaning that the changes to its source files are immediately reflected in running the tests and documentation. However, other changes (addition or removal of source files, or changes to dependencies) will not be picked up, and it is a good habit to run ``pdm install`` each time after updating the source tree.


Running the testsuite
---------------------

Some of the tests make use of `formal methods`_, and to run the complete testsuite, it is necessary to install the Yosys_ frontend and the yices2_ SMT solver. These are distributed as a part of the `OSS CAD Suite`_. Without the tools being installed, the tests that rely on formal verification will be skipped.

.. _formal methods: https://symbiyosys.readthedocs.io/en/latest/
.. _Yosys: https://github.com/YosysHQ/yosys
.. _yices2: https://github.com/SRI-CSL/yices2
.. _OSS CAD Suite: https://github.com/YosysHQ/oss-cad-suite-build

To run the testsuite, use:

.. code-block:: console

   $ pdm run test


Building the documentation
--------------------------

To build the documentation once, use:

.. code-block:: console

   $ pdm run document

The documentation index is located at ``./docs/_build/index.html``.

Working on documentation usually involves making many small, iterative changes, and it is laborous to rebuild it manually each time. To start a process that rebuilds documentation automatically on change, use:

.. code-block:: console

   $ pdm run document-live

While it is running you can browse the documentation at `https://127.0.0.1:8000 <https://127.0.0.1:8000>`_. The edits you make are reflected on the document open in the browser after a short delay. It is useful to keep an eye on the terminal where this process is running, as the information about syntactic errors, missing references, and other issues will be printed there.

Occasionally, the documentation builder will persist in rendering an incorrect or outdated version of the contents of a Python source file. To fix this, run:

.. code-block:: console

   $ pdm run document-live -a


Contributing your changes
=========================

.. todo::

   Write this section


Proposing new features
======================

.. todo::

   Write this section
