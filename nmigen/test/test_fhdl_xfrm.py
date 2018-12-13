from ..fhdl.ast import *
from ..fhdl.cd import *
from ..fhdl.ir import *
from ..fhdl.xfrm import *
from .tools import *


class DomainRenamerTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.s4 = Signal()
        self.s5 = Signal()
        self.c1 = Signal()

    def test_rename_signals(self):
        f = Fragment()
        f.add_statements(
            self.s1.eq(ClockSignal()),
            ResetSignal().eq(self.s2),
            self.s3.eq(0),
            self.s4.eq(ClockSignal("other")),
            self.s5.eq(ResetSignal("other")),
        )
        f.drive(self.s1, None)
        f.drive(self.s2, None)
        f.drive(self.s3, "sync")

        f = DomainRenamer("pix")(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s1) (clk pix))
            (eq (rst pix) (sig s2))
            (eq (sig s3) (const 1'd0))
            (eq (sig s4) (clk other))
            (eq (sig s5) (rst other))
        )
        """)
        self.assertEqual(f.drivers, {
            None: ValueSet((self.s1, self.s2)),
            "pix": ValueSet((self.s3,)),
        })

    def test_rename_multi(self):
        f = Fragment()
        f.add_statements(
            self.s1.eq(ClockSignal()),
            self.s2.eq(ResetSignal("other")),
        )

        f = DomainRenamer({"sync": "pix", "other": "pix2"})(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s1) (clk pix))
            (eq (sig s2) (rst pix2))
        )
        """)

    def test_rename_cd(self):
        cd_sync = ClockDomain()
        cd_pix  = ClockDomain()

        f = Fragment()
        f.add_domains(cd_sync, cd_pix)

        f = DomainRenamer("ext")(f)
        self.assertEqual(cd_sync.name, "ext")
        self.assertEqual(f.domains, {
            "ext": cd_sync,
            "pix": cd_pix,
        })

    def test_rename_cd_subfragment(self):
        cd_sync = ClockDomain()
        cd_pix  = ClockDomain()

        f1 = Fragment()
        f1.add_domains(cd_sync, cd_pix)
        f2 = Fragment()
        f2.add_domains(cd_sync)
        f1.add_subfragment(f2)

        f1 = DomainRenamer("ext")(f1)
        self.assertEqual(cd_sync.name, "ext")
        self.assertEqual(f1.domains, {
            "ext": cd_sync,
            "pix": cd_pix,
        })


class ResetInserterTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal(reset=1)
        self.s3 = Signal(reset=1, reset_less=True)
        self.c1 = Signal()

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
        f.add_domains(ClockDomain("sync"))
        f.drive(self.s1, "sync")
        f.drive(self.s2, "pix")

        f = ResetInserter({"pix": self.c1})(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s1) (const 1'd1))
            (eq (sig s2) (const 1'd0))
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
            (eq (sig s2) (const 1'd0))
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
            (eq (sig s3) (const 1'd0))
            (switch (sig c1)
                (case 1 )
            )
        )
        """)


class CEInserterTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.c1 = Signal()

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
            (eq (sig s2) (const 1'd0))
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
