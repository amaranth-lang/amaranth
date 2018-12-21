from nmigen import *
from nmigen.back import rtlil, verilog


class RegisterFile:
    def __init__(self):
        self.adr   = Signal(4)
        self.dat_r = Signal(8)
        self.dat_w = Signal(8)
        self.we    = Signal()
        self.mem   = Memory(width=8, depth=16, init=[0xaa, 0x55])

    def get_fragment(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port()
        m.submodules.wrport = wrport = self.mem.write_port()
        m.d.comb += [
            rdport.addr.eq(self.adr),
            self.dat_r.eq(rdport.data),
            rdport.en.eq(1),
            wrport.addr.eq(self.adr),
            wrport.data.eq(self.dat_w),
            wrport.en.eq(self.we),
        ]
        return m.lower(platform)


rf   = RegisterFile()
frag = rf.get_fragment(platform=None)
# print(rtlil.convert(frag, ports=[rf.adr, rf.dat_r, rf.dat_w, rf.we]))
print(verilog.convert(frag, ports=[rf.adr, rf.dat_r, rf.dat_w, rf.we]))
