Standard library
################

The :mod:`amaranth.lib` module, also known as the standard library, provides modules that falls into one of the three categories:

1. Modules that will used by essentially all idiomatic Amaranth code, or which are necessary for interoperability. This includes :mod:`amaranth.lib.enum` (enumerations), :mod:`amaranth.lib.data` (data structures), :mod:`amaranth.lib.wiring` (interfaces and components), :mod:`amaranth.lib.meta` (interface metadata), and :mod:`amaranth.lib.stream` (data streams).
2. Modules that abstract common functionality whose implementation differs between hardware platforms. This includes :mod:`amaranth.lib.memory` and :mod:`amaranth.lib.cdc`.
3. Modules that have essentially one correct implementation and are of broad utility in digital designs. This includes :mod:`amaranth.lib.fifo`, and :mod:`amaranth.lib.crc`.

As part of the Amaranth backwards compatibility guarantee, any behaviors described in these documents will not change from a version to another without at least one version including a warning about the impending change. Any nontrivial change to these behaviors must also go through the public review as a part of the `Amaranth Request for Comments process <https://amaranth-lang.org/rfcs/>`_.

The Amaranth standard library is separate from the Amaranth language: everything provided in it could have been implemented in a third-party library.

.. toctree::
   :maxdepth: 2

   stdlib/enum
   stdlib/data
   stdlib/wiring
   stdlib/meta
   stdlib/stream
   stdlib/memory
   stdlib/io
   stdlib/cdc
   stdlib/fifo
   stdlib/crc
