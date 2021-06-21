from nmigen import *
from nmigen.vendor.openlane import *

import os

class sky130_fd_sc_hd(OpenLANEPlatform):
    openlane_root = os.environ['OPENLANE_ROOT']
    pdk = "sky130A"
    cell_library = "sky130_fd_sc_hd"

    settings = {
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

if __name__ == "__main__":
    platform = sky130_fd_sc_hd()

    # inverter = Inverter()
    # platform.build(inverter, name="inverter", ports=inverter.get_ports())
