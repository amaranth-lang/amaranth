Language reference
##################

.. py:module:: amaranth.hdl

.. warning::

    This reference is a work in progress and is seriously incomplete!

    While the wording below states that anything not described in this document isn't covered by the backwards compatibility guarantee, this should be ignored until the document is complete and this warning is removed.

This reference describes the Python classes that underlie the Amaranth language's syntax. It assumes familiarity with the :doc:`language guide <guide>`.


.. _lang-stability:

Backwards compatibility
=======================

As part of the Amaranth backwards compatibility guarantee, any behaviors described in this document will not change from a version to another without at least one version including a warning about the impending change. Any nontrivial change to these behaviors must also go through the public review as a part of the `Amaranth Request for Comments process <https://amaranth-lang.org/rfcs/>`_.

Conversely, any behavior not documented here is subject to change at any time with or without notice, and any names under the :mod:`amaranth.hdl` module that are not explicitly included in this document, even if they do not begin with an underscore, are internal to the implementation of the language.


.. _lang-importing:

Importing syntax
================

There are two ways to import the Amaranth syntax into a Python file: by importing the :ref:`prelude <lang-prelude>` or by importing individual names from the :mod:`amaranth.hdl` module. Since the prelude is kept small and rarely extended to avoid breaking downstream code that uses a glob import, there are some names that are only exported from the :mod:`amaranth.hdl` module. The following three snippets are equivalent:

.. testcode::

    from amaranth import *

    m = Module()

.. testcode::

    import amaranth as am

    m = am.Module()

.. testcode::

    from amaranth.hdl import Module

    m = Module()

The prelude exports exactly the following names:

.. must be kept in sync with amaranth/__init__.py!

* :class:`Shape`
* :func:`unsigned`
* :func:`signed`
* :class:`Value`
* :class:`Const`
* :func:`C`
* :func:`Mux`
* :func:`Cat`
* :class:`Array`
* :class:`Signal`
* :class:`ClockSignal`
* :class:`ResetSignal`
* :class:`Format`
* :class:`Print`
* :func:`Assert`
* :class:`Module`
* :class:`ClockDomain`
* :class:`Elaboratable`
* :class:`Fragment`
* :class:`Instance`
* :class:`Memory`
* :class:`DomainRenamer`
* :class:`ResetInserter`
* :class:`EnableInserter`


.. _lang-srcloc:

Source locations
================

Many functions and methods in Amaranth take the :py:`src_loc_at=0` keyword argument. These language constructs may inspect the call stack to determine the file and line of its call site, which will be used to annotate generated code when a netlist is generated or to improve diagnostic messages.

Some call sites are not relevant for an Amaranth designer; e.g. when an Amaranth language construct is called from a user-defined utility function, the source location of the call site within this utility function is usually not interesting to the designer. In these cases, one or more levels of function calls can be removed from consideration using the :py:`src_loc_at` argument as follows (using :meth:`Shape.cast` to demonstrate the concept):

.. testcode::

    def my_shape_cast(obj, *, src_loc_at=0):
        ... # additionally process `obj`...
        return Shape.cast(obj, src_loc_at=1 + src_loc_at)

The number :py:`1` corresponds to the number of call stack frames that should be skipped.


Shapes
======

See also the introduction to :ref:`shapes <lang-shapes>` and :ref:`casting from shape-like objects <lang-shapelike>` in the language guide.

.. autoclass:: Shape
.. autofunction:: unsigned
.. autofunction:: signed
.. autoclass:: ShapeCastable()
.. autoclass:: ShapeLike()


Values
======

See also the introduction to :ref:`values <lang-values>` and :ref:`casting from value-like objects <lang-valuelike>` in the language guide.

.. autoclass:: Value
    :special-members: __bool__, __pos__, __neg__, __add__, __radd__, __sub__, __rsub__, __mul__, __rmul__, __mod__, __rmod__, __floordiv__, __rfloordiv__, __eq__, __ne__, __lt__, __le__, __gt__, __ge__, __abs__, __invert__, __and__, __rand__, __or__, __ror__, __xor__, __rxor__, __lshift__, __rlshift__, __rshift__, __rrshift__, __len__, __getitem__, __contains__, __hash__
.. autoclass:: ValueCastable()
.. autoclass:: ValueLike()
