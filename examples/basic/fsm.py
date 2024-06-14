from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class UARTReceiver(wiring.Component):
    i: In(1)
    data: Out(8)
    rdy: Out(1)
    ack: In(1)
    err: Out(1)

    def __init__(self, divisor):
        super().__init__()
        self.divisor = divisor

    def elaborate(self, platform):
        m = Module()

        ctr = Signal(range(self.divisor))
        stb = Signal()
        with m.If(ctr == 0):
            m.d.sync += ctr.eq(self.divisor - 1)
            m.d.comb += stb.eq(1)
        with m.Else():
            m.d.sync += ctr.eq(ctr - 1)

        bit = Signal(3)
        with m.FSM() as fsm:
            with m.State("START"):
                with m.If(~self.i):
                    m.next = "DATA"
                    m.d.sync += [
                        ctr.eq(self.divisor // 2),
                        bit.eq(7),
                    ]
            with m.State("DATA"):
                with m.If(stb):
                    m.d.sync += [
                        bit.eq(bit - 1),
                        self.data.eq(Cat(self.i, self.data))
                    ]
                    with m.If(bit == 0):
                        m.next = "STOP"
            with m.State("STOP"):
                with m.If(stb):
                    with m.If(self.i):
                        m.next = "DONE"
                    with m.Else():
                        m.next = "ERROR"

            with m.State("DONE"):
                m.d.comb += self.rdy.eq(1)
                with m.If(self.ack):
                    m.next = "START"

            m.d.comb += self.err.eq(fsm.ongoing("ERROR"))
            with m.State("ERROR"):
                pass

        return m


if __name__ == "__main__":
    rx = UARTReceiver(20)
    main(rx)
