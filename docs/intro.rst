.. TODO: this introduction is written for people well familiar with HDLs; we likely need
	 another one for people who will use Amaranth as their first HDL

Introduction
############

The Amaranth project provides an open-source toolchain for developing hardware based on synchronous digital logic using the Python programming language. It aims to be easy to learn and use, reduce or eliminate common coding mistakes, and simplify the design of complex hardware with reusable components.

The Amaranth toolchain consists of the :ref:`Amaranth language <intro-lang>`, the :ref:`standard library <intro-stdlib>`, the :ref:`simulator <intro-sim>`, and the :ref:`build system <intro-build>`, covering all steps of a typical FPGA development workflow. At the same time, it does not restrict the designer's choice of tools: existing industry-standard (System)Verilog or VHDL code can be integrated into an Amaranth-based design flow, or, conversely, Amaranth code can be integrated into an existing Verilog-based design flow.

.. TODO: add links to connect_rpc docs once they exist


.. _intro-lang:

The Amaranth language
=====================

The :doc:`Amaranth hardware description language <lang>` is a Python library for register transfer level modeling of synchronous logic. Ordinary Python code is used to construct a netlist of a digital circuit, which can be simulated, directly synthesized via Yosys_, or converted to human-readable Verilog code for use with industry-standard toolchains.

By relying on the flexibility, rich functionality and widespread adoption of the Python language, the Amaranth language is focused on a single task: modeling digital logic well. It has first-class support for building blocks like clock domains and finite state machines, and uses simple rules for arithmetic operations that closely match the Python semantics. Python classes, functions, loops and conditionals can be used to build organized and flexible designs; Python libraries can be seamlessly used with Amaranth during design or verification; and Python development tools can process Amaranth code.

A core design principle of the Amaranth language is to be not only easy to use, but also hard to accidentally misuse. Some HDLs provide functionality that has unexpected and undesirable behavior in synthesis, often with expensive consequences, and require a significant effort in learning a "safe" coding style and adopting third-party linting tools. Amaranth lacks non-synthesizable constructs and avoids error-prone inference in favor of explicit instantiation. It has many diagnostics (and regularly adds new ones) highlighting potential design issues. Most importantly, all usability issues are considered `reportable bugs`_.

.. _Yosys: https://yosyshq.net/yosys/
.. _reportable bugs: https://github.com/amaranth-lang/amaranth/issues


.. _intro-stdlib:

The Amaranth standard library
=============================

The Amaranth language comes with a standard library---a collection of essential digital design components and interfaces. It includes clock domain crossing primitives, synchronous and asynchronous FIFOs, a flexible I/O buffer interface, and more. By providing reliable building blocks out of the box, Amaranth allows the designer to focus on their application and avoids subtle differences in behavior between different designs.

.. TODO: link to stdlib here

Clock domain crossing often requires special treatment, such as using vendor-defined attributes or instantiating device-specific primitives. The CDC primitives in the Amaranth standard library can be overridden by the platform integration, and every platform integration included with Amaranth follows the vendor recommendations for CDC.

High-speed designs usually require the use of registered (and sometimes, geared) I/O buffers. The Amaranth standard library provides a common interface to be used between I/O buffers and peripheral implementations. The Amaranth build system, if used, can instantiate I/O buffers for every platform integration included with Amaranth.

While many designs will use at least some vendor-specific functionality, the components provided by the Amaranth standard library reduce the amount of code that needs to be changed when migrating between FPGA families, and the common interfaces simplify peripherals, test benches and simulations.

The Amaranth standard library is optional: the Amaranth language can be used without it. Conversely, it is possible to use the Amaranth standard library components in Verilog or VHDL code, with some limitations.

.. TODO: link to connect_rpc docs here *again*


.. _intro-sim:

The Amaranth simulator
======================

The Amaranth project includes an advanced simulator for Amaranth code implemented in Python with no system dependencies; in this simulator, test benches are written as Python generator functions. Of course, it is always possible to convert an Amaranth design to Verilog for use with well-known tool like `Icarus Verilog`_ or Verilator_.

The Amaranth simulator is event-driven and can simulate designs with multiple clocks or asynchronous resets. Although it is slower than `Icarus Verilog`_, it compiles the netlist to Python code ahead of time, achieving remarkably high performance for a pure Python implementation---especially when running on PyPy_.

Although Amaranth does not support native code simulation or co-simulation at the moment, such support will be added in near future.

.. _Icarus Verilog: http://iverilog.icarus.com/
.. _Verilator: https://www.veripool.org/wiki/verilator
.. _GTKWave: http://gtkwave.sourceforge.net/
.. _PyPy: https://www.pypy.org/


.. _intro-build:

The Amaranth build system
=========================

To achieve an end-to-end FPGA development workflow, the Amaranth project integrates with all major FPGA toolchains and provides definitions for many common development boards.

.. TODO: link to vendor docs and board docs here


FPGA toolchain integration
--------------------------

Each FPGA family requires the use of synthesis and place & route tools specific for that device family. The Amaranth build system directly integrates with every major open-source and commercial FPGA toolchain, and can be easily extended to cover others.

Through this integration, Amaranth can specialize the CDC primitives and I/O buffers for a particular device and toolchain; generate I/O and clock constraints from board definition files; synchronize the power-on reset in single-clock designs; include (System)Verilog and VHDL files in the design (if supported by the toolchain); and finally, generate a script running synthesis, placement, routing, and timing analysis. The generated code can be customized to insert additional options, commands, constraints, and so on.

The Amaranth build system produces self-contained, portable build trees that require only the toolchain to be present in the environment. This makes builds easier to reproduce, or to run on a remote machine. The generated build scripts are always provided for both \*nix and Windows.


Development board definitions
-----------------------------

Getting started with a new FPGA development board often requires going through a laborous and error-prone process of deriving toolchain configuration and constraint files from the supplied documentation. The Amaranth project includes a community-maintained repository of definitions for many open-source and commercial FPGA development boards.

These board definitions contain everything that is necessary to start using the board: FPGA family and model, clocks and resets, descriptions of on-board peripherals (including pin direction and attributes such as I/O standard), connector pinouts, and for boards with a built-in debug probe, the steps required to program the board. It takes a single Python invocation to generate, build, and download a test design that shows whether the board, toolchain, and programmer are working correctly.

Amaranth establishes a pin naming convention for many common peripherals (such as 7-segment displays, SPI flashes and SDRAM memories), enabling the reuse of unmodified interface code with many different boards. Further, the polarity of all control signals is unified to be active high, eliminating accidental polarity inversions and making simulation traces easier to follow; active low signals are inverted during I/O buffer instantiation.
