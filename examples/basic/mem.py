from amaranth import *
from amaranth.cli import main


class RegisterFile(Elaboratable):
    def __init__(self):
        self.adr   = Signal(4)
        self.dat_r = Signal(8)
        self.dat_w = Signal(8)
        self.we    = Signal()
        self.mem   = Memory(width=8, depth=16, init=[0xaa, 0x55])

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port()
        m.submodules.wrport = wrport = self.mem.write_port()
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
    main(rf, ports=[rf.adr, rf.dat_r, rf.dat_w, rf.we])
