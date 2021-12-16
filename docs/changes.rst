Changelog
#########

This document describes changes to the public interfaces in the Amaranth language and standard library. It does not include most bug fixes or implementation changes.


Version 0.3
============

The project has been renamed from nMigen to Amaranth.

Features deprecated in version 0.2 have been removed.


Migrating from version 0.2
--------------------------

.. currentmodule:: amaranth

Apply the following changes to code written against nMigen 0.2 to migrate it to Amaranth 0.3:

* Update ``import nmigen as nm`` :ref:`explicit prelude imports <lang-prelude>` to be ``import amaranth as am``, and adjust the code to use the ``am.*`` namespace.
* Update ``import nmigen.*`` imports to be ``import amaranth.*``.
* Update ``import nmigen_boards.*`` imports to be ``import amaranth_boards.*``.
* Update board definitions using :class:`vendor.lattice_machxo2.LatticeMachXO2Platform` to use :class:`vendor.lattice_machxo_2_3l.LatticeMachXO2Platform`.
* Update board definitions using :class:`vendor.xilinx_spartan_3_6.XilinxSpartan3APlatform`, :class:`vendor.xilinx_spartan_3_6.XilinxSpartan6Platform`, :class:`vendor.xilinx_7series.Xilinx7SeriesPlatform`, :class:`vendor.xilinx_ultrascale.XilinxUltrascalePlatform` to use :class:`vendor.xilinx.XilinxPlatform`.
* Switch uses of :class:`hdl.ast.UserValue` to :class:`ValueCastable`; note that :class:`ValueCastable` does not inherit from :class:`Value`, and inheriting from :class:`Value` is not supported.
* Switch uses of :mod:`back.pysim` to :mod:`sim`.
* Add an explicit ``ports=`` argument to uses of :func:`back.rtlil.convert` and :func:`back.verilog.convert` if missing.
* Remove uses of :class:`test.utils.FHDLTestCase` and vendor the implementation of :class:`test.utils.FHDLTestCase.assertFormal` if necessary.

While code that uses the features listed as deprecated below will work in Amaranth 0.3, they will be removed in the next version.


Language changes
----------------

.. currentmodule:: amaranth.hdl

* Added: :class:`Value` can be used with :func:`abs`.
* Added: :meth:`Value.rotate_left` and :meth:`Value.rotate_right`.
* Added: :meth:`Value.shift_left` and :meth:`Value.shift_right`.
* Added: :class:`ValueCastable`.
* Deprecated: :class:`ast.UserValue`; use :class:`ValueCastable` instead.
* Added: Divison and modulo operators can be used with a negative divisor.


Standard library changes
------------------------

.. currentmodule:: amaranth.lib

* Added: :class:`cdc.PulseSynchronizer`.
* Added: :class:`cdc.AsyncFFSynchronizer`.
* Changed: :class:`fifo.AsyncFIFO` is reset when the write domain is reset.
* Added: :attr:`fifo.AsyncFIFO.r_rst` is asserted when the write domain is reset.
* Added: :attr:`fifo.FIFOInterface.r_level` and :attr:`fifo.FIFOInterface.w_level`.


Toolchain changes
-----------------

.. currentmodule:: amaranth

* Changed: Backend and simulator reject wires larger than 65536 bits.
* Added: Backend emits Yosys enumeration attributes for :ref:`enumeration-shaped <lang-shapeenum>` signals.
* Added: If a compatible Yosys version is not installed, :mod:`back.verilog` will fall back to the `amaranth-yosys <https://github.com/amaranth-lang/amaranth-yosys>`_ PyPI package. The package can be :ref:`installed <install>` as ``amaranth[builtin-yosys]`` to ensure this dependency is available.
* Added: :mod:`back.cxxrtl`.
* Added: :mod:`sim`, a simulator interface with support for multiple simulation backends.
* Deprecated: :mod:`back.pysim`; use :mod:`sim` instead.
* Removed: The ``with Simulator(fragment, ...) as sim:`` form.
* Removed: :meth:`sim.Simulator.add_process` with a generator argument.
* Deprecated: :meth:`sim.Simulator.step`; use :meth:`sim.Simulator.advance` instead.
* Added: :meth:`build.BuildPlan.execute_remote_ssh`.
* Deprecated: :class:`test.utils.FHDLTestCase`, with no replacement.
* Deprecated: :func:`back.rtlil.convert()` and :func:`back.verilog.convert()` without an explicit `ports=` argument.
* Changed: VCD output now uses a top-level "bench" module that contains testbench only signals.


Platform integration changes
----------------------------

.. currentmodule:: amaranth.vendor

* Added: ``SB_LFOSC`` and ``SB_HFOSC`` as ``default_clk`` clock sources in :class:`lattice_ice40.LatticeICE40Platform`, .
* Added: :class:`lattice_machxo2.LatticeMachXO2Platform` generates binary (``.bit``) bitstreams.
* Added: :class:`lattice_machxo_2_3l.LatticeMachXO3LPlatform`.
* Deprecated: :mod:`lattice_machxo2`; use :class:`lattice_machxo_2_3l.LatticeMachXO2Platform` instead.
* Removed: :class:`xilinx_7series.Xilinx7SeriesPlatform.grade`; this family has no temperature grades.
* Removed: and :class:`xilinx_ultrascale.XilinxUltrascalePlatform.grade`; this family has temperature grade as part of speed grade.
* Added: Symbiflow toolchain support for :class:`xilinx_7series.Xilinx7SeriesPlatform`.
* Added: :class:`lattice_machxo_2_3l.LatticeMachXO2Or3LPlatform` generates separate Flash and SRAM SVF programming vectors, ``{{name}}_flash.svf`` and ``{{name}}_sram.svf``.
* Deprecated: :class:`lattice_machxo_2_3l.LatticeMachXO2Or3LPlatform` SVF programming vector ``{{name}}.svf``; use ``{{name}}_flash.svf`` instead.
* Added: :class:`quicklogic.QuicklogicPlatform`.
* Added: ``cyclonev_oscillator`` as ``default_clk`` clock source in :class:`intel.IntelPlatform`.
* Added: ``add_settings`` and ``add_constraints`` overrides in :class:`intel.IntelPlatform`.
* Added: :class:`xilinx.XilinxPlatform`.
* Deprecated: :class:`xilinx_spartan_3_6.XilinxSpartan3APlatform`, :class:`xilinx_spartan_3_6.XilinxSpartan6Platform`, :class:`xilinx_7series.Xilinx7SeriesPlatform`, :class:`xilinx_ultrascale.XilinxUltrascalePlatform`; use :class:`xilinx.XilinxPlatform` instead.
* Added: Mistral toolchain support for :class:`intel.IntelPlatform`.
* Added: ``synth_design_opts`` override in :class:`xilinx.XilinxPlatform`.


Versions 0.1, 0.2
=================

No changelog is provided for these versions.

The PyPI packages were published under the ``nmigen`` namespace, rather than ``amaranth``.
