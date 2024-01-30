Standard library
################

The :mod:`amaranth.lib` module, also known as the standard library, provides modules that falls into one of the three categories:

1. Modules that will used by essentially all idiomatic Amaranth code, and are necessary for interoperability. This includes :mod:`amaranth.lib.enum` (enumerations), :mod:`amaranth.lib.data` (data structures), and :mod:`amaranth.lib.wiring` (interfaces and components).
2. Modules that abstract common functionality whose implementation differs between hardware platforms. This includes :mod:`amaranth.lib.cdc`.
3. Modules that have essentially one correct implementation and are of broad utility in digital designs. This includes :mod:`amaranth.lib.coding`, :mod:`amaranth.lib.fifo`, and :mod:`amaranth.lib.crc`.

As part of the Amaranth backwards compatibility guarantee, any behaviors described in these documents will not change from a version to another without at least one version including a warning about the impending change. Any nontrivial change to these behaviors must also go through the public review as a part of the `Amaranth Request for Comments process <https://amaranth-lang.org/rfcs/>`_.

The Amaranth standard library is separate from the Amaranth language: everything provided in it could have been implemented in a third-party library.

.. toctree::
   :maxdepth: 2

   stdlib/enum
   stdlib/data
   stdlib/wiring
   stdlib/cdc
   stdlib/coding
   stdlib/fifo
   stdlib/crc
