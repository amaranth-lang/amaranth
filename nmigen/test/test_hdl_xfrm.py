from ..hdl.ast import *
from ..hdl.cd import *
from ..hdl.ir import *
from ..hdl.xfrm import *
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
        f.add_driver(self.s1, None)
        f.add_driver(self.s2, None)
        f.add_driver(self.s3, "sync")

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
            None: SignalSet((self.s1, self.s2)),
            "pix": SignalSet((self.s3,)),
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


class DomainLowererTestCase(FHDLTestCase):
    def setUp(self):
        self.s = Signal()

    def test_lower_clk(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_statements(
            self.s.eq(ClockSignal("sync"))
        )

        f = DomainLowerer({"sync": sync})(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s) (sig clk))
        )
        """)

    def test_lower_rst(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_statements(
            self.s.eq(ResetSignal("sync"))
        )

        f = DomainLowerer({"sync": sync})(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s) (sig rst))
        )
        """)

    def test_lower_rst_reset_less(self):
        sync = ClockDomain(reset_less=True)
        f = Fragment()
        f.add_statements(
            self.s.eq(ResetSignal("sync", allow_reset_less=True))
        )

        f = DomainLowerer({"sync": sync})(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig s) (const 1'd0))
        )
        """)

    def test_lower_drivers(self):
        pix = ClockDomain()
        f = Fragment()
        f.add_driver(ClockSignal("pix"), None)
        f.add_driver(ResetSignal("pix"), "sync")

        f = DomainLowerer({"pix": pix})(f)
        self.assertEqual(f.drivers, {
            None: SignalSet((pix.clk,)),
            "sync": SignalSet((pix.rst,))
        })

    def test_lower_wrong_domain(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_statements(
            self.s.eq(ClockSignal("xxx"))
        )

        with self.assertRaises(DomainError,
                msg="Signal (clk xxx) refers to nonexistent domain 'xxx'"):
            DomainLowerer({"sync": sync})(f)

    def test_lower_wrong_reset_less_domain(self):
        sync = ClockDomain(reset_less=True)
        f = Fragment()
        f.add_statements(
            self.s.eq(ResetSignal("sync"))
        )

        with self.assertRaises(DomainError,
                msg="Signal (rst sync) refers to reset of reset-less domain 'sync'"):
            DomainLowerer({"sync": sync})(f)


class SampleLowererTestCase(FHDLTestCase):
    def setUp(self):
        self.i = Signal()
        self.o1 = Signal()
        self.o2 = Signal()
        self.o3 = Signal()

    def test_lower_signal(self):
        f = Fragment()
        f.add_statements(
            self.o1.eq(Sample(self.i, 2, "sync")),
            self.o2.eq(Sample(self.i, 1, "sync")),
            self.o3.eq(Sample(self.i, 1, "pix")),
        )

        f = SampleLowerer()(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig o1) (sig $sample$s$i$sync$2))
            (eq (sig o2) (sig $sample$s$i$sync$1))
            (eq (sig o3) (sig $sample$s$i$pix$1))
            (eq (sig $sample$s$i$sync$1) (sig i))
            (eq (sig $sample$s$i$sync$2) (sig $sample$s$i$sync$1))
            (eq (sig $sample$s$i$pix$1) (sig i))
        )
        """)
        self.assertEqual(len(f.drivers["sync"]), 2)
        self.assertEqual(len(f.drivers["pix"]), 1)

    def test_lower_const(self):
        f = Fragment()
        f.add_statements(
            self.o1.eq(Sample(1, 2, "sync")),
        )

        f = SampleLowerer()(f)
        self.assertRepr(f.statements, """
        (
            (eq (sig o1) (sig $sample$c$1$sync$2))
            (eq (sig $sample$c$1$sync$1) (const 1'd1))
            (eq (sig $sample$c$1$sync$2) (sig $sample$c$1$sync$1))
        )
        """)
        self.assertEqual(len(f.drivers["sync"]), 2)


class SwitchCleanerTestCase(FHDLTestCase):
    def test_clean(self):
        a = Signal()
        b = Signal()
        c = Signal()
        stmts = [
            Switch(a, {
                1: a.eq(0),
                0: [
                    b.eq(1),
                    Switch(b, {1: [
                        Switch(a|b, {})
                    ]})
                ]
            })
        ]

        self.assertRepr(SwitchCleaner()(stmts), """
        (
            (switch (sig a)
                (case 1
                    (eq (sig a) (const 1'd0)))
                (case 0
                    (eq (sig b) (const 1'd1)))
            )
        )
        """)


class LHSGroupAnalyzerTestCase(FHDLTestCase):
    def test_no_group_unrelated(self):
        a = Signal()
        b = Signal()
        stmts = [
            a.eq(0),
            b.eq(0),
        ]

        groups = LHSGroupAnalyzer()(stmts)
        self.assertEqual(list(groups.values()), [
            SignalSet((a,)),
            SignalSet((b,)),
        ])

    def test_group_related(self):
        a = Signal()
        b = Signal()
        stmts = [
            a.eq(0),
            Cat(a, b).eq(0),
        ]

        groups = LHSGroupAnalyzer()(stmts)
        self.assertEqual(list(groups.values()), [
            SignalSet((a, b)),
        ])

    def test_no_loops(self):
        a = Signal()
        b = Signal()
        stmts = [
            a.eq(0),
            Cat(a, b).eq(0),
            Cat(a, b).eq(0),
        ]

        groups = LHSGroupAnalyzer()(stmts)
        self.assertEqual(list(groups.values()), [
            SignalSet((a, b)),
        ])

    def test_switch(self):
        a = Signal()
        b = Signal()
        stmts = [
            a.eq(0),
            Switch(a, {
                1: b.eq(0),
            })
        ]

        groups = LHSGroupAnalyzer()(stmts)
        self.assertEqual(list(groups.values()), [
            SignalSet((a,)),
            SignalSet((b,)),
        ])


class LHSGroupFilterTestCase(FHDLTestCase):
    def test_filter(self):
        a = Signal()
        b = Signal()
        c = Signal()
        stmts = [
            Switch(a, {
                1: a.eq(0),
                0: [
                    b.eq(1),
                    Switch(b, {1: []})
                ]
            })
        ]

        self.assertRepr(LHSGroupFilter(SignalSet((a,)))(stmts), """
        (
            (switch (sig a)
                (case 1
                    (eq (sig a) (const 1'd0)))
                (case 0 )
            )
        )
        """)


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
        f.add_driver(self.s1, "sync")

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
        f.add_driver(self.s1, "sync")
        f.add_driver(self.s2, "pix")

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
        f.add_driver(self.s2, "sync")

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
        f.add_driver(self.s3, "sync")

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
        f.add_driver(self.s1, "sync")

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
        f.add_driver(self.s1, "sync")
        f.add_driver(self.s2, "pix")

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
        f1.add_driver(self.s1, "sync")

        f2 = Fragment()
        f2.add_statements(
            self.s2.eq(1)
        )
        f2.add_driver(self.s2, "sync")
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
