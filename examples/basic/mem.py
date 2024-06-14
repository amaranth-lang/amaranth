from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.lib.memory import Memory
from amaranth.cli import main


class RegisterFile(wiring.Component):
    adr: In(4)
    dat_r: Out(8)
    dat_w: In(8)
    we: In(1)

    def __init__(self):
        super().__init__()
        self.mem = Memory(shape=8, depth=16, init=[0xaa, 0x55])

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self.mem
        rdport = self.mem.read_port()
        wrport = self.mem.write_port()
        m.d.comb += [
            rdport.addr.eq(self.adr),
            self.dat_r.eq(rdport.data),
            wrport.addr.eq(self.adr),
            wrport.data.eq(self.dat_w),
            wrport.en.eq(self.we),
        ]
        return m


if __name__ == "__main__":
    rf = RegisterFile()
    main(rf)
