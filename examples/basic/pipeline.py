from amaranth import *
from amaranth.cli import main


class MulAdd(Elaboratable):
    def __init__(self, width):
        self.a = Signal(width)
        self.b = Signal(width)
        self.c = Signal(width)
        self.stb = Signal()
        
        self.o = Signal(width * 2 + 1)
        self.o_stb = Signal()
        self.width = width

    def elaborate(self, platform):
        m = Module()

        with m.Pipeline(self.stb) as pln:
            with m.Stage():
                pln.mul = self.a * self.b
            with m.Stage("ADD_ONE"):
                pln.added_one = pln.mul + 1
            with m.Stage("ADD"):
                m.d.sync += self.o.eq(pln.mul + self.c)
            
            m.d.comb += self.o_stb.eq(pln.o_stb)

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator

    dut = MulAdd(width=16)

    def bench():
        yield dut.a.eq(10)
        yield dut.b.eq(2)
        yield dut.c.eq(5)
        yield dut.stb.eq(1)
        yield
        yield dut.stb.eq(0)

        yield

        yield dut.a.eq(11)
        yield dut.b.eq(2)
        yield dut.c.eq(5)
        yield dut.stb.eq(1)
        yield
        yield dut.stb.eq(0)

        for _ in range(4):
            yield

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("pipeline.vcd"):
        sim.run()

    # main(muladd, ports=[muladd.a, muladd.b, muladd.c, muladd.stb, muladd.o, muladd.o_stb])
