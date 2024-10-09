Installation
############

.. _install-playground:

In-browser playground
=====================

You can try Amaranth out without installing anything by visiting the `Amaranth Playground`_. The playground webpage contains a `fully functional Python interpreter <Pyodide_>`_ and an Amaranth toolchain that can simulate a design, display waveforms, and generate Verilog code. It works on all modern browsers that support WebAssembly_, including Firefox, Chrome, and Edge.

.. _Amaranth Playground: https://amaranth-lang.org/play/
.. _Pyodide: https://pyodide.org/en/stable/
.. _WebAssembly: https://webassembly.org/


.. _install-sysreqs:

System requirements
===================

..
   This version requirement needs to be synchronized with the one in pyproject.toml!

.. |yosys-version| replace:: 0.40 (or newer)

Amaranth HDL requires Python 3.9; it works on CPython_ 3.9 (or newer), and works faster on PyPy3.9_ 7.3.7 (or newer). Installation requires pip_ 23.0 (or newer).

For most workflows, Amaranth requires Yosys_ |yosys-version|. A `compatible version of Yosys <amaranth-yosys_>`_ is distributed via PyPI_ for most popular platforms, so it is usually not necessary to install Yosys separately.

Simulating Amaranth code requires no additional software. However, a waveform viewer like Surfer_ or GTKWave_ is invaluable for debugging. As an alternative, the `Amaranth Playground`_ can be used to display waveforms for simple designs.

Synthesizing, placing and routing an Amaranth design for an FPGA requires the FPGA family specific toolchain. The open source iCE40, ECP5, MachXO2/3, Nexus, and Gowin toolchains are distributed via PyPI_ for most popular platforms by the YoWASP_ project.

.. TODO: Link to FPGA family docs here

.. _CPython: https://www.python.org/
.. _PyPy3.9: https://www.pypy.org/
.. _pip: https://pip.pypa.io/en/stable/
.. _Yosys: https://yosyshq.net/yosys/
.. _amaranth-yosys: https://pypi.org/project/amaranth-yosys/
.. _PyPI: https://pypi.org/
.. _Surfer: https://surfer-project.org/
.. _GTKWave: https://gtkwave.sourceforge.net/
.. _YoWASP: https://yowasp.org/


.. _install-deps:

Installing prerequisites
========================

.. |builtin-yosys-architectures| replace:: x86_64 and AArch64
.. |upgrade-pip| replace:: Before continuing, make sure you have the latest version of pip_ installed by running:

.. platform-picker::

   .. platform-choice:: windows
      :title: Windows

      :ref:`Install Python <python:using-on-windows>`, either from Windows Store or using the full installer. If using the full installer, make sure to install a 64-bit version of Python.

      |upgrade-pip|

      .. code-block:: doscon

         > pip install --upgrade pip

   .. platform-choice:: macos
      :title: macOS

      Install Homebrew_. Then, install Python by running:

      .. code-block:: console

         $ brew install python

      .. _Homebrew: https://brew.sh

      |upgrade-pip|

      .. code-block:: console

         $ pip install --upgrade pip

   .. platform-choice:: debian
      :altname: linux
      :title: Debian

      Install Python by running:

      .. code-block:: console

         $ sudo apt-get install python3-pip

      On architectures other than |builtin-yosys-architectures|, install Yosys by running:

      .. code-block:: console

         $ sudo apt-get install yosys

      If Yosys |yosys-version| is not available, `build Yosys from source`_.

      |upgrade-pip|

      .. code-block:: console

         $ pip3 install --user --upgrade pip

   .. platform-choice:: linux
      :title: Other Linux

      Install Python from the package repository of your distribution.

      On architectures other than |builtin-yosys-architectures|, install Yosys from the package repository of your distribution.

      If Yosys |yosys-version| is not available, `build Yosys from source`_.

      .. _build Yosys from source: https://github.com/YosysHQ/yosys/#building-from-source

      |upgrade-pip|

      .. code-block:: console

         $ pip3 install --user --upgrade pip


.. _install:

Installing Amaranth
===================

The latest release of Amaranth should work well for most applications. A development snapshot---any commit from the ``main`` branch of Amaranth---should be similarly reliable, but is likely to include experimental API changes that will be in flux until the next release. With that in mind, development snapshots can be used to try out new functionality or to avoid bugs fixed since the last release.


.. _install-release:

Latest release
--------------

.. |release:install| replace:: To install the latest release of Amaranth, run:

.. platform-picker::

   .. platform-choice:: windows
      :title: Windows

      |release:install|

      .. code-block:: doscon

         > pip install --upgrade amaranth[builtin-yosys]

   .. platform-choice:: macos
      :title: macOS

      |release:install|

      .. code-block:: console

         $ pip install --user --upgrade 'amaranth[builtin-yosys]'

   .. platform-choice:: linux
      :title: Linux

      If you **did not** install Yosys manually in the :ref:`previous step <install-deps>`, to install the latest release of Amaranth, run:

      .. code-block:: console

         $ pip3 install --user --upgrade 'amaranth[builtin-yosys]'

      If you **did** install Yosys manually in the previous step, run:

      .. code-block:: console

         $ pip3 install --user --upgrade amaranth


.. _install-snapshot:

Development snapshot
--------------------

.. |snapshot:install| replace:: To install the latest development snapshot of Amaranth, run:

.. platform-picker::

   .. platform-choice:: windows
      :title: Windows

      |snapshot:install|

      .. code-block:: doscon

         > pip install "amaranth[builtin-yosys] @ git+https://github.com/amaranth-lang/amaranth.git"

   .. platform-choice:: macos
      :title: macOS

      |snapshot:install|

      .. code-block:: console

         $ pip install --user 'amaranth[builtin-yosys] @ git+https://github.com/amaranth-lang/amaranth.git'

   .. platform-choice:: linux
      :title: Linux

      If you **did not** install Yosys manually in the :ref:`previous step <install-deps>`, to install the latest release of Amaranth, run:

      .. code-block:: console

         $ pip3 install --user 'amaranth[builtin-yosys] @ git+https://github.com/amaranth-lang/amaranth.git'

      If you **did** install Yosys manually in the previous step, run:

      .. code-block:: console

         $ pip3 install --user 'amaranth @ git+https://github.com/amaranth-lang/amaranth.git'


.. _install-develop:

Editable development snapshot
-----------------------------

.. |develop:first-time| replace:: To install an editable development snapshot of Amaranth for the first time, run:
.. |develop:update| replace:: Any changes made to the ``amaranth`` directory will immediately affect any code that uses Amaranth. To update the snapshot, run:
.. |develop:reinstall| replace:: any time package dependencies may have been added or changed (notably after updating the snapshot with ``git``). Otherwise, code using Amaranth may crash because of a dependency version mismatch.

.. platform-picker::

   .. platform-choice:: windows
      :title: Windows

      |develop:first-time|

      .. code-block:: doscon

         > git clone https://github.com/amaranth-lang/amaranth
         > cd amaranth
         > pip install --editable .[builtin-yosys]

      |develop:update|

      .. code-block:: doscon

         > cd amaranth
         > git pull --ff-only origin main
         > pip install --editable .[builtin-yosys]

      Run the ``pip install --editable .[builtin-yosys]`` command |develop:reinstall|

   .. platform-choice:: macos
      :title: macOS

      |develop:first-time|

      .. code-block:: console

         $ git clone https://github.com/amaranth-lang/amaranth
         $ cd amaranth
         $ pip install --user --editable '.[builtin-yosys]'

      |develop:update|

      .. code-block:: console

         $ cd amaranth
         $ git pull --ff-only origin main
         $ pip install --user --editable '.[builtin-yosys]'

      Run the ``pip install --editable .[builtin-yosys]`` command |develop:reinstall|

   .. platform-choice:: linux
      :title: Linux

      If you **did** install Yosys manually in the :ref:`previous step <install-deps>`, omit ``[builtin-yosys]`` from the following commands.

      |develop:first-time|

      .. code-block:: console

         $ git clone https://github.com/amaranth-lang/amaranth
         $ cd amaranth
         $ pip3 install --user --editable '.[builtin-yosys]'

      |develop:update|

      .. code-block:: console

         $ cd amaranth
         $ git pull --ff-only origin main
         $ pip3 install --user --editable '.[builtin-yosys]'

      Run the ``pip3 install --editable .[builtin-yosys]`` command |develop:reinstall|


Installing board definitions
=============================

.. todo::

	 Explain how to install `<https://github.com/amaranth-lang/amaranth-boards>`_.
