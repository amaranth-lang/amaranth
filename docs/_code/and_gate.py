from amaranth import *
from amaranth.back import verilog

class AndGate(Elaboratable):
    def __init__(self):
        # Input ports
        self.a = Signal()
        self.b = Signal()
        # Output port
        self.y = Signal()
        
    def elaborate(self, platform):
        # The 'elaborate' method builds the actual circuit
        m = Module()
        # y = a AND b
        m.d.comb += self.y.eq(self.a & self.b)
        return m

# Create the gate
gate = AndGate()

# Generate Verilog (for viewing or using with other tools)
with open("and_gate.v", "w") as f:
    f.write(verilog.convert(gate, ports=[gate.a, gate.b, gate.y]))

# How to run: pdm run python and_gate.py
# This will generate and_gate.v