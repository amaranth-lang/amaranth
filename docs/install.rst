Installation
############

System requirements
===================

nMigen requires Python 3.6; it works on CPython_ 3.6 (or newer), and works faster on PyPy3.6_ 7.2 (or newer).

Simulating nMigen code requires no additional software. However, a waveform viewer like GTKWave_ is invaluable for debugging.

Converting nMigen code to Verilog requires Yosys_ 0.9 (or newer).

Synthesizing, placing and routing an nMigen design for an FPGA requires Yosys_ 0.9 (or newer), as well as the FPGA family specific toolchain.

.. TODO: Link to FPGA family docs here

.. _CPython: https://www.python.org/
.. _PyPy3.6: https://www.pypy.org/
.. _Yosys: http://www.clifford.at/yosys/
.. _GTKWave: http://gtkwave.sourceforge.net/


Installing prerequisites
========================

... on Windows
--------------

.. todo::

   Determine what's appropriate here (do we put Python in PATH? what about Yosys? is there something better than GTKWave? do we just give up and suggest WSL?)


... on Debian Linux
-------------------

nMigen works on Debian 10 or newer. The required version of Yosys is available in the main repository since Debian 11, but requires the Backports_ repository on Debian 10. Run:

.. note: debian 10 provides: python3 3.7.3, yosys 0.8 (yosys 0.9 in backports)
.. note: debian 11 provides: python3 3.8.2, yosys 0.9

.. code-block:: shell

   $ sudo apt-get install python3-pip yosys gtkwave

.. _Backports: https://wiki.debian.org/Backports


... on Ubuntu Linux
-------------------

nMigen works on Ubuntu 20.04 LTS or newer.

.. note: ubuntu 20.04 provides: python3 3.8.2, yosys 0.9

.. code-block:: shell

   $ sudo apt-get install python3-pip yosys gtkwave


... on macOS
------------

nMigen works best with Homebrew_. Run:

.. code-block:: shell

   $ brew install python yosys gtkwave

.. _Homebrew: https://brew.sh


... on other platforms
----------------------

Refer to the `Yosys README`_ for detailed build instructions.

.. _Yosys README: https://github.com/YosysHQ/yosys/#setup


Installing nMigen
=================

The latest release of nMigen should work well for most applications. A development snapshot---any commit from the ``master`` branch of nMigen---should be similarly reliable, but is likely to include experimental API changes that will be in flux until the next release. With that in mind, development snapshots can be used to try out new functionality or to avoid bugs fixed since the last release.


Latest release
--------------

To install the latest release of nMigen, run:

.. code-block:: shell

   $ pip3 install --upgrade nmigen


Development snapshot
--------------------

To install a development snapshot of nMigen for the first time, run:

.. code-block:: shell

   $ git clone https://github.com/nmigen/nmigen
   $ cd nmigen
   $ pip3 install --editable .

Any changes made to the ``nmigen`` directory will immediately affect any code that uses nMigen. To update the snapshot, run:

.. code-block:: shell

   $ cd nmigen
   $ git pull --ff-only origin master


Installing board definitions
=============================

.. todo::

	 Explain how to install `<https://github.com/nmigen/nmigen-boards>`_.
