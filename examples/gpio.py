from types import SimpleNamespace
from nmigen import *
from nmigen.back import rtlil, verilog, pysim


class GPIO:
    def __init__(self, pins, bus):
        self.pins = pins
        self.bus  = bus

    def get_fragment(self, platform):
        m = Module()
        m.d.comb += self.bus.dat_r.eq(self.pins[self.bus.adr])
        with m.If(self.bus.we):
            m.d.sync += self.pins[self.bus.adr].eq(self.bus.dat_w)
        return m.lower(platform)


# TODO: use Record
bus = SimpleNamespace(
    adr=Signal(max=8),
    dat_r=Signal(),
    dat_w=Signal(),
    we=Signal()
)
pins = Signal(8)
gpio = GPIO(Array(pins), bus)
frag = gpio.get_fragment(platform=None)

# print(rtlil.convert(frag, ports=[pins, bus.adr, bus.dat_r, bus.dat_w, bus.we]))
print(verilog.convert(frag, ports=[pins, bus.adr, bus.dat_r, bus.dat_w, bus.we]))
