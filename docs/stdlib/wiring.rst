.. _wiring:

Interfaces and connections
##########################

.. py:module:: amaranth.lib.wiring

The :mod:`amaranth.lib.wiring` module provides a way to declare the interfaces between design components and connect them to each other in a reliable and convenient way.

.. testsetup::

   from amaranth import *


.. _wiring-introduction:

Introduction
============

Overview
++++++++

This module provides four related facilities:

1. Description and construction of interface objects via :class:`Flow` (:data:`In` and :data:`Out`), :class:`Member`, and :class:`Signature`, as well as the associated container class :class:`SignatureMembers`. These classes provide the syntax used in defining components, and are also useful for introspection.
2. Flipping of signatures and interface objects via :class:`FlippedSignature` and :class:`FlippedInterface`, as well as the associated container class :class:`FlippedSignatureMembers`. This facility reduces boilerplate by adapting existing signatures and interface objects: the flip operation changes the :data:`In` data flow of a member to :data:`Out` and vice versa.
3. Connecting interface objects together via :func:`connect`. The :func:`connect` function ensures that the provided interface objects can be connected to each other, and adds the necessary :py:`.eq()` statements to a :class:`Module`.
4. Defining reusable, self-contained components via :class:`Component`. Components are :class:`Elaboratable` objects that interact with the rest of the design through an interface specified by their signature.

To use this module, add the following imports to the beginning of the file:

.. testcode::

   from amaranth.lib import wiring
   from amaranth.lib.wiring import In, Out

The :ref:`"Motivation" <wiring-intro1>` and :ref:`"Reusable interfaces" <wiring-intro2>` sections describe concepts that are essential for using this module and writing idiomatic Amaranth code. The sections after describe advanced use cases that are only relevant for more complex code.


.. _wiring-intro1:

Motivation
++++++++++

Consider a reusable counter with an enable input, configurable limit, and an overflow flag. Using only the core Amaranth language, it could be implemented as:

.. testcode::

    class BasicCounter(Elaboratable):
        def __init__(self):
            self.en  = Signal()

            self.count = Signal(8)
            self.limit = Signal.like(self.count)

            self.overflow  = Signal()

        def elaborate(self, platform):
            m = Module()

            with m.If(self.en):
                m.d.sync += self.overflow.eq(0)
                with m.If(self.count == self.limit):
                    m.d.sync += self.overflow.eq(1)
                    m.d.sync += self.count.eq(0)
                with m.Else():
                    m.d.sync += self.count.eq(self.count + 1)

            return m

Nothing in this implementation indicates the directions of its ports (:py:`en`, :py:`count`, :py:`limit`, and :py:`overflow`) in relation to other parts of the design. To understand whether the value of a port is expected to be provided externally or generated internally, it is first necessary to read the body of the :py:`elaborate` method. If the port is not used within that method in a particular elaboratable, it is not possible to determine its direction, or whether it is even meant to be connected.

The :mod:`amaranth.lib.wiring` module provides a solution for this problem: *components*. A component is an elaboratable that declares the shapes and directions of its ports in its *signature*. The example above can be rewritten to use the :class:`Component` base class (which itself inherits from :class:`Elaboratable`) to be:

.. testcode::

    class ComponentCounter(wiring.Component):
        en: In(1)

        count: Out(8)
        limit: In(8)

        overflow: Out(1)

        def elaborate(self, platform):
            m = Module()

            with m.If(self.en):
                m.d.sync += self.overflow.eq(0)
                with m.If(self.count == self.limit):
                    m.d.sync += self.overflow.eq(1)
                    m.d.sync += self.count.eq(0)
                with m.Else():
                    m.d.sync += self.count.eq(self.count + 1)

            return m

The code in the constructor *creating* the signals of the counter's interface one by one is now gone, replaced with the :term:`variable annotations <python:variable annotation>` *declaring* the counter's interface. The inherited constructor, :meth:`Component.__init__`, creates the same attributes with the same values as before, and the :py:`elaborate` method is unchanged.

The major difference between the two examples is that the :py:`ComponentCounter` provides unambiguous answers to two questions that previously required examining the :py:`elaborate` method:

1. Which of the Python object's attributes are ports that are intended to be connected to the rest of the design.
2. What is the direction of the flow of information through the port.

This information, aside from being clear from the source code, can now be retrieved from the :py:`.signature` attribute, which contains an instance of the :class:`Signature` class:

.. doctest::

    >>> ComponentCounter().signature
    Signature({'en': In(1), 'count': Out(8), 'limit': In(8), 'overflow': Out(1)})

The :ref:`shapes <lang-shapes>` of the ports need not be static. The :py:`ComponentCounter` can be made generic, with its range specified when it is constructed, by creating the signature explicitly in its constructor:

.. testcode::

    class GenericCounter(wiring.Component):
        def __init__(self, width):
            super().__init__({
                "en": In(1),

                "count": Out(width),
                "limit": In(width),

                "overflow": Out(1)
            })

        # The implementation of the `elaborate` method is the same.
        elaborate = ComponentCounter.elaborate

.. doctest::

    >>> GenericCounter(16).signature
    Signature({'en': In(1), 'count': Out(16), 'limit': In(16), 'overflow': Out(1)})

Instances of the :class:`ComponentCounter` and :class:`GenericCounter` class are two examples of *interface objects*. An interface object is a Python object of any type whose a :py:`signature` attribute contains a :class:`Signature` with which the interface object is compliant (as determined by the :meth:`is_compliant <Signature.is_compliant>` method of the signature).

The next section introduces the concepts of directionality and connection, and discusses interface objects in more detail.


.. _wiring-intro2:

Reusable interfaces
+++++++++++++++++++

Consider a more complex example where two components are communicating with a *stream* that is using *ready/valid signaling*, where the :py:`valid` signal indicates that the value of :py:`data` provided by the source is meaningful, and the :py:`ready` signal indicates that the sink has consumed the data word:

.. testcode::

    class DataProducer(wiring.Component):
        en: In(1)

        data: Out(8)
        valid: Out(1)
        ready: In(1)

        def elaborate(self, platform): ...


    class DataConsumer(wiring.Component):
        data: In(8)
        valid: In(1)
        ready: Out(1)

        # ... other ports...

        def elaborate(self, platform): ...

Data would be transferred between these components by assigning the outputs to the inputs elsewhere in the design:

.. testcode::

    m = Module()
    m.submodules.producer = producer = DataProducer()
    m.submodules.consumer = consumer = DataConsumer()

    ...

    m.d.comb += [
        consumer.data.eq(producer.data),
        consumer.valid.eq(producer.valid),
        producer.ready.eq(consumer.ready),
    ]

Although this example is short, it is already repetitive and redundant. The ports on the producer and the consumer, which must match each other for the connection to be made correctly, are declared twice; and the connection itself is made in an error-prone manual way even though the signatures include all of the information required to create it.

The signature of a stream could be defined in a generic way:

.. testcode::

    class SimpleStreamSignature(wiring.Signature):
        def __init__(self, data_shape):
            super().__init__({
                "data": Out(data_shape),
                "valid": Out(1),
                "ready": In(1)
            })

        def __eq__(self, other):
            return self.members == other.members

.. doctest::

    >>> SimpleStreamSignature(8).members
    SignatureMembers({'data': Out(8), 'valid': Out(1), 'ready': In(1)})

A definition like this is usable, depending on the data flow direction of the members, only in the producer (as in the code above) or only in the consumer. To resolve this problem, this module introduces *flipping*: an operation that reverses the data flow direction of the members of a signature or an interface object while leaving everything else about the object intact. In Amaranth, the (non-flipped) signature definition always declares the data flow directions appropriate for a bus initiator, stream source, controller, and so on. A bus target, stream sink, peripheral, and so on would reuse the source definition by flipping it.

A signature is flipped by calling :meth:`sig.flip() <Signature.flip>`, and an interface object is flipped by calling :func:`flipped(intf) <flipped>`. These calls return instances of the :class:`FlippedSignature` and :class:`FlippedInterface` classes, respectively, which use metaprogramming to wrap another object, changing only the data flow directions of its members and forwarding all other method calls and attribute accesses to the wrapped object.

The example above can be rewritten to use this definition of a stream signature as:

.. testcode::

    class StreamProducer(wiring.Component):
        en: In(1)
        source: Out(SimpleStreamSignature(8))

        def elaborate(self, platform): ...


    class StreamConsumer(wiring.Component):
        sink: Out(SimpleStreamSignature(8).flip())

        def elaborate(self, platform): ...


    m = Module()
    m.submodules.producer = producer = StreamProducer()
    m.submodules.consumer = consumer = StreamConsumer()

The producer and the consumer reuse the same signature, relying on flipping to make the port directions complementary:

.. doctest::

    >>> producer.source.signature.members
    SignatureMembers({'data': Out(8), 'valid': Out(1), 'ready': In(1)})
    >>> producer.source.signature.members['data']
    Out(8)
    >>> consumer.sink.signature.members
    SignatureMembers({'data': Out(8), 'valid': Out(1), 'ready': In(1)}).flip()
    >>> consumer.sink.signature.members['data']
    In(8)

In the :py:`StreamConsumer` definition above, the :py:`sink` member has its direction flipped explicitly because the sink is a stream input; this is the case for every interface due to how port directions are defined. Since this operation is so ubiquitous, it is also performed when :py:`In(...)` is used with a signature rather than a shape. The :py:`StreamConsumer` definition above should normally be written as:

.. testcode::

    class StreamConsumerUsingIn(wiring.Component):
        sink: In(SimpleStreamSignature(8))

        def elaborate(self, platform): ...

The data flow directions of the ports are identical between the two definitions:

.. doctest::

    >>> consumer.sink.signature.members == StreamConsumerUsingIn().sink.signature.members
    True

If signatures are nested within each other multiple levels deep, the final port direction is determined by how many nested :py:`In(...)` members there are. For each :py:`In(...)` signature wrapping a port, the data flow direction of the port is flipped once:

.. doctest::

    >>> sig = wiring.Signature({"port": Out(1)})
    >>> sig.members["port"]
    Out(1)
    >>> in1 = wiring.Signature({"sig": In(sig)})
    >>> in1.members["sig"].signature.members["port"]
    In(1)
    >>> in2 = wiring.Signature({"sig": In(in1)})
    >>> in2.members["sig"].signature.members["sig"].signature.members["port"]
    Out(1)

Going back to the stream example, the producer and the consumer now communicate with one another using the same set of ports with identical shapes and complementary directions (the auxiliary :py:`en` port being outside of the stream signature), and can be *connected* using the :func:`connect` function:

.. testcode::

    wiring.connect(m, producer.source, consumer.sink)

This function examines the signatures of the two provided interface objects, ensuring that they are exactly complementary, and then adds combinational :py:`.eq()` statements to the module for each of the port pairs to form the connection. Aside from the *connectability* check, the single line above is equivalent to:

.. testcode::

    m.d.comb += [
        consumer.sink.data.eq(producer.source.data),
        consumer.sink.valid.eq(producer.source.valid),
        producer.source.ready.eq(consumer.sink.ready),
    ]

Even on the simple example of a stream signature it is clear how using the :func:`connect` function results in more concise, readable, and robust code. The difference is proportionally more pronounced with more complex signatures. When a signature is being refactored, no changes to the code that uses :func:`connect` is required.

This explanation concludes the essential knowledge necessary for using this module and writing idiomatic Amaranth code.


.. _wiring-forwarding:

Forwarding interior interfaces
++++++++++++++++++++++++++++++

Consider a case where a component includes another component as a part of its implementation, and where it is necessary to *forward* the ports of the inner component, that is, expose them within the outer component's signature. To use the :py:`SimpleStreamSignature` definition above in an example:

.. testcode::

    class DataProcessorImplementation(wiring.Component):
        source: Out(SimpleStreamSignature(8))

        def elaborate(self, platform): ...


    class DataProcessorWrapper(wiring.Component):
        source: Out(SimpleStreamSignature(8))

        def elaborate(self, platform):
            m = Module()
            m.submodules.impl = impl = DataProcessorImplementation()
            m.d.comb += [
                self.source.data.eq(impl.source.data),
                self.source.valid.eq(impl.source.valid),
                impl.source.ready.eq(self.source.ready),
            ]
            return m

Because forwarding the ports requires assigning an output to an output and an input to an input, the :func:`connect` function, which connects outputs to inputs and vice versa, cannot be used---at least not directly. The :func:`connect` function is designed to cover the usual case of connecting the interfaces of modules *from outside* those modules. In order to connect an interface *from inside* a module, it is necessary to flip that interface first using the :func:`flipped` function. The :py:`DataProcessorWrapper` should instead be implemented as:

.. testcode::

    class DataProcessorWrapper(wiring.Component):
        source: Out(SimpleStreamSignature(8))

        def elaborate(self, platform):
            m = Module()
            m.submodules.impl = impl = DataProcessorImplementation()
            wiring.connect(m, wiring.flipped(self.source), impl.source)
            return m

In some cases, *both* of the two interfaces provided to :func:`connect` must be flipped. For example, the correct way to implement a component that forwards an input interface to an output interface with no processing is:

.. testcode::

    class DataForwarder(wiring.Component):
        sink: In(SimpleStreamSignature(8))
        source: Out(SimpleStreamSignature(8))

        def elaborate(self, platform):
            m = Module()
            wiring.connect(m, wiring.flipped(self.sink), wiring.flipped(self.source))
            return m

.. warning::

    It is important to wrap an interface with the :func:`flipped` function whenever it is being connected from inside the module. If the :py:`elaborate` function above had made a connection using :py:`wiring.connect(m, self.sink, self.source)`, it would not work correctly. No diagnostic is emitted in this case.


.. _wiring-constant-inputs:

Constant inputs
+++++++++++++++

Sometimes, a component must conform to a particular signature, but some of the input ports required by the signature must have a fixed value at all times. This module addresses this case by allowing both :class:`Signal` and :class:`Const` objects to be used to implement port members:

.. testcode::

    class ProducerRequiringReady(wiring.Component):
        source: Out(SimpleStreamSignature(8))

        def __init__(self):
            super().__init__()
            self.source.ready = Const(1)

        def elaborate(self, platform): ...


    class ConsumerAlwaysReady(wiring.Component):
        sink: In(SimpleStreamSignature(8))

        def __init__(self):
            super().__init__()
            self.sink.ready = Const(1)

        def elaborate(self, platform): ...


    class ConsumerPossiblyUnready(wiring.Component):
        sink: In(SimpleStreamSignature(8))

        def elaborate(self, platform): ...

.. doctest::

    >>> SimpleStreamSignature(8).is_compliant(ProducerRequiringReady().source)
    True
    >>> SimpleStreamSignature(8).flip().is_compliant(ConsumerAlwaysReady().sink)
    True

However, the :func:`connect` function considers a constant input to be connectable only to a constant output with the same value:

.. doctest::

    >>> wiring.connect(m, ProducerRequiringReady().source, ConsumerAlwaysReady().sink)
    >>> wiring.connect(m, ProducerRequiringReady().source, ConsumerPossiblyUnready().sink)
    Traceback (most recent call last):
      ...
    amaranth.lib.wiring.ConnectionError: Cannot connect to the input member 'arg0.ready' that has a constant value 1

This feature reduces the proliferation of similar but subtly incompatible interfaces that are semantically similar, only differing in the presence or absence of optional control or status signals.


.. _wiring-adapting-interfaces:

Adapting interfaces
+++++++++++++++++++

Sometimes, a design requires an interface with a particular signature to be used, but the only implementation available is either a component with an incompatible signature or an elaboratable with no signature at all. If this problem cannot be resolved by other means, *interface adaptation* can be used, where the existing signals are placed into a new interface with the appropriate signature. For example:

.. testcode::

    class LegacyAXIDataProducer(Elaboratable):
        def __init__(self):
            self.adata = Signal(8)
            self.avalid = Signal()
            self.aready = Signal()

        def elaborate(self, platform): ...


    class ModernDataConsumer(wiring.Component):
        sink: In(SimpleStreamSignature(8))


    data_producer = LegacyAXIDataProducer()
    data_consumer = ModernDataConsumer()

    adapted_data_source = SimpleStreamSignature(8).create()
    adapted_data_source.data = data_producer.adata
    adapted_data_source.valid = data_producer.avalid
    adapted_data_source.ready = data_producer.aready

    m = Module()
    wiring.connect(m, adapted_data_source, data_consumer.sink)

When creating an adapted interface, use the :meth:`create <Signature.create>` method of the signature that is required elsewhere in the design.

.. _wiring-customizing:

Customizing signatures and interfaces
+++++++++++++++++++++++++++++++++++++

The :mod:`amaranth.lib.wiring` module encourages creation of reusable building blocks. In the examples above, a custom signature, :py:`SimpleStreamSignature`, was introduced to illustrate the essential concepts necessary to use this module. While sufficient for that goal, it does not demonstrate the full capabilities provided by the module.

Consider a simple System-on-Chip memory bus with a configurable address width. In an application like that, additional properties and methods could be usefully defined both on the signature (for example, properties to retrieve the parameters of the interface) and on the created interface object (for example, methods to examine the control and status signals). These can be defined as follows:

.. testcode::

    from amaranth.lib import enum


    class TransferType(enum.Enum, shape=1):
        Write = 0
        Read  = 1


    class SimpleBusSignature(wiring.Signature):
        def __init__(self, addr_width=32):
            self._addr_width = addr_width
            super().__init__({
                "en":     Out(1),
                "rw":     Out(TransferType),
                "addr":   Out(self._addr_width),
                "r_data": In(32),
                "w_data": Out(32),
            })

        @property
        def addr_width(self):
            return self._addr_width

        def __eq__(self, other):
            return isinstance(other, SimpleBusSignature) and self.addr_width == other.addr_width

        def __repr__(self):
            return f"SimpleBusSignature({self.addr_width})"

        def create(self, *, path=None, src_loc_at=0):
            return SimpleBusInterface(self, path=path, src_loc_at=1 + src_loc_at)


    class SimpleBusInterface(wiring.PureInterface):
        def is_read_xfer(self):
            return self.en & (self.rw == TransferType.Read)

        def is_write_xfer(self):
            return self.en & (self.rw == TransferType.Write)

This example demonstrates several important principles of use:

* Defining additional properties for a custom signature. The :class:`Signature` objects are mutable in a restricted way, and can be frozen with the :meth:`freeze <Signature.freeze>` method. In almost all cases, the newly defined properties must be immutable, as shown above.
* Defining a signature-specific :py:`__eq__` method. While anonymous (created from a dictionary of members) instances of :class:`Signature` compare structurally, instances of :class:`Signature`-derived classes compare by identity unless the equality operator is overridden. In almost all cases, the equality operator should compare the parameters of the signatures rather than their structures.
* Defining a signature-specific :py:`__repr__` method. Similarly to :py:`__eq__`, the default implementation for :class:`Signature`-derived classes uses the signature's identity. In almost all cases, the representation conversion operator should return an expression that constructs an equivalent signature.
* Defining a signature-specific :py:`create` method. The default implementation used in anonymous signatures, :meth:`Signature.create`, returns a new instance of :class:`PureInterface`. Whenever the custom signature has a corresponding custom interface object class, this method should return a new instance of that class. It should not have any required arguments beyond the ones that :meth:`Signature.create` has (required parameters should be provided when creating the signature and not the interface), but may take additional optional arguments, forwarding them to the interface object constructor.

.. doctest::

    >>> sig32 = SimpleBusSignature(); sig32
    SimpleBusSignature(32)
    >>> sig24 = SimpleBusSignature(24); sig24
    SimpleBusSignature(24)
    >>> sig24.addr_width
    24
    >>> sig24 == SimpleBusSignature(24)
    True
    >>> bus = sig24.create(); bus
    <SimpleBusInterface: SimpleBusSignature(24), en=(sig bus__en), rw=EnumView(TransferType, (sig bus__rw)), addr=(sig bus__addr), r_data=(sig bus__r_data), w_data=(sig bus__w_data)>
    >>> bus.is_read_xfer()
    (& (sig bus__en) (== (sig bus__rw) (const 1'd1)))

The custom properties defined for both the signature and the interface object can be used on the flipped signature and the flipped interface in the usual way:

.. doctest::

    >>> sig32.flip().addr_width
    32
    >>> wiring.flipped(bus).is_read_xfer()
    (& (sig bus__en) (== (sig bus__rw) (const 1'd1)))

.. note::

    Unusually for Python, when the implementation of a property or method is invoked through a flipped object, the :py:`self` argument receives the flipped object that has the type :class:`FlippedSignature` or :class:`FlippedInterface`. This wrapper object proxies all attribute accesses and method calls to the original signature or interface, the only change being that of the data flow directions. See the documentation for these classes for a more detailed explanation.

.. warning::

    While the wrapper object forwards attribute accesses and method calls, it does not currently proxy special methods such as :py:`__getitem__` or :py:`__add__` that are rarely, if ever, used with interface objects. This limitation may be lifted in the future.


.. _wiring-path:

Paths
+++++

Whenever an operation in this module needs to refer to the interior of an object, it accepts or produces a *path*: a tuple of strings and integers denoting the attribute names and indexes through which an interior value can be extracted. For example, the path :py:`("buses", 0, "cyc")` into the object :py:`obj` corresponds to the Python expression :py:`obj.buses[0].cyc`.

When they appear in diagnostics, paths are printed as the corresponding Python expression.


Signatures
==========

.. autoclass:: Flow()
   :no-members:

   .. autoattribute:: Out
      :no-value:
   .. autoattribute:: In
      :no-value:
   .. automethod:: flip
   .. automethod:: __call__

.. autodata:: Out
.. autodata:: In

.. autoclass:: Member(flow, description, *, init=None)

.. autoexception:: SignatureError

.. autoclass:: SignatureMembers
.. autoclass:: FlippedSignatureMembers
   :no-members:

   .. automethod:: flip

.. autoclass:: Signature
.. autoclass:: FlippedSignature(unflipped)
   :no-members:

   .. automethod:: flip
   .. automethod:: __getattr__
   .. automethod:: __setattr__
   .. automethod:: __delattr__

.. autoclass:: SignatureMeta


Interfaces
==========

.. autoclass:: PureInterface
.. autoclass:: FlippedInterface(unflipped)

.. autofunction:: flipped


Making connections
==================

.. autoexception:: ConnectionError

.. autofunction:: connect


Components
==========

.. _JSON Schema: https://json-schema.org

.. autoclass:: Component


Component metadata
==================

.. autoexception:: InvalidMetadata

.. autoclass:: ComponentMetadata
   :no-members:
   :members: validate, origin, as_json

   .. autoattribute:: schema
      :annotation: = { "$id": "https://amaranth-lang.org/schema/amaranth/0.5/component.json", ... }
