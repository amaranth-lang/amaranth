from nmigen import *
from nmigen.cli import main


pin = Signal()
pin_t = TSTriple()

m = Module()
m.submodules += pin_t.get_tristate(pin)

if __name__ == "__main__":
    main(m, ports=[pin, pin_t.oe, pin_t.i, pin_t.o])
