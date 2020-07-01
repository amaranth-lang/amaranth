Installation
############

System requirements
===================

nMigen requires Python 3.6; it works on CPython_ 3.6 (or newer), and works faster on PyPy3.6_ 7.2 (or newer).

For most workflows, nMigen requires Yosys_ 0.9 (or newer). A compatible version of Yosys is distributed via PyPI_ for most popular platforms.

Simulating nMigen code requires no additional software. However, a waveform viewer like GTKWave_ is invaluable for debugging.

Synthesizing, placing and routing an nMigen design for an FPGA requires the FPGA family specific toolchain.

.. TODO: Link to FPGA family docs here

.. _CPython: https://www.python.org/
.. _PyPy3.6: https://www.pypy.org/
.. _Yosys: http://www.clifford.at/yosys/
.. _PyPI: https://pypi.org/
.. _GTKWave: http://gtkwave.sourceforge.net/


.. _install-deps:

Installing prerequisites
========================

.. |builtin-yosys-architectures| replace:: x86_64 and AArch64

.. content-tabs::

   .. tab-container:: windows
      :title: Windows

      `Install Python <python:using-on-windows>`_, either from Windows Store or using the full installer. If using the full installer, make sure to install a 64-bit version of Python.

      `Download GTKWave`_, either win32 or win64 binaries. GTKWave does not need to be installed; it can be unpacked to any convenient location and run from there.

      .. _Download GTKWave: https://sourceforge.net/projects/gtkwave/files/

   .. tab-container:: macos
      :title: macOS

      Install Homebrew_. Then, install Python and GTKWave by running:

      .. code-block:: console

         $ brew install python gtkwave

      .. _Homebrew: https://brew.sh

   .. tab-container:: linux
      :title: Linux

      .. rubric:: Debian-based distributions

      Install Python and GTKWave by running:

      .. code-block:: console

         $ sudo apt-get install python3-pip gtkwave

      On architectures other than |builtin-yosys-architectures|, install Yosys by running:

      .. code-block:: console

         $ sudo apt-get install yosys

      If Yosys 0.9 (or newer) is not available, `build Yosys from source`_.

      .. rubric:: Other distributions

      Install Python and GTKWave from the package repository of your distribution.

      On architectures other than |builtin-yosys-architectures|, install Yosys from the package repository of your distribution.

      If Yosys 0.9 (or newer) is not available, `build Yosys from source`_.

      .. _build Yosys from source: https://github.com/YosysHQ/yosys/#setup


.. _install:

Installing nMigen
=================

The latest release of nMigen should work well for most applications. A development snapshot---any commit from the ``master`` branch of nMigen---should be similarly reliable, but is likely to include experimental API changes that will be in flux until the next release. With that in mind, development snapshots can be used to try out new functionality or to avoid bugs fixed since the last release.


.. _install-release:

Latest release
--------------

.. |release:install| replace:: To install the latest release of nMigen, run:

.. content-tabs::

   .. tab-container:: windows
      :title: Windows

      |release:install|

      .. code-block:: doscon

         > pip install --upgrade nmigen[builtin-yosys]

   .. tab-container:: macos
      :title: macOS

      |release:install|

      .. code-block:: console

         $ pip install --user --upgrade nmigen[builtin-yosys]

   .. tab-container:: linux
      :title: Linux

      If you **did not** install Yosys manually in the :ref:`previous step <install-deps>`, to install the latest release of nMigen, run:

      .. code-block:: console

         $ pip3 install --user --upgrade nmigen[builtin-yosys]

      If you **did** install Yosys manually in the previous step, run:

      .. code-block:: console

         $ pip3 install --user --upgrade nmigen


.. _install-develop:

Development snapshot
--------------------

.. |snapshot:first-time| replace:: To install a development snapshot of nMigen for the first time, run:
.. |snapshot:update| replace:: Any changes made to the ``nmigen`` directory will immediately affect any code that uses nMigen. To update the snapshot, run:
.. |snapshot:reinstall| replace:: It is important to run the ``pip3 install --editable .[builtin-yosys]`` each time the development snapshot is updated in case package dependencies have been added or changed. Otherwise, code using nMigen may misbehave or crash with an ``ImportError``.

.. content-tabs::

   .. tab-container:: windows
      :title: Windows

      |snapshot:first-time|

      .. code-block:: doscon

         > git clone https://github.com/nmigen/nmigen
         > cd nmigen
         > pip install --editable .[builtin-yosys]

      |snapshot:update|

      .. code-block:: doscon

         > cd nmigen
         > git pull --ff-only origin master
         > pip install --editable .[builtin-yosys]

      |snapshot:reinstall|

   .. tab-container:: macos
      :title: macOS

      |snapshot:first-time|

      .. code-block:: console

         $ git clone https://github.com/nmigen/nmigen
         $ cd nmigen
         $ pip install --user --editable .[builtin-yosys]

      |snapshot:update|

      .. code-block:: console

         $ cd nmigen
         $ git pull --ff-only origin master
         $ pip install --user --editable .[builtin-yosys]

      |snapshot:reinstall|

   .. tab-container:: linux
      :title: Linux

      If you **did** install Yosys manually in a :ref:`previous step <install-deps>`, omit ``[builtin-yosys]`` from the following commands.

      |snapshot:first-time|

      .. code-block:: console

         $ git clone https://github.com/nmigen/nmigen
         $ cd nmigen
         $ pip3 install --user --editable .[builtin-yosys]

      |snapshot:update|

      .. code-block:: console

         $ cd nmigen
         $ git pull --ff-only origin master
         $ pip3 install --user --editable .[builtin-yosys]

      |snapshot:reinstall|


Installing board definitions
=============================

.. todo::

	 Explain how to install `<https://github.com/nmigen/nmigen-boards>`_.
