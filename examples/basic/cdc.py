from nmigen import *
from nmigen.lib.cdc import MultiReg
from nmigen.cli import main


i, o = Signal(name="i"), Signal(name="o")
m = Module()
m.submodules += MultiReg(i, o)

if __name__ == "__main__":
    main(m, ports=[i, o])
