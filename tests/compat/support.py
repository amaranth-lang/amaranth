from amaranth.compat import *
from amaranth.compat.fhdl import verilog
from amaranth._utils import _ignore_deprecated


class SimCase:
    def setUp(self, *args, **kwargs):
        with _ignore_deprecated():
            self.tb = self.TestBench(*args, **kwargs)

    def test_to_verilog(self):
        verilog.convert(self.tb)

    def run_with(self, generator):
        with _ignore_deprecated():
            run_simulation(self.tb, generator)
