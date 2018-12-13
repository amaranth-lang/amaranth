import re
import unittest

from nmigen.fhdl.ast import *
from nmigen.fhdl.ir import *
from nmigen.fhdl.xfrm import *


class ResetInserterTestCase(unittest.TestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal(reset=1)
        self.s3 = Signal(reset=1, reset_less=True)
        self.c1 = Signal()

    def assertRepr(self, obj, repr_str):
        obj = Statement.wrap(obj)
        repr_str = re.sub(r"\s+",   " ",  repr_str)
        repr_str = re.sub(r"\( (?=\()", "(", repr_str)
        repr_str = re.sub(r"\) (?=\))", ")", repr_str)
        self.assertEqual(repr(obj), repr_str.strip())

    def test_reset_default(self):
        f = Fragment()
        f.add_statements(
            self.s1.eq(1)
        )
        f.drive(self.s1, "sync")

        f = ResetInserter(self.c1)(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s1) (const 1'd1))
            (switch (sig c1)
                (case 1 (eq (sig s1) (const 1'd0)))
            )
        )
        """)

    def test_reset_cd(self):
        f = Fragment()
        f.add_statements(
            self.s1.eq(1),
            self.s2.eq(0),
        )
        f.drive(self.s1, "sync")
        f.drive(self.s2, "pix")

        f = ResetInserter({"pix": self.c1})(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s1) (const 1'd1))
            (eq (sig s2) (const 0'd0))
            (switch (sig c1)
                (case 1 (eq (sig s2) (const 1'd1)))
            )
        )
        """)

    def test_reset_value(self):
        f = Fragment()
        f.add_statements(
            self.s2.eq(0)
        )
        f.drive(self.s2, "sync")

        f = ResetInserter(self.c1)(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s2) (const 0'd0))
            (switch (sig c1)
                (case 1 (eq (sig s2) (const 1'd1)))
            )
        )
        """)

    def test_reset_less(self):
        f = Fragment()
        f.add_statements(
            self.s3.eq(0)
        )
        f.drive(self.s3, "sync")

        f = ResetInserter(self.c1)(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s3) (const 0'd0))
            (switch (sig c1)
                (case 1 )
            )
        )
        """)


class CEInserterTestCase(unittest.TestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.c1 = Signal()

    def assertRepr(self, obj, repr_str):
        obj = Statement.wrap(obj)
        repr_str = re.sub(r"\s+",   " ",  repr_str)
        repr_str = re.sub(r"\( (?=\()", "(", repr_str)
        repr_str = re.sub(r"\) (?=\))", ")", repr_str)
        self.assertEqual(repr(obj), repr_str.strip())

    def test_ce_default(self):
        f = Fragment()
        f.add_statements(
            self.s1.eq(1)
        )
        f.drive(self.s1, "sync")

        f = CEInserter(self.c1)(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s1) (const 1'd1))
            (switch (sig c1)
                (case 0 (eq (sig s1) (sig s1)))
            )
        )
        """)

    def test_ce_cd(self):
        f = Fragment()
        f.add_statements(
            self.s1.eq(1),
            self.s2.eq(0),
        )
        f.drive(self.s1, "sync")
        f.drive(self.s2, "pix")

        f = CEInserter({"pix": self.c1})(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s1) (const 1'd1))
            (eq (sig s2) (const 0'd0))
            (switch (sig c1)
                (case 0 (eq (sig s2) (sig s2)))
            )
        )
        """)

    def test_ce_subfragment(self):
        f1 = Fragment()
        f1.add_statements(
            self.s1.eq(1)
        )
        f1.drive(self.s1, "sync")

        f2 = Fragment()
        f2.add_statements(
            self.s2.eq(1)
        )
        f2.drive(self.s2, "sync")
        f1.add_subfragment(f2)

        f1 = CEInserter(self.c1)(f1)
        (f2, _), = f1.subfragments
        self.assertRepr(f1.statements, """
        (
            (eq (sig s1) (const 1'd1))
            (switch (sig c1)
                (case 0 (eq (sig s1) (sig s1)))
            )
        )
        """)
        self.assertRepr(f2.statements, """
        (
            (eq (sig s2) (const 1'd1))
            (switch (sig c1)
                (case 0 (eq (sig s2) (sig s2)))
            )
        )
        """)
