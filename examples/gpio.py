from types import SimpleNamespace
from nmigen import *
from nmigen.cli import main


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


if __name__ == "__main__":
    # TODO: use Record
    bus = SimpleNamespace(
        adr  =Signal(name="adr", max=8),
        dat_r=Signal(name="dat_r"),
        dat_w=Signal(name="dat_w"),
        we   =Signal(name="we"),
    )
    pins = Signal(8)
    gpio = GPIO(Array(pins), bus)
    main(gpio, ports=[pins, bus.adr, bus.dat_r, bus.dat_w, bus.we])
