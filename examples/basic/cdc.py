from nmigen import *
from nmigen.lib.cdc import FFSynchronizer
from nmigen.cli import main


i, o = Signal(name="i"), Signal(name="o")
m = Module()
m.submodules += FFSynchronizer(i, o)

if __name__ == "__main__":
    main(m, ports=[i, o])
