Installation
############

System requirements
===================

.. |yosys-version| replace:: 0.10 (or newer)

Amaranth HDL requires Python 3.6; it works on CPython_ 3.6 (or newer), and works faster on PyPy3.6_ 7.2 (or newer).

For most workflows, Amaranth requires Yosys_ |yosys-version|. A compatible version of Yosys is distributed via PyPI_ for most popular platforms.

Simulating Amaranth code requires no additional software. However, a waveform viewer like GTKWave_ is invaluable for debugging.

Synthesizing, placing and routing an Amaranth design for an FPGA requires the FPGA family specific toolchain.

.. TODO: Link to FPGA family docs here

.. _CPython: https://www.python.org/
.. _PyPy3.6: https://www.pypy.org/
.. _Yosys: https://yosyshq.net/yosys/
.. _PyPI: https://pypi.org/
.. _GTKWave: http://gtkwave.sourceforge.net/


.. _install-deps:

Installing prerequisites
========================

.. |builtin-yosys-architectures| replace:: x86_64 and AArch64

.. platform-picker::

   .. platform-choice:: windows
      :title: Windows

      :ref:`Install Python <python:using-on-windows>`, either from Windows Store or using the full installer. If using the full installer, make sure to install a 64-bit version of Python.

      `Download GTKWave`_, either win32 or win64 binaries. GTKWave does not need to be installed; it can be unpacked to any convenient location and run from there.

      .. _Download GTKWave: https://sourceforge.net/projects/gtkwave/files/

   .. platform-choice:: macos
      :title: macOS

      Install Homebrew_. Then, install Python and GTKWave by running:

      .. code-block:: console

         $ brew install python gtkwave

      .. _Homebrew: https://brew.sh

   .. platform-choice:: debian
      :altname: linux
      :title: Debian

      Install Python and GTKWave by running:

      .. code-block:: console

         $ sudo apt-get install python3-pip gtkwave

      On architectures other than |builtin-yosys-architectures|, install Yosys by running:

      .. code-block:: console

         $ sudo apt-get install yosys

      If Yosys |yosys-version| is not available, `build Yosys from source`_.

   .. platform-choice:: arch
      :altname: linux
      :title: Arch Linux

      Install Python, pip, GTKWave and Yosys by running:

      .. code-block:: console

         $ sudo pacman -S python python-pip gtkwave yosys

   .. platform-choice:: linux
      :title: Other Linux

      Install Python and GTKWave from the package repository of your distribution.

      On architectures other than |builtin-yosys-architectures|, install Yosys from the package repository of your distribution.

      If Yosys |yosys-version| is not available, `build Yosys from source`_.

      .. _build Yosys from source: https://github.com/YosysHQ/yosys/#setup


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

   .. platform-choice:: arch
      :altname: linux
      :title: Arch Linux

      |release:install|

      .. code-block:: console

         $ sudo pacman -S python-amaranth


.. _install-snapshot:

Development snapshot
--------------------

.. |snapshot:install| replace:: To install the latest development snapshot of Amaranth, run:

.. platform-picker::

   .. platform-choice:: windows
      :title: Windows

      |snapshot:install|

      .. code-block:: doscon

         > pip install git+https://github.com/amaranth-lang/amaranth.git#egg=amaranth[builtin-yosys]

   .. platform-choice:: macos
      :title: macOS

      |snapshot:install|

      .. code-block:: console

         $ pip install --user 'git+https://github.com/amaranth-lang/amaranth.git#egg=amaranth[builtin-yosys]'

   .. platform-choice:: linux
      :title: Linux

      If you **did not** install Yosys manually in the :ref:`previous step <install-deps>`, to install the latest release of Amaranth, run:

      .. code-block:: console

         $ pip3 install --user 'git+https://github.com/amaranth-lang/amaranth.git#egg=amaranth[builtin-yosys]'

      If you **did** install Yosys manually in the previous step, run:

      .. code-block:: console

         $ pip3 install --user 'git+https://github.com/amaranth-lang/amaranth.git#egg=amaranth'


.. _install-develop:

Editable development snapshot
-----------------------------

.. |develop:first-time| replace:: To install an editable development snapshot of Amaranth for the first time, run:
.. |develop:update| replace:: Any changes made to the ``amaranth`` directory will immediately affect any code that uses Amaranth. To update the snapshot, run:
.. |develop:reinstall| replace:: each time the editable development snapshot is updated in case package dependencies have been added or changed. Otherwise, code using Amaranth may misbehave or crash with an ``ImportError``.

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
