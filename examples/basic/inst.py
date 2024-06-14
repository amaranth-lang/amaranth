from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class System(wiring.Component):
    adr: In(16)
    dat_r: In(8)
    dat_w: Out(8)
    we: In(1)

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
    main(sys)
