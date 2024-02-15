Metadata
########

.. py:module:: amaranth.lib.meta

The :mod:`amaranth.lib.meta` module provides a way to annotate objects in an Amaranth design and
exchange these annotations with external tools in a standardized format.

.. _JSON Schema: https://json-schema.org

.. testsetup::

    from amaranth import *
    from amaranth.lib import wiring
    from amaranth.lib.wiring import In, Out


Introduction
------------

Many Amaranth designs stay entirely within the Amaranth ecosystem, using the facilities it provides
to define, test, and build hardware. In this case, the design is available for exploration using
Python code, and metadata is not necessary. However, if an Amaranth design needs to fit into
an existing ecosystem, or, conversely, to integrate components developed for another ecosystem,
metadata can be used to exchange structured information about the design.

Consider a simple :ref:`component <wiring>`:

.. testcode::

    class Adder(wiring.Component):
        a: In(unsigned(32))
        b: In(unsigned(32))
        o: Out(unsigned(33))

        def elaborate(self, platform):
            m = Module()
            m.d.comb += self.o.eq(self.a + self.b)
            return m

..
    TODO: link to Verilog backend doc when we have it

While it can be easily converted to Verilog, external tools will find the interface of
the resulting module opaque unless they parse its Verilog source (a difficult and unrewarding task),
or are provided with a description of it. Components can describe their signature with JSON-based
metadata:

.. doctest::

    >>> adder = Adder()
    >>> adder.metadata # doctest: +ELLIPSIS
    <amaranth.lib.wiring.ComponentMetadata for <Adder object at ...>>
    >>> adder.metadata.as_json() # doctest: +SKIP
    {
        'interface': {
            'members': {
                'a': {
                    'type': 'port',
                    'name': 'a',
                    'dir': 'in',
                    'width': 32,
                    'signed': False,
                    'reset': '0'
                },
                'b': {
                    'type': 'port',
                    'name': 'b',
                    'dir': 'in',
                    'width': 32,
                    'signed': False,
                    'reset': '0'
                },
                'o': {
                    'type': 'port',
                    'name': 'o',
                    'dir': 'out',
                    'width': 33,
                    'signed': False,
                    'reset': '0'
                }
            },
            'annotations': {}
        }
    }

.. testcode::
    :hidden:

    # The way doctest requires this object to be formatted is truly hideous, even with +NORMALIZE_WHITESPACE.
    assert adder.metadata.as_json() == {'interface': {'members': {'a': {'type': 'port', 'name': 'a', 'dir': 'in', 'width': 32, 'signed': False, 'reset': '0'}, 'b': {'type': 'port', 'name': 'b', 'dir': 'in', 'width': 32, 'signed': False, 'reset': '0'}, 'o': {'type': 'port', 'name': 'o', 'dir': 'out', 'width': 33, 'signed': False, 'reset': '0'}}, 'annotations': {}}}


All metadata in Amaranth must adhere to a schema in the `JSON Schema`_ language, which is integral
to its definition, and can be used to validate the generated JSON:

.. doctest::

    >>> wiring.ComponentMetadata.validate(adder.metadata.as_json())


Defining annotations
--------------------

.. todo:: Write this.


Publishing schemas
------------------

.. todo:: Write this

An ``Annotation`` schema must have a ``"$id"`` property, which holds an URL that serves as its
unique identifier. The suggested format of this URL is:

    <protocol>://<domain>/schema/<package>/<version>/<path>.json

where:
    * ``<domain>`` is a domain name registered to the person or entity defining the annotation;
    * ``<package>`` is the name of the Python package providing the ``Annotation`` subclass;
    * ``<version>`` is the version of the aforementioned package;
    * ``<path>`` is a non-empty string specific to the annotation.


Reference
---------

.. todo::

    Write this.

.. autoclass:: Annotation
    :no-members:
    :members: validate, origin, as_json

    .. autoattribute:: schema
        :annotation: = { "$id": "...", ... }
