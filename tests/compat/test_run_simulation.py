import unittest

from amaranth import Signal, Module, Elaboratable

from .support import SimCase


class RunSimulation(SimCase, unittest.TestCase):
    """ test for https://github.com/amaranth-lang/amaranth/issues/344 """

    class TestBench(Elaboratable):
        def __init__(self):
            self.a = Signal()

        def elaborate(self, platform):
            m = Module()
            m.d.sync += self.a.eq(~self.a)
            return m

    def test_run_simulation(self):
        def gen():
            yield
            for i in range(10):
                yield
                a = (yield self.tb.a)
                self.assertEqual(a, i % 2)

        self.run_with(gen())
