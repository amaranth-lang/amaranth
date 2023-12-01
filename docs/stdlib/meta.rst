.. _meta:

Interface metadata
##################

.. py:module:: amaranth.lib.meta

The :mod:`amaranth.lib.meta` module provides a way to annotate objects in an Amaranth design and exchange these annotations with external tools in a standardized format.

.. _JSON Schema: https://json-schema.org

.. _"$id" keyword: https://json-schema.org/draft/2020-12/draft-bhutton-json-schema-01#name-the-id-keyword

.. testsetup::

    from amaranth import *
    from amaranth.lib import wiring, meta
    from amaranth.lib.wiring import In, Out


Introduction
------------

Many Amaranth designs stay entirely within the Amaranth ecosystem, using the facilities it provides to define, test, and build hardware. In this case, the design is available for exploration using Python code, and metadata is not necessary. However, if an Amaranth design needs to fit into an existing ecosystem, or, conversely, to integrate components developed for another ecosystem, metadata can be used to exchange structured information about the design.

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

While it can be easily converted to Verilog, external tools will find the interface of the resulting module opaque unless they parse its Verilog source (a difficult and unrewarding task), or are provided with a description of it. Components can describe their signature with JSON-based metadata:

.. doctest::

    >>> adder = Adder()
    >>> adder.metadata # doctest: +ELLIPSIS
    <amaranth.lib.wiring.ComponentMetadata for ...Adder object at ...>
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
                    'init': '0'
                },
                'b': {
                    'type': 'port',
                    'name': 'b',
                    'dir': 'in',
                    'width': 32,
                    'signed': False,
                    'init': '0'
                },
                'o': {
                    'type': 'port',
                    'name': 'o',
                    'dir': 'out',
                    'width': 33,
                    'signed': False,
                    'init': '0'
                }
            },
            'annotations': {}
        }
    }

.. testcode::
    :hide:

    # The way doctest requires this object to be formatted is truly hideous, even with +NORMALIZE_WHITESPACE.
    assert adder.metadata.as_json() == {'interface': {'members': {'a': {'type': 'port', 'name': 'a', 'dir': 'in', 'width': 32, 'signed': False, 'init': '0'}, 'b': {'type': 'port', 'name': 'b', 'dir': 'in', 'width': 32, 'signed': False, 'init': '0'}, 'o': {'type': 'port', 'name': 'o', 'dir': 'out', 'width': 33, 'signed': False, 'init': '0'}}, 'annotations': {}}}


All metadata in Amaranth must adhere to a schema in the `JSON Schema`_ language, which is integral to its definition, and can be used to validate the generated JSON:

.. doctest::

    >>> wiring.ComponentMetadata.validate(adder.metadata.as_json())

The built-in component metadata can be extended to provide arbitrary information about an interface through user-defined annotations. For example, a memory bus interface could provide the layout of any memory-mapped peripherals accessible through that bus.


Defining annotations
--------------------

Consider a simple control and status register (CSR) bus that provides the memory layout of the accessible registers via an annotation:

.. testcode::

    class CSRLayoutAnnotation(meta.Annotation):
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://amaranth-lang.org/schema/example/0/csr-layout.json",
            "type": "object",
            "properties": {
                "registers": {
                    "type": "object",
                    "patternProperties": {
                        "^.+$": {
                            "type": "integer",
                            "minimum": 0,
                        },
                    },
                },
            },
            "requiredProperties": [
                "registers",
            ],
        }

        def __init__(self, origin):
            self._origin = origin

        @property
        def origin(self):
            return self._origin

        def as_json(self):
            instance = {
                "registers": self.origin.registers,
            }
            # Validating the value returned by `as_json()` ensures its conformance.
            self.validate(instance)
            return instance


    class CSRSignature(wiring.Signature):
        def __init__(self):
            super().__init__({
                "addr":     Out(16),
                "w_en":     Out(1),
                "w_data":   Out(32),
                "r_en":     Out(1),
                "r_data":   In(32),
            })

        def annotations(self, obj, /):
            # Unfortunately `super()` cannot be used in `wiring.Signature` subclasses;
            # instead, use a direct call to a superclass method. In this case that is
            # `wiring.Signature` itself, but in a more complex class hierarchy it could
            # be different.
            return wiring.Signature.annotations(self, obj) + (CSRLayoutAnnotation(obj),)

A component that embeds a few CSR registers would define their addresses:

.. testcode::

    class MyPeripheral(wiring.Component):
        csr_bus: In(CSRSignature())

        def __init__(self):
            super().__init__()
            self.csr_bus.registers = {
                "control": 0x0000,
                "status":  0x0004,
                "data":    0x0008,
            }

.. doctest::

    >>> peripheral = MyPeripheral()
    >>> peripheral.metadata.as_json() # doctest: +SKIP
    {
        'interface': {
            'members': {
                'csr_bus': {
                    'type': 'interface',
                    'members': {
                        'addr': {
                            'type': 'port',
                            'name': 'csr_bus__addr',
                            'dir': 'in',
                            'width': 16,
                            'signed': False,
                            'init': '0'
                        },
                        'w_en': {
                            'type': 'port',
                            'name': 'csr_bus__w_en',
                            'dir': 'in',
                            'width': 1,
                            'signed': False,
                            'init': '0'
                        },
                        'w_data': {
                            'type': 'port',
                            'name': 'csr_bus__w_data',
                            'dir': 'in',
                            'width': 32,
                            'signed': False,
                            'init': '0'
                        },
                        'r_en': {
                            'type': 'port',
                            'name': 'csr_bus__r_en',
                            'dir': 'in',
                            'width': 1,
                            'signed': False,
                            'init': '0'
                        },
                        'r_data': {
                            'type': 'port',
                            'name': 'csr_bus__r_data',
                            'dir': 'out',
                            'width': 32,
                            'signed': False,
                            'init': '0'
                        },
                    },
                    'annotations': {
                        'https://amaranth-lang.org/schema/example/0/csr-layout.json': {
                            'registers': {
                                'control': 0,
                                'status':  4,
                                'data':    8
                            }
                        }
                    }
                }
            },
            'annotations': {}
        }
    }

.. testcode::
    :hide:

    # The way doctest requires this object to be formatted is truly hideous, even with +NORMALIZE_WHITESPACE.
    assert peripheral.metadata.as_json() == {'interface': {'members': {'csr_bus': {'type': 'interface', 'members': {'addr': {'type': 'port', 'name': 'csr_bus__addr', 'dir': 'in', 'width': 16, 'signed': False, 'init': '0'}, 'w_en': {'type': 'port', 'name': 'csr_bus__w_en', 'dir': 'in', 'width': 1, 'signed': False, 'init': '0'}, 'w_data': {'type': 'port', 'name': 'csr_bus__w_data', 'dir': 'in', 'width': 32, 'signed': False, 'init': '0'}, 'r_en': {'type': 'port', 'name': 'csr_bus__r_en', 'dir': 'in', 'width': 1, 'signed': False, 'init': '0'}, 'r_data': {'type': 'port', 'name': 'csr_bus__r_data', 'dir': 'out', 'width': 32, 'signed': False, 'init': '0'}}, 'annotations': {'https://amaranth-lang.org/schema/example/0/csr-layout.json': {'registers': {'control': 0, 'status': 4, 'data': 8}}}}}, 'annotations': {}}}


Identifying schemas
-------------------

An :class:`Annotation` schema must have a ``"$id"`` property, whose value is a URL that serves as its globally unique identifier. The suggested format of this URL is:

.. code::

    <protocol>://<domain>/schema/<package>/<version>/<path>.json

where:

    * ``<domain>`` is a domain name registered to the person or entity defining the annotation;
    * ``<package>`` is the name of the Python package providing the :class:`Annotation` subclass;
    * ``<version>`` is the version of that package;
    * ``<path>`` is a non-empty string specific to the annotation.

.. note::

    Annotations used in the Amaranth project packages are published under https://amaranth-lang.org/schema/ according to this URL format, and are covered by the usual compatibility commitment.

    Other projects that define additional Amaranth annotations are encouraged, but not required, to make their schemas publicly accessible; the only requirement is for the URL to be globally unique.


Reference
---------

.. autoexception:: InvalidSchema

.. autoexception:: InvalidAnnotation

.. autoclass:: Annotation
    :no-members:
    :members: validate, origin, as_json

    .. automethod:: __init_subclass__()

    .. autoattribute:: schema
        :annotation: = { "$id": "...", ... }
