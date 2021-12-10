from amaranth import *
from amaranth.lib.cdc import FFSynchronizer
from amaranth.cli import main


i, o = Signal(name="i"), Signal(name="o")
m = Module()
m.submodules += FFSynchronizer(i, o)

if __name__ == "__main__":
    main(m, ports=[i, o])
