from nmigen import *
from nmigen.vendor.openlane import Sky130FDSCHDPlatform

import os

class OpenlaneExamplePlatform(Sky130FDSCHDPlatform):
    openlane_root = os.environ['OPENLANE_ROOT']

    flow_settings = {
        "PL_TARGET_DENSITY": 0.75,
        "FP_HORIZONTAL_HALO": 6,
        "FP_VERTICAL_HALO": 6,
        "FP_CORE_UTIL": 5,
    }

    connectors  = []
    resources = []


# An example configurable width inverter for the OpenLANE ASIC flow
class Inverter(Elaboratable):
    def __init__(self, width=8):
        self.i = Signal(width)
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.o.eq(~self.i)

        return m

    def get_ports(self):
        return [self.i, self.o]

# A small blinky showing the synchronous capabilities
class Blinky(Elaboratable):
    def __init__(self):
        self.o = Signal()

    def elaborate(self, platform):
        timer = Signal(20)

        m = Module()

        m.d.sync += timer.eq(timer + 1)
        m.d.comb += self.o.eq(timer[-1])

        return m

    def get_ports(self):
        return [self.o]

if __name__ == "__main__":
    platform = OpenlaneExamplePlatform()

    inverter = Inverter()
    platform.build(inverter, name="inverter", ports=inverter.get_ports())

    blinky = Blinky()
    platform.build(blinky, name="blinky", ports=blinky.get_ports())
