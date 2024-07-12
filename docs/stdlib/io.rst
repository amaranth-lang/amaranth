Input/output buffers
====================

.. py:module:: amaranth.lib.io

The :mod:`amaranth.lib.io` module provides a platform-independent way to instantiate platform-specific input/output buffers: combinational, synchronous, and double data rate (DDR).


Introduction
------------

The Amaranth language provides :ref:`core I/O values <lang-iovalues>` that designate connections to external devices, and :ref:`I/O buffer instances <lang-iobufferinstance>` that implement platform-independent combinational I/O buffers. This low-level mechanism is foundational to all I/O in Amaranth and must be used whenever a device-specific platform is unavailable, but is limited in its capabilities. The :mod:`amaranth.lib.io` module builds on top of it to provide *library I/O ports* that specialize and annotate I/O values, and *buffer components* that connect ports to logic.

.. note::

    Unfortunately, the terminology related to I/O has several ambiguities:

    * A "port" could refer to an *interface port* (:class:`.Signal` objects created by the :mod:`amaranth.lib.wiring` module), a *core I/O port* (:class:`amaranth.hdl.IOPort` object), or a *library I/O port* (:class:`amaranth.lib.io.PortLike` object).
    * A "I/O buffer" could refer to an *I/O buffer instance* (:class:`amaranth.hdl.IOBufferInstance`) or a *I/O buffer component* (:class:`amaranth.lib.io.Buffer`, :class:`.FFBuffer`, or :class:`.DDRBuffer` objects).

    Amaranth documentation always uses the least ambiguous form of these terms.


Examples
--------

.. testsetup::

    from amaranth import *

    class MockPlatform:
        def request(self, name, *, dir):
            from amaranth.hdl import IOPort
            from amaranth.lib import io
            if name == "led":
                return io.SingleEndedPort(IOPort(1, name=name), direction="o")
            if name == "clk24":
                return io.SingleEndedPort(IOPort(1, name=name), direction="i")
            if name == "d":
                return io.SingleEndedPort(IOPort(8, name=name), direction="io")
            if name == "re":
                return io.SingleEndedPort(IOPort(1, name=name), direction="i")
            if name == "we":
                return io.SingleEndedPort(IOPort(1, name=name), direction="i")
            if name == "dclk":
                return io.SingleEndedPort(IOPort(1, name=name), direction="o")
            if name == "dout":
                return io.SingleEndedPort(IOPort(8, name=name), direction="o")
            raise NameError

        def get_io_buffer(self, buffer):
            return Fragment()

        def build(self, top):
            from amaranth.back import rtlil
            return rtlil.convert(Fragment.get(top, self), ports=[])


All of the following examples assume that one of the built-in FPGA platforms is used.

.. testcode::

    from amaranth.sim import Simulator
    from amaranth.lib import io, wiring, stream
    from amaranth.lib.wiring import In, Out


LED output
++++++++++

In this example, a library I/O port for a LED is requested from the platform and driven to blink the LED:

.. testcode::

    class Toplevel(Elaboratable):
        def elaborate(self, platform):
            m = Module()

            delay = Signal(24)
            state = Signal()
            with m.If(delay == 0):
                m.d.sync += delay.eq(~0)
                m.d.sync += state.eq(~state)
            with m.Else():
                m.d.sync += delay.eq(delay - 1)

            m.submodules.led = led = io.Buffer("o", platform.request("led", dir="-"))
            m.d.comb += led.o.eq(state)

            return m

.. testcode::
    :hide:

    MockPlatform().build(Toplevel())


Clock input
+++++++++++

In this example, a clock domain is created and driven from an external clock source:

.. testcode::

    class Toplevel(Elaboratable):
        def elaborate(self, platform):
            m = Module()

            m.domains.sync = cd_sync = ClockDomain(local=True)

            m.submodules.clk24 = clk24 = io.Buffer("i", platform.request("clk24", dir="-"))
            m.d.comb += cd_sync.clk.eq(clk24.i)

            ...

            return m

.. testcode::
    :hide:

    MockPlatform().build(Toplevel())


Bidirectional bus
+++++++++++++++++

This example implements a peripheral for a clocked parallel bus. This peripheral can store and recall one byte of data. The data is stored with a write enable pulse, and recalled with a read enable pulse:

.. testcode::

    class Toplevel(Elaboratable):
        def elaborate(self, platform):
            m = Module()

            m.submodules.bus_d = bus_d = io.FFBuffer("io", platform.request("d", dir="-"))
            m.submodules.bus_re = bus_re = io.Buffer("i", platform.request("re", dir="-"))
            m.submodules.bus_we = bus_we = io.Buffer("i", platform.request("we", dir="-"))

            data = Signal.like(bus_d.i)
            with m.If(bus_re.i):
                m.d.comb += bus_d.oe.eq(1)
                m.d.comb += bus_d.o.eq(data)
            with m.Elif(bus_we.i):
                m.d.sync += data.eq(bus_d.i)

            return m

.. testcode::
    :hide:

    MockPlatform().build(Toplevel())

This bus requires a turn-around time of at least 1 cycle to avoid electrical contention.

Note that data appears on the bus one cycle after the read enable input is asserted, and that the write enable input stores the data present on the bus in the *previous* cycle. This is called *pipelining* and is typical for clocked buses; see :class:`.FFBuffer` for a waveform diagram. Although it increases the maximum clock frequency at which the bus can run, it also makes the bus signaling more complicated.


Clock forwarding
++++++++++++++++

In this example of a `source-synchronous interface <https://en.wikipedia.org/wiki/Source-synchronous>`__, a clock signal is generated with the same phase as the DDR data signals associated with it:

.. testcode::

    class SourceSynchronousOutput(wiring.Component):
        dout: In(16)

        def elaborate(self, platform):
            m = Module()

            m.submodules.bus_dclk = bus_dclk = \
                io.DDRBuffer("o", platform.request("dclk", dir="-"))
            m.d.comb += [
                bus_dclk.o[0].eq(1),
                bus_dclk.o[1].eq(0),
            ]

            m.submodules.bus_dout = bus_dout = \
                io.DDRBuffer("o", platform.request("dout", dir="-"))
            m.d.comb += [
                bus_dout.o[0].eq(self.dout[:8]),
                bus_dout.o[1].eq(self.dout[8:]),
            ]

            return m

.. testcode::
    :hide:

    MockPlatform().build(SourceSynchronousOutput())

This component transmits :py:`dout` on each cycle as two halves: the low 8 bits on the rising edge of the data clock, and the high 8 bits on the falling edge of the data clock. The transmission is *edge-aligned*, meaning that the data edges exactly coincide with the clock edges.


Simulation
----------

The Amaranth simulator, :mod:`amaranth.sim`, cannot simulate :ref:`core I/O values <lang-iovalues>` or :ref:`I/O buffer instances <lang-iobufferinstance>` as it only operates on unidirectionally driven two-state wires. This module provides a simulation-only library I/O port, :class:`SimulationPort`, so that components that use library I/O buffers can be tested.

A component that is designed for testing should accept the library I/O ports it will drive as constructor parameters rather than requesting them from the platform directly. Synthesizable designs will instantiate the component with a :class:`SingleEndedPort`, :class:`DifferentialPort`, or a platform-specific library I/O port, while tests will instantiate the component with a :class:`SimulationPort`. Tests are able to inject inputs into the component using :py:`sim_port.i`, capture the outputs of the component via :py:`sim_port.o`, and ensure that the component is driving the outputs at the appropriate times using :py:`sim_port.oe`.

For example, consider a simple serializer that accepts a stream of multi-bit data words and outputs them bit by bit. It can be tested as follows:

.. testcode::

    class OutputSerializer(wiring.Component):
        data: In(stream.Signature(8))

        def __init__(self, dclk_port, dout_port):
            self.dclk_port = dclk_port
            self.dout_port = dout_port

            super().__init__()

        def elaborate(self, platform):
            m = Module()

            m.submodules.dclk = dclk = io.Buffer("o", self.dclk_port)
            m.submodules.dout = dout = io.Buffer("o", self.dout_port)

            index = Signal(range(8))
            m.d.comb += dout.o.eq(self.data.payload.bit_select(index, 1))

            with m.If(self.data.valid):
                m.d.sync += dclk.o.eq(~dclk.o)
                with m.If(dclk.o):
                    m.d.sync += index.eq(index + 1)
                    with m.If(index == 7):
                        m.d.comb += self.data.ready.eq(1)

            return m

    def test_output_serializer():
        dclk_port = io.SimulationPort("o", 1)
        dout_port = io.SimulationPort("o", 1)

        dut = OutputSerializer(dclk_port, dout_port)

        async def testbench_write_data(ctx):
            ctx.set(dut.data.payload, 0xA1)
            ctx.set(dut.data.valid, 1)
            await ctx.tick().until(dut.data.ready)
            ctx.set(dut.data.valid, 0)

        async def testbench_sample_output(ctx):
            for bit in [1,0,0,0,0,1,0,1]:
                _, dout_value = await ctx.posedge(dut.dclk_port.o).sample(dut.dout_port.o)
                assert ctx.get(dut.dout_port.oe) == 1, "DUT is not driving the data output"
                assert dout_value == bit, "DUT drives the wrong value on data output"

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench_write_data)
        sim.add_testbench(testbench_sample_output)
        sim.run()

.. testcode::
    :hide:

    test_output_serializer()


Ports
-----

.. autoclass:: Direction()

.. autoclass:: PortLike
.. autoclass:: SingleEndedPort
.. autoclass:: DifferentialPort
.. autoclass:: SimulationPort


Buffers
-------

.. autoclass:: Buffer(direction, port)
.. autoclass:: FFBuffer(direction, port, *, i_domain=None, o_domain=None)
.. autoclass:: DDRBuffer(direction, port, *, i_domain=None, o_domain=None)
