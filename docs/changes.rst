Changelog
#########

This document describes changes to the public interfaces in the Amaranth language and standard library. It does not include most bug fixes or implementation changes.


Version 0.4 (unreleased)
========================

Support has been added for a new and improved way of defining data structures in :mod:`amaranth.lib.data` and component interfaces in :mod:`amaranth.lib.wiring`, as defined in `RFC 1`_ and `RFC 2`_. :class:`Record` has been deprecated. In a departure from the usual policy, to give designers additional time to migrate, :class:`Record` will be removed in Amaranth 0.6 (one release later than normal).

Support for enumerations has been extended. A shape for enumeration members can be provided for an enumeration class, as defined in `RFC 3`_.

The language includes several new extension points for integration with :class:`Value` based data structures defined outside of the core language. In particular, ``Signal(shape)`` may now return a :class:`Signal` object wrapped in another if ``shape`` implements the call protocol, as defined in `RFC 15`_.

Several issues with shape inference have been resolved. Notably, ``a - b`` where both ``a`` and ``b`` are unsigned now returns a signed value.

Support for Python 3.6 and 3.7 has been removed, and support for Python 3.11 and 3.12 has been added.

Features deprecated in version 0.3 have been removed. In particular, the ``nmigen.*`` namespace is not provided, ``# nmigen:`` annotations are not recognized, and ``NMIGEN_*`` envronment variables are not used.


Migrating from version 0.3
--------------------------

Apply the following changes to code written against Amaranth 0.3 to migrate it to version 0.4:

* Update shell environment to use ``AMARANTH_*`` environment variables instead of ``NMIGEN_*`` environment variables.
* Update shell environment to use ``AMARANTH_ENV_<TOOLCHAIN>`` (with all-uppercase ``<TOOLCHAIN>`` name) environment variable names instead of ``AMARANTH_ENV_<Toolchain>`` or ``NMIGEN_ENV_<Toolchain>`` (with mixed-case ``<Toolchain>`` name).
* Update imports of the form ``from amaranth.vendor.some_vendor import SomeVendorPlatform`` to ``from amaranth.vendor import SomeVendorPlatform``. This change will reduce future churn.
* Replace uses of ``Const.normalize(value, shape)`` with ``Const(value, shape).value``.
* Replace uses of ``Repl(value, count)`` with ``value.replicate(count)``.
* Replace uses of ``Record`` with :mod:`amaranth.lib.data` and :mod:`amaranth.lib.wiring`. The appropriate replacement depends on the use case. If ``Record`` was being used for data storage and accessing the bit-level representation, use :mod:`amaranth.lib.data`. If ``Record`` was being used for connecting design components together, use :mod:`amaranth.lib.wiring`.
* Ensure the ``Pin`` instance returned by ``platform.request`` is not cast to value directly, but used for its fields. Replace code like ``leds = Cat(platform.request(led, n) for n in range(4))`` with ``leds = Cat(platform.request(led, n).o for n in range(4))`` (note the ``.o``).
* Remove uses of ``amaranth.lib.scheduler.RoundRobin`` by inlining or copying the implementation of that class.
* Remove uses of ``amaranth.lib.fifo.SyncFIFO(fwft=False)`` and ``amaranth.lib.fifo.FIFOInterface(fwft=False)`` by converting code to use ``fwft=True`` FIFOs or copying the implementation of those classes.

While code that uses the features listed as deprecated below will work in Amaranth 0.4, they will be removed in the next version.


Implemented RFCs
----------------

.. _RFC 1: https://amaranth-lang.org/rfcs/0001-aggregate-data-structures.html
.. _RFC 2: https://amaranth-lang.org/rfcs/0002-interfaces.html
.. _RFC 3: https://amaranth-lang.org/rfcs/0003-enumeration-shapes.html
.. _RFC 4: https://amaranth-lang.org/rfcs/0004-const-castable-exprs.html
.. _RFC 5: https://amaranth-lang.org/rfcs/0005-remove-const-normalize.html
.. _RFC 6: https://amaranth-lang.org/rfcs/0006-stdlib-crc.html
.. _RFC 8: https://amaranth-lang.org/rfcs/0008-aggregate-extensibility.html
.. _RFC 9: https://amaranth-lang.org/rfcs/0009-const-init-shape-castable.html
.. _RFC 10: https://amaranth-lang.org/rfcs/0010-move-repl-to-value.html
.. _RFC 15: https://amaranth-lang.org/rfcs/0015-lifting-shape-castables.html
.. _RFC 18: https://amaranth-lang.org/rfcs/0018-reorganize-vendor-platforms.html
.. _RFC 19: https://amaranth-lang.org/rfcs/0019-remove-scheduler.html
.. _RFC 20: https://amaranth-lang.org/rfcs/0020-deprecate-non-fwft-fifos.html
.. _RFC 22: https://amaranth-lang.org/rfcs/0022-valuecastable-shape.html
.. _RFC 28: https://amaranth-lang.org/rfcs/0028-override-value-operators.html


* `RFC 1`_: Aggregate data structure library
* `RFC 2`_: Interface definition library
* `RFC 3`_: Enumeration shapes
* `RFC 4`_: Constant-castable expressions
* `RFC 5`_: Remove ``Const.normalize``
* `RFC 6`_: CRC generator
* `RFC 8`_: Aggregate extensibility
* `RFC 9`_: Constant initialization for shape-castable objects
* `RFC 10`_: Move ``Repl`` to ``Value.replicate``
* `RFC 18`_: Reorganize vendor platforms
* `RFC 19`_: Remove ``amaranth.lib.scheduler``
* `RFC 15`_: Lifting shape-castable objects
* `RFC 20`_: Deprecate non-FWFT FIFOs
* `RFC 22`_: Define ``ValueCastable.shape()``
* `RFC 28`_: Allow overriding ``Value`` operators


Language changes
----------------

.. currentmodule:: amaranth.hdl

* Added: :class:`ShapeCastable`, similar to :class:`ValueCastable`.
* Added: :meth:`Value.as_signed` and :meth:`Value.as_unsigned` can be used on left-hand side of assignment (with no difference in behavior).
* Added: :meth:`Const.cast`. (`RFC 4`_)
* Added: :meth:`Value.matches` and ``with m.Case():`` accept any constant-castable objects. (`RFC 4`_)
* Added: :meth:`Value.replicate`, superseding :class:`Repl`. (`RFC 10`_)
* Added: :class:`Memory` supports transparent read ports with read enable.
* Changed: creating a :class:`Signal` with a shape that is a :class:`ShapeCastable` implementing :meth:`ShapeCastable.__call__` wraps the returned object using that method. (`RFC 15`_)
* Changed: :meth:`Value.cast` casts :class:`ValueCastable` objects recursively.
* Changed: :meth:`Value.cast` treats instances of classes derived from both :class:`enum.Enum` and :class:`int` (including :class:`enum.IntEnum`) as enumerations rather than integers.
* Changed: :meth:`Value.matches` with an empty list of patterns returns ``Const(1)`` rather than ``Const(0)``, to match the behavior of ``with m.Case():``.
* Changed: :class:`Cat` warns if an enumeration without an explicitly specified shape is used. (`RFC 3`_)
* Deprecated: :meth:`Const.normalize`; use ``Const(value, shape).value`` instead of ``Const.normalize(value, shape)``. (`RFC 5`_)
* Deprecated: :class:`Repl`; use :meth:`Value.replicate` instead. (`RFC 10`_)
* Deprecated: :class:`Record`; use :mod:`amaranth.lib.data` and :mod:`amaranth.lib.wiring` instead. (`RFC 1`_, `RFC 2`_)
* Removed: (deprecated in 0.1) casting of :class:`Shape` to and from a ``(width, signed)`` tuple.
* Removed: (deprecated in 0.3) :class:`ast.UserValue`.
* Removed: (deprecated in 0.3) support for ``# nmigen:`` linter instructions at the beginning of file.


Standard library changes
------------------------

.. currentmodule:: amaranth.lib

* Added: :mod:`amaranth.lib.enum`. (`RFC 3`_)
* Added: :mod:`amaranth.lib.data`. (`RFC 1`_)
* Added: :mod:`amaranth.lib.crc`. (`RFC 6`_)
* Deprecated: :mod:`amaranth.lib.scheduler`. (`RFC 19`_)
* Deprecated: :class:`amaranth.lib.fifo.FIFOInterface` with ``fwft=False``. (`RFC 20`_)
* Deprecated: :class:`amaranth.lib.fifo.SyncFIFO` with ``fwft=False``. (`RFC 20`_)


Toolchain changes
-----------------

.. currentmodule:: amaranth

* Changed: text files are written with LF line endings on Windows, like on other platforms.
* Added: ``debug_verilog`` override in :class:`build.TemplatedPlatform`.
* Added: ``env=`` argument to :meth:`build.run.BuildPlan.execute_local`.
* Deprecated: use of mixed-case toolchain environment variable names, such as ``NMIGEN_ENV_Diamond`` or ``AMARANTH_ENV_Diamond``; use upper-case environment variable names, such as ``AMARANTH_ENV_DIAMOND``.
* Removed: (deprecated in 0.3) :meth:`sim.Simulator.step`.
* Removed: (deprecated in 0.3) :mod:`back.pysim`.
* Removed: (deprecated in 0.3) support for invoking :func:`back.rtlil.convert()` and :func:`back.verilog.convert()` without an explicit `ports=` argument.
* Removed: (deprecated in 0.3) :mod:`test`.


Platform integration changes
----------------------------

.. currentmodule:: amaranth.vendor

* Added: ``icepack_opts`` override in :class:`vendor.LatticeICE40Platform`.
* Added: ``OSCH`` as ``default_clk`` clock source in :class:`vendor.LatticeMachXO2Platform`, :class:`vendor.LatticeMachXO3LPlatform`.
* Added: Xray toolchain support in :class:`vendor.XilinxPlatform`.
* Added: :class:`vendor.GowinPlatform`.
* Deprecated: :mod:`vendor.intel`, :mod:`vendor.lattice_ecp5`, :mod:`vendor.lattice_ice40`, :mod:`vendor.lattice_machxo2_3l`, :mod:`vendor.quicklogic`, :mod:`vendor.xilinx`; import platforms directly from :mod:`vendor` instead. (`RFC 18`_)
* Removed: (deprecated in 0.3) :mod:`lattice_machxo2`
* Removed: (deprecated in 0.3) :class:`lattice_machxo_2_3l.LatticeMachXO2Or3LPlatform` SVF programming vector ``{{name}}.svf``.
* Removed: (deprecated in 0.3) :class:`xilinx_spartan_3_6.XilinxSpartan3APlatform`, :class:`xilinx_spartan_3_6.XilinxSpartan6Platform`, :class:`xilinx_7series.Xilinx7SeriesPlatform`, :class:`xilinx_ultrascale.XilinxUltrascalePlatform`.


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
* Added: Division and modulo operators can be used with a negative divisor.
* Deprecated: ``# nmigen:`` linter instructions at the beginning of file; use ``# amaranth:`` instead.


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
* Deprecated: ``NMIGEN_*`` environment variables; use ``AMARANTH_*`` environment variables instead.


Platform integration changes
----------------------------

.. currentmodule:: amaranth.vendor

* Added: ``SB_LFOSC`` and ``SB_HFOSC`` as ``default_clk`` clock sources in :class:`lattice_ice40.LatticeICE40Platform`.
* Added: :class:`lattice_machxo2.LatticeMachXO2Platform` generates binary (``.bit``) bitstreams.
* Added: :class:`lattice_machxo_2_3l.LatticeMachXO3LPlatform`.
* Deprecated: :mod:`lattice_machxo2`; use :class:`lattice_machxo_2_3l.LatticeMachXO2Platform` instead.
* Removed: :class:`xilinx_7series.Xilinx7SeriesPlatform.grade`; this family has no temperature grades.
* Removed: :class:`xilinx_ultrascale.XilinxUltrascalePlatform.grade`; this family has temperature grade as part of speed grade.
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
