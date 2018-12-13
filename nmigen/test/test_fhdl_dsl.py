import re
import unittest
from contextlib import contextmanager

from nmigen.fhdl.ast import *
from nmigen.fhdl.dsl import *


class DSLTestCase(unittest.TestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.s4 = Signal()
        self.c1 = Signal()
        self.c2 = Signal()
        self.c3 = Signal()
        self.w1 = Signal(4)

    @contextmanager
    def assertRaises(self, exception, msg=None):
        with super().assertRaises(exception) as cm:
            yield
        if msg:
            # WTF? unittest.assertRaises is completely broken.
            self.assertEqual(str(cm.exception), msg)

    def assertRepr(self, obj, repr_str):
        repr_str = re.sub(r"\s+",   " ",  repr_str)
        repr_str = re.sub(r"\( (?=\()", "(", repr_str)
        repr_str = re.sub(r"\) (?=\))", ")", repr_str)
        self.assertEqual(repr(obj), repr_str.strip())

    def test_d_comb(self):
        m = Module()
        m.d.comb += self.c1.eq(1)
        m._flush()
        self.assertEqual(m._driving[self.c1], None)
        self.assertRepr(m._statements, """(
            (eq (sig c1) (const 1'd1))
        )""")

    def test_d_sync(self):
        m = Module()
        m.d.sync += self.c1.eq(1)
        m._flush()
        self.assertEqual(m._driving[self.c1], "sync")
        self.assertRepr(m._statements, """(
            (eq (sig c1) (const 1'd1))
        )""")

    def test_d_pix(self):
        m = Module()
        m.d.pix += self.c1.eq(1)
        m._flush()
        self.assertEqual(m._driving[self.c1], "pix")
        self.assertRepr(m._statements, """(
            (eq (sig c1) (const 1'd1))
        )""")

    def test_d_index(self):
        m = Module()
        m.d["pix"] += self.c1.eq(1)
        m._flush()
        self.assertEqual(m._driving[self.c1], "pix")
        self.assertRepr(m._statements, """(
            (eq (sig c1) (const 1'd1))
        )""")

    def test_d_no_conflict(self):
        m = Module()
        m.d.comb += self.w1[0].eq(1)
        m.d.comb += self.w1[1].eq(1)

    def test_d_conflict(self):
        m = Module()
        with self.assertRaises(SyntaxError,
                msg="Driver-driver conflict: trying to drive (sig c1) from d.sync, but it "
                    "is already driven from d.comb"):
            m.d.comb += self.c1.eq(1)
            m.d.sync += self.c1.eq(1)

    def test_d_wrong(self):
        m = Module()
        with self.assertRaises(AttributeError,
                msg="Cannot assign 'd.pix' attribute; did you mean 'd.pix +='?"):
            m.d.pix = None

    def test_d_asgn_wrong(self):
        m = Module()
        with self.assertRaises(SyntaxError,
                msg="Only assignments may be appended to d.sync"):
            m.d.sync += Switch(self.s1, {})

    def test_comb_wrong(self):
        m = Module()
        with self.assertRaises(AttributeError,
                msg="'Module' object has no attribute 'comb'; did you mean 'd.comb'?"):
            m.comb += self.c1.eq(1)

    def test_sync_wrong(self):
        m = Module()
        with self.assertRaises(AttributeError,
                msg="'Module' object has no attribute 'sync'; did you mean 'd.sync'?"):
            m.sync += self.c1.eq(1)

    def test_attr_wrong(self):
        m = Module()
        with self.assertRaises(AttributeError,
                msg="'Module' object has no attribute 'nonexistentattr'"):
            m.nonexistentattr

    def test_If(self):
        m = Module()
        with m.If(self.s1):
            m.d.comb += self.c1.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (cat (sig s1))
                (case 1 (eq (sig c1) (const 1'd1)))
            )
        )
        """)

    def test_If_Elif(self):
        m = Module()
        with m.If(self.s1):
            m.d.comb += self.c1.eq(1)
        with m.Elif(self.s2):
            m.d.sync += self.c2.eq(0)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (cat (sig s1) (sig s2))
                (case -1 (eq (sig c1) (const 1'd1)))
                (case 1- (eq (sig c2) (const 0'd0)))
            )
        )
        """)

    def test_If_Elif_Else(self):
        m = Module()
        with m.If(self.s1):
            m.d.comb += self.c1.eq(1)
        with m.Elif(self.s2):
            m.d.sync += self.c2.eq(0)
        with m.Else():
            m.d.comb += self.c3.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (cat (sig s1) (sig s2))
                (case -1 (eq (sig c1) (const 1'd1)))
                (case 1- (eq (sig c2) (const 0'd0)))
                (case -- (eq (sig c3) (const 1'd1)))
            )
        )
        """)

    def test_Elif_wrong(self):
        m = Module()
        with self.assertRaises(SyntaxError,
                msg="Elif without preceding If"):
            with m.Elif(self.s2):
                pass

    def test_Else_wrong(self):
        m = Module()
        with self.assertRaises(SyntaxError,
                msg="Else without preceding If/Elif"):
            with m.Else():
                pass

    def test_If_wide(self):
        m = Module()
        with m.If(self.w1):
            m.d.comb += self.c1.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (cat (b (sig w1)))
                (case 1 (eq (sig c1) (const 1'd1)))
            )
        )
        """)

    def test_auto_flush(self):
        m = Module()
        with m.If(self.w1):
            m.d.comb += self.c1.eq(1)
        m.d.comb += self.c2.eq(1)
        self.assertRepr(m._statements, """
        (
            (switch (cat (b (sig w1)))
                (case 1 (eq (sig c1) (const 1'd1)))
            )
            (eq (sig c2) (const 1'd1))
        )
        """)
