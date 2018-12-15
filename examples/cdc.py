from nmigen import *
from nmigen.back import rtlil, verilog


i, o = Signal(name="i"), Signal(name="o")
m = Module()
m.submodules += MultiReg(i, o)
frag = m.lower(platform=None)
# print(rtlil.convert(frag, ports=[i, o]))
print(verilog.convert(frag, ports=[i, o]))
