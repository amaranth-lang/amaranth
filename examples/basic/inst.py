from amaranth import *
from amaranth.cli import main


class System(Elaboratable):
    def __init__(self):
        self.adr   = Signal(16)
        self.dat_r = Signal(8)
        self.dat_w = Signal(8)
        self.we    = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.cpu = Instance("CPU",
            p_RESET_ADDR=0xfff0,
            i_d_adr  =self.adr,
            i_d_dat_r=self.dat_r,
            o_d_dat_w=self.dat_w,
            i_d_we   =self.we,
        )
        return m


if __name__ == "__main__":
    sys = System()
    main(sys, ports=[sys.adr, sys.dat_r, sys.dat_w, sys.we])
