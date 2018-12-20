from nmigen import *
from nmigen.back import rtlil, verilog


class System:
    def __init__(self):
        self.adr   = Signal(16)
        self.dat_r = Signal(8)
        self.dat_w = Signal(8)
        self.we    = Signal()

    def get_fragment(self, platform):
        m = Module()
        m.submodules += Instance("CPU",
            p_RESET_ADDR=0xfff0,
            i_d_adr  =self.adr,
            i_d_dat_r=self.dat_r,
            o_d_dat_w=self.dat_w,
            i_d_we   =self.we,
        )
        return m.lower(platform)


sys  = System()
frag = sys.get_fragment(platform=None)
# print(rtlil.convert(frag, ports=[sys.adr, sys.dat_r, sys.dat_w, sys.we]))
print(verilog.convert(frag, ports=[sys.adr, sys.dat_r, sys.dat_w, sys.we]))
