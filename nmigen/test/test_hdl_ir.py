from collections import OrderedDict

from ..hdl.ast import *
from ..hdl.cd import *
from ..hdl.ir import *
from ..hdl.mem import *
from .tools import *


class FragmentGeneratedTestCase(FHDLTestCase):
    def test_find_subfragment(self):
        f1 = Fragment()
        f2 = Fragment()
        f1.add_subfragment(f2, "f2")

        self.assertEqual(f1.find_subfragment(0), f2)
        self.assertEqual(f1.find_subfragment("f2"), f2)

    def test_find_subfragment_wrong(self):
        f1 = Fragment()
        f2 = Fragment()
        f1.add_subfragment(f2, "f2")

        with self.assertRaises(NameError,
                msg="No subfragment at index #1"):
            f1.find_subfragment(1)
        with self.assertRaises(NameError,
                msg="No subfragment with name 'fx'"):
            f1.find_subfragment("fx")

    def test_find_generated(self):
        f1 = Fragment()
        f2 = Fragment()
        f2.generated["sig"] = sig = Signal()
        f1.add_subfragment(f2, "f2")

        self.assertEqual(SignalKey(f1.find_generated("f2", "sig")),
                         SignalKey(sig))


class FragmentDriversTestCase(FHDLTestCase):
    def test_empty(self):
        f = Fragment()
        self.assertEqual(list(f.iter_comb()), [])
        self.assertEqual(list(f.iter_sync()), [])


class FragmentPortsTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.c1 = Signal()
        self.c2 = Signal()
        self.c3 = Signal()

    def test_empty(self):
        f = Fragment()
        self.assertEqual(list(f.iter_ports()), [])

        f._propagate_ports(ports=())
        self.assertEqual(f.ports, SignalDict([]))

    def test_iter_signals(self):
        f = Fragment()
        f.add_ports(self.s1, self.s2, dir="io")
        self.assertEqual(SignalSet((self.s1, self.s2)), f.iter_signals())

    def test_self_contained(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1),
            self.s1.eq(self.c1)
        )

        f._propagate_ports(ports=())
        self.assertEqual(f.ports, SignalDict([]))

    def test_infer_input(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )

        f._propagate_ports(ports=())
        self.assertEqual(f.ports, SignalDict([
            (self.s1, "i")
        ]))

    def test_request_output(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )

        f._propagate_ports(ports=(self.c1,))
        self.assertEqual(f.ports, SignalDict([
            (self.s1, "i"),
            (self.c1, "o")
        ]))

    def test_input_in_subfragment(self):
        f1 = Fragment()
        f1.add_statements(
            self.c1.eq(self.s1)
        )
        f2 = Fragment()
        f2.add_statements(
            self.s1.eq(0)
        )
        f1.add_subfragment(f2)
        f1._propagate_ports(ports=())
        self.assertEqual(f1.ports, SignalDict())
        self.assertEqual(f2.ports, SignalDict([
            (self.s1, "o"),
        ]))

    def test_input_only_in_subfragment(self):
        f1 = Fragment()
        f2 = Fragment()
        f2.add_statements(
            self.c1.eq(self.s1)
        )
        f1.add_subfragment(f2)
        f1._propagate_ports(ports=())
        self.assertEqual(f1.ports, SignalDict([
            (self.s1, "i"),
        ]))
        self.assertEqual(f2.ports, SignalDict([
            (self.s1, "i"),
        ]))

    def test_output_from_subfragment(self):
        f1 = Fragment()
        f1.add_statements(
            self.c1.eq(0)
        )
        f2 = Fragment()
        f2.add_statements(
            self.c2.eq(1)
        )
        f1.add_subfragment(f2)

        f1._propagate_ports(ports=(self.c2,))
        self.assertEqual(f1.ports, SignalDict([
            (self.c2, "o"),
        ]))
        self.assertEqual(f2.ports, SignalDict([
            (self.c2, "o"),
        ]))

    def test_input_output_sibling(self):
        f1 = Fragment()
        f2 = Fragment()
        f2.add_statements(
            self.c1.eq(self.c2)
        )
        f1.add_subfragment(f2)
        f3 = Fragment()
        f3.add_statements(
            self.c2.eq(0)
        )
        f3.add_driver(self.c2)
        f1.add_subfragment(f3)

        f1._propagate_ports(ports=())
        self.assertEqual(f1.ports, SignalDict())

    def test_output_input_sibling(self):
        f1 = Fragment()
        f2 = Fragment()
        f2.add_statements(
            self.c2.eq(0)
        )
        f2.add_driver(self.c2)
        f1.add_subfragment(f2)
        f3 = Fragment()
        f3.add_statements(
            self.c1.eq(self.c2)
        )
        f1.add_subfragment(f3)

        f1._propagate_ports(ports=())
        self.assertEqual(f1.ports, SignalDict())

    def test_input_cd(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )
        f.add_domains(sync)
        f.add_driver(self.c1, "sync")

        f._propagate_ports(ports=())
        self.assertEqual(f.ports, SignalDict([
            (self.s1,  "i"),
            (sync.clk, "i"),
            (sync.rst, "i"),
        ]))

    def test_input_cd_reset_less(self):
        sync = ClockDomain(reset_less=True)
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )
        f.add_domains(sync)
        f.add_driver(self.c1, "sync")

        f._propagate_ports(ports=())
        self.assertEqual(f.ports, SignalDict([
            (self.s1,  "i"),
            (sync.clk, "i"),
        ]))

    def test_inout(self):
        s = Signal()
        f1 = Fragment()
        f2 = Fragment()
        f2.add_ports(s, dir="io")
        f1.add_subfragment(f2)

        f1._propagate_ports(ports=())
        self.assertEqual(f1.ports, SignalDict([
            (s, "io")
        ]))


class FragmentDomainsTestCase(FHDLTestCase):
    def test_iter_signals(self):
        cd1 = ClockDomain()
        cd2 = ClockDomain(reset_less=True)
        s1 = Signal()
        s2 = Signal()

        f = Fragment()
        f.add_domains(cd1, cd2)
        f.add_driver(s1, "cd1")
        self.assertEqual(SignalSet((cd1.clk, cd1.rst, s1)), f.iter_signals())
        f.add_driver(s2, "cd2")
        self.assertEqual(SignalSet((cd1.clk, cd1.rst, cd2.clk, s1, s2)), f.iter_signals())

    def test_propagate_up(self):
        cd = ClockDomain()

        f1 = Fragment()
        f2 = Fragment()
        f1.add_subfragment(f2)
        f2.add_domains(cd)

        f1._propagate_domains_up()
        self.assertEqual(f1.domains, {"cd": cd})

    def test_domain_conflict(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        f = Fragment()
        f.add_subfragment(fa, "a")
        f.add_subfragment(fb, "b")

        f._propagate_domains_up()
        self.assertEqual(f.domains, {"a_sync": cda, "b_sync": cdb})
        (fa, _), (fb, _) = f.subfragments
        self.assertEqual(fa.domains, {"a_sync": cda})
        self.assertEqual(fb.domains, {"b_sync": cdb})

    def test_domain_conflict_anon(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        f = Fragment()
        f.add_subfragment(fa, "a")
        f.add_subfragment(fb)

        with self.assertRaises(DomainError,
                msg="Domain 'sync' is defined by subfragments 'a', <unnamed #1> of fragment "
                    "'top'; it is necessary to either rename subfragment domains explicitly, "
                    "or give names to subfragments"):
            f._propagate_domains_up()

    def test_domain_conflict_name(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        f = Fragment()
        f.add_subfragment(fa, "x")
        f.add_subfragment(fb, "x")

        with self.assertRaises(DomainError,
                msg="Domain 'sync' is defined by subfragments #0, #1 of fragment 'top', some "
                    "of which have identical names; it is necessary to either rename subfragment "
                    "domains explicitly, or give distinct names to subfragments"):
            f._propagate_domains_up()

    def test_propagate_down(self):
        cd = ClockDomain()

        f1 = Fragment()
        f2 = Fragment()
        f1.add_domains(cd)
        f1.add_subfragment(f2)

        f1._propagate_domains_down()
        self.assertEqual(f2.domains, {"cd": cd})

    def test_propagate_down_idempotent(self):
        cd = ClockDomain()

        f1 = Fragment()
        f1.add_domains(cd)
        f2 = Fragment()
        f2.add_domains(cd)
        f1.add_subfragment(f2)

        f1._propagate_domains_down()
        self.assertEqual(f1.domains, {"cd": cd})
        self.assertEqual(f2.domains, {"cd": cd})

    def test_propagate(self):
        cd = ClockDomain()

        f1 = Fragment()
        f2 = Fragment()
        f1.add_domains(cd)
        f1.add_subfragment(f2)

        f1._propagate_domains(ensure_sync_exists=False)
        self.assertEqual(f1.domains, {"cd": cd})
        self.assertEqual(f2.domains, {"cd": cd})

    def test_propagate_ensure_sync(self):
        f1 = Fragment()
        f2 = Fragment()
        f1.add_subfragment(f2)

        f1._propagate_domains(ensure_sync_exists=True)
        self.assertEqual(f1.domains.keys(), {"sync"})
        self.assertEqual(f2.domains.keys(), {"sync"})
        self.assertEqual(f1.domains["sync"], f2.domains["sync"])


class FragmentHierarchyConflictTestCase(FHDLTestCase):
    def setUp_self_sub(self):
        self.s1 = Signal()
        self.c1 = Signal()
        self.c2 = Signal()

        self.f1 = Fragment()
        self.f1.add_statements(self.c1.eq(0))
        self.f1.add_driver(self.s1)
        self.f1.add_driver(self.c1, "sync")

        self.f1a = Fragment()
        self.f1.add_subfragment(self.f1a, "f1a")

        self.f2 = Fragment()
        self.f2.add_statements(self.c2.eq(1))
        self.f2.add_driver(self.s1)
        self.f2.add_driver(self.c2, "sync")
        self.f1.add_subfragment(self.f2)

        self.f1b = Fragment()
        self.f1.add_subfragment(self.f1b, "f1b")

        self.f2a = Fragment()
        self.f2.add_subfragment(self.f2a, "f2a")

    def test_conflict_self_sub(self):
        self.setUp_self_sub()

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [
            (self.f1a, "f1a"),
            (self.f1b, "f1b"),
            (self.f2a, "f2a"),
        ])
        self.assertRepr(self.f1.statements, """
        (
            (eq (sig c1) (const 1'd0))
            (eq (sig c2) (const 1'd1))
        )
        """)
        self.assertEqual(self.f1.drivers, {
            None:   SignalSet((self.s1,)),
            "sync": SignalSet((self.c1, self.c2)),
        })

    def test_conflict_self_sub_error(self):
        self.setUp_self_sub()

        with self.assertRaises(DriverConflict,
                msg="Signal '(sig s1)' is driven from multiple fragments: top, top.<unnamed #1>"):
            self.f1._resolve_hierarchy_conflicts(mode="error")

    def test_conflict_self_sub_warning(self):
        self.setUp_self_sub()

        with self.assertWarns(DriverConflict,
                msg="Signal '(sig s1)' is driven from multiple fragments: top, top.<unnamed #1>; "
                    "hierarchy will be flattened"):
            self.f1._resolve_hierarchy_conflicts(mode="warn")

    def setUp_sub_sub(self):
        self.s1 = Signal()
        self.c1 = Signal()
        self.c2 = Signal()

        self.f1 = Fragment()

        self.f2 = Fragment()
        self.f2.add_driver(self.s1)
        self.f2.add_statements(self.c1.eq(0))
        self.f1.add_subfragment(self.f2)

        self.f3 = Fragment()
        self.f3.add_driver(self.s1)
        self.f3.add_statements(self.c2.eq(1))
        self.f1.add_subfragment(self.f3)

    def test_conflict_sub_sub(self):
        self.setUp_sub_sub()

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [])
        self.assertRepr(self.f1.statements, """
        (
            (eq (sig c1) (const 1'd0))
            (eq (sig c2) (const 1'd1))
        )
        """)

    def setUp_self_subsub(self):
        self.s1 = Signal()
        self.c1 = Signal()
        self.c2 = Signal()

        self.f1 = Fragment()
        self.f1.add_driver(self.s1)

        self.f2 = Fragment()
        self.f2.add_statements(self.c1.eq(0))
        self.f1.add_subfragment(self.f2)

        self.f3 = Fragment()
        self.f3.add_driver(self.s1)
        self.f3.add_statements(self.c2.eq(1))
        self.f2.add_subfragment(self.f3)

    def test_conflict_self_subsub(self):
        self.setUp_self_subsub()

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [])
        self.assertRepr(self.f1.statements, """
        (
            (eq (sig c1) (const 1'd0))
            (eq (sig c2) (const 1'd1))
        )
        """)

    def setUp_memory(self):
        self.m = Memory(width=8, depth=4)
        self.fr = self.m.read_port().elaborate(platform=None)
        self.fw = self.m.write_port().elaborate(platform=None)
        self.f1 = Fragment()
        self.f2 = Fragment()
        self.f2.add_subfragment(self.fr)
        self.f1.add_subfragment(self.f2)
        self.f3 = Fragment()
        self.f3.add_subfragment(self.fw)
        self.f1.add_subfragment(self.f3)

    def test_conflict_memory(self):
        self.setUp_memory()

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [
            (self.fr, None),
            (self.fw, None),
        ])

    def test_conflict_memory_error(self):
        self.setUp_memory()

        with self.assertRaises(DriverConflict,
                msg="Memory 'm' is accessed from multiple fragments: top.<unnamed #0>, "
                    "top.<unnamed #1>"):
            self.f1._resolve_hierarchy_conflicts(mode="error")

    def test_conflict_memory_warning(self):
        self.setUp_memory()

        with self.assertWarns(DriverConflict,
                msg="Memory 'm' is accessed from multiple fragments: top.<unnamed #0>, "
                    "top.<unnamed #1>; hierarchy will be flattened"):
            self.f1._resolve_hierarchy_conflicts(mode="warn")

    def test_explicit_flatten(self):
        self.f1 = Fragment()
        self.f2 = Fragment()
        self.f2.flatten = True
        self.f1.add_subfragment(self.f2)

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [])


class InstanceTestCase(FHDLTestCase):
    def setUp_cpu(self):
        self.rst = Signal()
        self.stb = Signal()
        self.pins = Signal(8)
        self.inst = Instance("cpu",
            p_RESET=0x1234,
            i_clk=ClockSignal(),
            i_rst=self.rst,
            o_stb=self.stb,
            io_pins=self.pins
        )

    def test_init(self):
        self.setUp_cpu()
        f = self.inst
        self.assertEqual(f.type, "cpu")
        self.assertEqual(f.parameters, OrderedDict([("RESET", 0x1234)]))
        self.assertEqual(list(f.named_ports.keys()), ["clk", "rst", "stb", "pins"])
        self.assertEqual(f.ports, SignalDict([
            (self.stb, "o"),
            (self.pins, "io"),
        ]))

    def test_prepare(self):
        self.setUp_cpu()
        f = self.inst.prepare()
        clk = f.domains["sync"].clk
        self.assertEqual(f.type, "cpu")
        self.assertEqual(f.parameters, OrderedDict([("RESET", 0x1234)]))
        self.assertEqual(list(f.named_ports.keys()), ["clk", "rst", "stb", "pins"])
        self.assertEqual(f.ports, SignalDict([
            (clk, "i"),
            (self.rst, "i"),
            (self.stb, "o"),
            (self.pins, "io"),
        ]))
