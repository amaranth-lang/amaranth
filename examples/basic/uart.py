from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class UART(wiring.Component):
    """
    Parameters
    ----------
    divisor : int
        Set to ``round(clk-rate / baud-rate)``.
        E.g. ``12e6 / 115200`` = ``104``.
    """
    def __init__(self, divisor, data_bits=8):
        assert divisor >= 4

        self.data_bits = data_bits
        self.divisor   = divisor

        super().__init__({
            "tx_o": Out(1),
            "rx_i": In(1),

            "tx_data": In(data_bits),
            "tx_rdy": In(1),
            "tx_ack": Out(1),

            "rx_data": Out(data_bits),
            "rx_err": Out(1),
            "rx_ovf": Out(1),
            "rx_rdy": Out(1),
            "rx_ack": In(1),
        })

    def elaborate(self, platform):
        m = Module()

        tx_phase = Signal(range(self.divisor))
        tx_shreg = Signal(1 + self.data_bits + 1, init=-1)
        tx_count = Signal(range(len(tx_shreg) + 1))

        m.d.comb += self.tx_o.eq(tx_shreg[0])
        with m.If(tx_count == 0):
            m.d.comb += self.tx_ack.eq(1)
            with m.If(self.tx_rdy):
                m.d.sync += [
                    tx_shreg.eq(Cat(C(0, 1), self.tx_data, C(1, 1))),
                    tx_count.eq(len(tx_shreg)),
                    tx_phase.eq(self.divisor - 1),
                ]
        with m.Else():
            with m.If(tx_phase != 0):
                m.d.sync += tx_phase.eq(tx_phase - 1)
            with m.Else():
                m.d.sync += [
                    tx_shreg.eq(Cat(tx_shreg[1:], C(1, 1))),
                    tx_count.eq(tx_count - 1),
                    tx_phase.eq(self.divisor - 1),
                ]

        rx_phase = Signal(range(self.divisor))
        rx_shreg = Signal(1 + self.data_bits + 1, init=-1)
        rx_count = Signal(range(len(rx_shreg) + 1))

        m.d.comb += self.rx_data.eq(rx_shreg[1:-1])
        with m.If(rx_count == 0):
            m.d.comb += self.rx_err.eq(~(~rx_shreg[0] & rx_shreg[-1]))
            with m.If(~self.rx_i):
                with m.If(self.rx_ack | ~self.rx_rdy):
                    m.d.sync += [
                        self.rx_rdy.eq(0),
                        self.rx_ovf.eq(0),
                        rx_count.eq(len(rx_shreg)),
                        rx_phase.eq(self.divisor // 2),
                    ]
                with m.Else():
                    m.d.sync += self.rx_ovf.eq(1)
            with m.If(self.rx_ack):
                m.d.sync += self.rx_rdy.eq(0)
        with m.Else():
            with m.If(rx_phase != 0):
                m.d.sync += rx_phase.eq(rx_phase - 1)
            with m.Else():
                m.d.sync += [
                    rx_shreg.eq(Cat(rx_shreg[1:], self.rx_i)),
                    rx_count.eq(rx_count - 1),
                    rx_phase.eq(self.divisor - 1),
                ]
                with m.If(rx_count == 1):
                    m.d.sync += self.rx_rdy.eq(1)

        return m


if __name__ == "__main__":
    uart = UART(divisor=5)

    import argparse

    parser = argparse.ArgumentParser()
    p_action = parser.add_subparsers(dest="action")
    p_action.add_parser("simulate")
    p_action.add_parser("generate")

    args = parser.parse_args()
    if args.action == "simulate":
        from amaranth.sim import Simulator, Passive, Period

        sim = Simulator(uart)
        sim.add_clock(Period(MHz=1))

        async def testbench_loopback(ctx):
            async for val in ctx.changed(uart.tx_o):
                ctx.set(uart.rx_i, val)

        sim.add_testbench(testbench_loopback, background=True)

        async def testbench_transmit(ctx):
            assert ctx.get(uart.tx_ack)
            assert not ctx.get(uart.rx_rdy)

            ctx.set(uart.tx_data, 0x5A)
            ctx.set(uart.tx_rdy, 1)
            await ctx.tick()
            ctx.set(uart.tx_rdy, 0)
            await ctx.tick()
            assert not ctx.get(uart.tx_ack)

            await ctx.tick().repeat(uart.divisor * 12)

            assert ctx.get(uart.tx_ack)
            assert ctx.get(uart.rx_rdy)
            assert not ctx.get(uart.rx_err)
            assert ctx.get(uart.rx_data) == 0x5A

            ctx.set(uart.rx_ack, 1)
            await ctx.tick()
            ctx.set(uart.rx_ack, 0)
            await ctx.tick()
            assert not ctx.get(uart.rx_rdy)

        sim.add_testbench(testbench_transmit)

        with sim.write_vcd("uart.vcd", "uart.gtkw"):
            sim.run()

    if args.action == "generate":
        from amaranth.back import verilog

        print(verilog.convert(uart))
