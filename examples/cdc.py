from nmigen.fhdl import *
from nmigen.back import rtlil, verilog
from nmigen.genlib.cdc import *


i, o = Signal(name="i"), Signal(name="o")
frag = MultiReg(i, o).get_fragment(platform=None)
# print(rtlil.convert(frag, ports=[i, o]))
print(verilog.convert(frag, ports=[i, o]))
