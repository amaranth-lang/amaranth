import unittest

from amaranth.compat import *
from amaranth.compat.genlib.fsm import FSM

from .support import SimCase


class FSMCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.ctrl   = Signal()
            self.data   = Signal()
            self.status = Signal(8)

            self.submodules.dut = FSM()
            self.dut.act("IDLE",
                If(self.ctrl,
                    NextState("START")
                )
            )
            self.dut.act("START",
                If(self.data,
                    NextState("SET-STATUS-LOW")
                ).Else(
                    NextState("SET-STATUS")
                )
            )
            self.dut.act("SET-STATUS",
                NextValue(self.status, 0xaa),
                NextState("IDLE")
            )
            self.dut.act("SET-STATUS-LOW",
                NextValue(self.status[:4], 0xb),
                NextState("IDLE")
            )

    def assertState(self, fsm, state):
        self.assertEqual(fsm.decoding[(yield fsm.state)], state)

    def test_next_state(self):
        def gen():
            yield from self.assertState(self.tb.dut, "IDLE")
            yield
            yield from self.assertState(self.tb.dut, "IDLE")
            yield self.tb.ctrl.eq(1)
            yield
            yield from self.assertState(self.tb.dut, "IDLE")
            yield self.tb.ctrl.eq(0)
            yield
            yield from self.assertState(self.tb.dut, "START")
            yield
            yield from self.assertState(self.tb.dut, "SET-STATUS")
            yield self.tb.ctrl.eq(1)
            yield
            yield from self.assertState(self.tb.dut, "IDLE")
            yield self.tb.ctrl.eq(0)
            yield self.tb.data.eq(1)
            yield
            yield from self.assertState(self.tb.dut, "START")
            yield self.tb.data.eq(0)
            yield
            yield from self.assertState(self.tb.dut, "SET-STATUS-LOW")
        self.run_with(gen())

    def test_next_value(self):
        def gen():
            self.assertEqual((yield self.tb.status), 0x00)
            yield self.tb.ctrl.eq(1)
            yield
            yield self.tb.ctrl.eq(0)
            yield
            yield
            yield from self.assertState(self.tb.dut, "SET-STATUS")
            yield self.tb.ctrl.eq(1)
            yield
            self.assertEqual((yield self.tb.status), 0xaa)
            yield self.tb.ctrl.eq(0)
            yield self.tb.data.eq(1)
            yield
            yield self.tb.data.eq(0)
            yield
            yield from self.assertState(self.tb.dut, "SET-STATUS-LOW")
            yield
            self.assertEqual((yield self.tb.status), 0xab)
        self.run_with(gen())
