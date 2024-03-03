# amaranth: UnusedElaboratable=no

from amaranth.hdl._ast import *
from amaranth.hdl._cd import *
from amaranth.hdl._dsl import *
from amaranth.hdl._ir import *
from amaranth.hdl._xfrm import *
from amaranth.hdl._mem import *
from amaranth.hdl._mem import MemoryInstance

from .utils import *
from amaranth._utils import _ignore_deprecated


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
            "comb",
            self.s1.eq(ClockSignal()),
            ResetSignal().eq(self.s2),
            self.s4.eq(ClockSignal("other")),
            self.s5.eq(ResetSignal("other")),
        )
        f.add_statements(
            "sync",
            self.s3.eq(0),
        )
        f.add_driver(self.s1, "comb")
        f.add_driver(self.s2, "comb")
        f.add_driver(self.s3, "sync")

        f = DomainRenamer("pix")(f)
        self.assertRepr(f.statements["comb"], """
        (
            (eq (sig s1) (clk pix))
            (eq (rst pix) (sig s2))
            (eq (sig s4) (clk other))
            (eq (sig s5) (rst other))
        )
        """)
        self.assertRepr(f.statements["pix"], """
        (
            (eq (sig s3) (const 1'd0))
        )
        """)
        self.assertFalse("sync" in f.statements)
        self.assertEqual(f.drivers, {
            "comb": SignalSet((self.s1, self.s2)),
            "pix": SignalSet((self.s3,)),
        })

    def test_rename_multi(self):
        f = Fragment()
        f.add_statements(
            "comb",
            self.s1.eq(ClockSignal()),
            self.s2.eq(ResetSignal("other")),
        )

        f = DomainRenamer({"sync": "pix", "other": "pix2"})(f)
        self.assertRepr(f.statements["comb"], """
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

    def test_rename_cd_preserves_allow_reset_less(self):
        cd_pix  = ClockDomain(reset_less=True)

        f = Fragment()
        f.add_domains(cd_pix)
        f.add_statements(
            "comb",
            self.s1.eq(ResetSignal(allow_reset_less=True)),
        )

        f = DomainRenamer("pix")(f)
        f = DomainLowerer()(f)
        self.assertRepr(f.statements["comb"], """
        (
            (eq (sig s1) (const 1'd0))
        )
        """)


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

    def test_rename_mem_ports(self):
        m = Module()
        with _ignore_deprecated():
            mem = Memory(depth=4, width=16)
        m.submodules.mem = mem
        mem.read_port(domain="a")
        mem.read_port(domain="b")
        mem.write_port(domain="c")

        f = Fragment.get(m, None)
        f = DomainRenamer({"a": "d", "c": "e"})(f)
        mem = f.subfragments[0][0]
        self.assertIsInstance(mem, MemoryInstance)
        self.assertEqual(mem._read_ports[0]._domain, "d")
        self.assertEqual(mem._read_ports[1]._domain, "b")
        self.assertEqual(mem._write_ports[0]._domain, "e")

    def test_rename_wrong_to_comb(self):
        with self.assertRaisesRegex(ValueError,
                r"^Domain 'sync' may not be renamed to 'comb'$"):
            DomainRenamer("comb")

    def test_rename_wrong_from_comb(self):
        with self.assertRaisesRegex(ValueError,
                r"^Domain 'comb' may not be renamed$"):
            DomainRenamer({"comb": "sync"})


class DomainLowererTestCase(FHDLTestCase):
    def setUp(self):
        self.s = Signal()

    def test_lower_clk(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_domains(sync)
        f.add_statements(
            "comb",
            self.s.eq(ClockSignal("sync"))
        )

        f = DomainLowerer()(f)
        self.assertRepr(f.statements["comb"], """
        (
            (eq (sig s) (sig clk))
        )
        """)

    def test_lower_rst(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_domains(sync)
        f.add_statements(
            "comb",
            self.s.eq(ResetSignal("sync"))
        )

        f = DomainLowerer()(f)
        self.assertRepr(f.statements["comb"], """
        (
            (eq (sig s) (sig rst))
        )
        """)

    def test_lower_rst_reset_less(self):
        sync = ClockDomain(reset_less=True)
        f = Fragment()
        f.add_domains(sync)
        f.add_statements(
            "comb",
            self.s.eq(ResetSignal("sync", allow_reset_less=True))
        )

        f = DomainLowerer()(f)
        self.assertRepr(f.statements["comb"], """
        (
            (eq (sig s) (const 1'd0))
        )
        """)

    def test_lower_drivers(self):
        sync = ClockDomain()
        pix = ClockDomain()
        f = Fragment()
        f.add_domains(sync, pix)
        f.add_driver(ClockSignal("pix"), "comb")
        f.add_driver(ResetSignal("pix"), "sync")

        f = DomainLowerer()(f)
        self.assertEqual(f.drivers, {
            "comb": SignalSet((pix.clk,)),
            "sync": SignalSet((pix.rst,))
        })

    def test_lower_wrong_domain(self):
        f = Fragment()
        f.add_statements(
            "comb",
            self.s.eq(ClockSignal("xxx"))
        )

        with self.assertRaisesRegex(DomainError,
                r"^Signal \(clk xxx\) refers to nonexistent domain 'xxx'$"):
            DomainLowerer()(f)

    def test_lower_wrong_reset_less_domain(self):
        sync = ClockDomain(reset_less=True)
        f = Fragment()
        f.add_domains(sync)
        f.add_statements(
            "comb",
            self.s.eq(ResetSignal("sync"))
        )

        with self.assertRaisesRegex(DomainError,
                r"^Signal \(rst sync\) refers to reset of reset-less domain 'sync'$"):
            DomainLowerer()(f)


class ResetInserterTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal(init=1)
        self.s3 = Signal(init=1, reset_less=True)
        self.c1 = Signal()

    def test_reset_default(self):
        f = Fragment()
        f.add_statements(
            "sync",
            self.s1.eq(1)
        )
        f.add_driver(self.s1, "sync")

        f = ResetInserter(self.c1)(f)
        self.assertRepr(f.statements["sync"], """
        (
            (eq (sig s1) (const 1'd1))
            (switch (sig c1)
                (case 1 (eq (sig s1) (const 1'd0)))
            )
        )
        """)

    def test_reset_cd(self):
        f = Fragment()
        f.add_statements("sync", self.s1.eq(1))
        f.add_statements("pix", self.s2.eq(0))
        f.add_domains(ClockDomain("sync"))
        f.add_driver(self.s1, "sync")
        f.add_driver(self.s2, "pix")

        f = ResetInserter({"pix": self.c1})(f)
        self.assertRepr(f.statements["sync"], """
        (
            (eq (sig s1) (const 1'd1))
        )
        """)
        self.assertRepr(f.statements["pix"], """
        (
            (eq (sig s2) (const 1'd0))
            (switch (sig c1)
                (case 1 (eq (sig s2) (const 1'd1)))
            )
        )
        """)

    def test_reset_value(self):
        f = Fragment()
        f.add_statements("sync", self.s2.eq(0))
        f.add_driver(self.s2, "sync")

        f = ResetInserter(self.c1)(f)
        self.assertRepr(f.statements["sync"], """
        (
            (eq (sig s2) (const 1'd0))
            (switch (sig c1)
                (case 1 (eq (sig s2) (const 1'd1)))
            )
        )
        """)

    def test_reset_less(self):
        f = Fragment()
        f.add_statements("sync", self.s3.eq(0))
        f.add_driver(self.s3, "sync")

        f = ResetInserter(self.c1)(f)
        self.assertRepr(f.statements["sync"], """
        (
            (eq (sig s3) (const 1'd0))
            (switch (sig c1)
                (case 1 )
            )
        )
        """)


class EnableInserterTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.c1 = Signal()

    def test_enable_default(self):
        f = Fragment()
        f.add_statements("sync", self.s1.eq(1))
        f.add_driver(self.s1, "sync")

        f = EnableInserter(self.c1)(f)
        self.assertRepr(f.statements["sync"], """
        (
            (switch (sig c1)
                (case 1 (eq (sig s1) (const 1'd1)))
            )
        )
        """)

    def test_enable_cd(self):
        f = Fragment()
        f.add_statements("sync", self.s1.eq(1))
        f.add_statements("pix", self.s2.eq(0))
        f.add_driver(self.s1, "sync")
        f.add_driver(self.s2, "pix")

        f = EnableInserter({"pix": self.c1})(f)
        self.assertRepr(f.statements["sync"], """
        (
            (eq (sig s1) (const 1'd1))
        )
        """)
        self.assertRepr(f.statements["pix"], """
        (
            (switch (sig c1)
                (case 1 (eq (sig s2) (const 1'd0)))
            )
        )
        """)

    def test_enable_subfragment(self):
        f1 = Fragment()
        f1.add_statements("sync", self.s1.eq(1))
        f1.add_driver(self.s1, "sync")

        f2 = Fragment()
        f2.add_statements("sync", self.s2.eq(1))
        f2.add_driver(self.s2, "sync")
        f1.add_subfragment(f2)

        f1 = EnableInserter(self.c1)(f1)
        (f2, _, _), = f1.subfragments
        self.assertRepr(f1.statements["sync"], """
        (
            (switch (sig c1)
                (case 1 (eq (sig s1) (const 1'd1)))
            )
        )
        """)
        self.assertRepr(f2.statements["sync"], """
        (
            (switch (sig c1)
                (case 1 (eq (sig s2) (const 1'd1)))
            )
        )
        """)

    def test_enable_read_port(self):
        with _ignore_deprecated():
            mem = Memory(width=8, depth=4)
        mem.read_port(transparent=False)
        f = EnableInserter(self.c1)(mem).elaborate(platform=None)
        self.assertRepr(f._read_ports[0]._en, """
        (& (sig mem_r_en) (sig c1))
        """)

    def test_enable_write_port(self):
        with _ignore_deprecated():
            mem = Memory(width=8, depth=4)
        mem.write_port(granularity=2)
        f = EnableInserter(self.c1)(mem).elaborate(platform=None)
        self.assertRepr(f._write_ports[0]._en, """
        (m
            (sig c1)
            (sig mem_w_en)
            (const 4'd0)
        )
        """)


class _MockElaboratable(Elaboratable):
    def __init__(self):
        self.s1 = Signal()

    def elaborate(self, platform):
        f = Fragment()
        f.add_statements("sync", self.s1.eq(1))
        f.add_driver(self.s1, "sync")
        return f


class TransformedElaboratableTestCase(FHDLTestCase):
    def setUp(self):
        self.c1 = Signal()
        self.c2 = Signal()

    def test_getattr(self):
        e = _MockElaboratable()
        te = EnableInserter(self.c1)(e)

        self.assertIs(te.s1, e.s1)

    def test_composition(self):
        e = _MockElaboratable()
        te1 = EnableInserter(self.c1)(e)
        te2 = ResetInserter(self.c2)(te1)

        self.assertIsInstance(te1, TransformedElaboratable)
        self.assertIs(te1, te2)

        f = Fragment.get(te2, None)
        self.assertRepr(f.statements["sync"], """
        (
            (switch (sig c1)
                (case 1 (eq (sig s1) (const 1'd1)))
            )
            (switch (sig c2)
                (case 1 (eq (sig s1) (const 1'd0)))
            )
        )
        """)
