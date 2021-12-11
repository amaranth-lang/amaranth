# amaranth: UnusedElaboratable=no

from collections import OrderedDict

from amaranth.hdl.ast import *
from amaranth.hdl.cd import *
from amaranth.hdl.ir import *
from amaranth.hdl.mem import *

from .utils import *


class ElaboratesToNone(Elaboratable):
    def elaborate(self, platform):
        return


class ElaboratesToSelf(Elaboratable):
    def elaborate(self, platform):
        return self


class FragmentGetTestCase(FHDLTestCase):
    def test_get_wrong_none(self):
        with self.assertRaisesRegex(AttributeError,
                r"^Object None cannot be elaborated$"):
            Fragment.get(None, platform=None)

        with self.assertWarnsRegex(UserWarning,
                r"^\.elaborate\(\) returned None; missing return statement\?$"):
            with self.assertRaisesRegex(AttributeError,
                    r"^Object None cannot be elaborated$"):
                Fragment.get(ElaboratesToNone(), platform=None)

    def test_get_wrong_self(self):
        with self.assertRaisesRegex(RecursionError,
                r"^Object <.+?ElaboratesToSelf.+?> elaborates to itself$"):
            Fragment.get(ElaboratesToSelf(), platform=None)


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

        with self.assertRaisesRegex(NameError,
                r"^No subfragment at index #1$"):
            f1.find_subfragment(1)
        with self.assertRaisesRegex(NameError,
                r"^No subfragment with name 'fx'$"):
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

        f._propagate_ports(ports=(), all_undef_as_ports=True)
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

        f._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f.ports, SignalDict([]))

    def test_infer_input(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )

        f._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f.ports, SignalDict([
            (self.s1, "i")
        ]))

    def test_request_output(self):
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )

        f._propagate_ports(ports=(self.c1,), all_undef_as_ports=True)
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
        f1._propagate_ports(ports=(), all_undef_as_ports=True)
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
        f1._propagate_ports(ports=(), all_undef_as_ports=True)
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

        f1._propagate_ports(ports=(self.c2,), all_undef_as_ports=True)
        self.assertEqual(f1.ports, SignalDict([
            (self.c2, "o"),
        ]))
        self.assertEqual(f2.ports, SignalDict([
            (self.c2, "o"),
        ]))

    def test_output_from_subfragment_2(self):
        f1 = Fragment()
        f1.add_statements(
            self.c1.eq(self.s1)
        )
        f2 = Fragment()
        f2.add_statements(
            self.c2.eq(self.s1)
        )
        f1.add_subfragment(f2)
        f3 = Fragment()
        f3.add_statements(
            self.s1.eq(0)
        )
        f2.add_subfragment(f3)

        f1._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f2.ports, SignalDict([
            (self.s1, "o"),
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

        f1._propagate_ports(ports=(), all_undef_as_ports=True)
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

        f1._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f1.ports, SignalDict())

    def test_input_cd(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_statements(
            self.c1.eq(self.s1)
        )
        f.add_domains(sync)
        f.add_driver(self.c1, "sync")

        f._propagate_ports(ports=(), all_undef_as_ports=True)
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

        f._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f.ports, SignalDict([
            (self.s1,  "i"),
            (sync.clk, "i"),
        ]))

    def test_inout(self):
        s = Signal()
        f1 = Fragment()
        f2 = Instance("foo", io_x=s)
        f1.add_subfragment(f2)

        f1._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f1.ports, SignalDict([
            (s, "io")
        ]))

    def test_in_out_same_signal(self):
        s = Signal()

        f1 = Instance("foo", i_x=s, o_y=s)
        f2 = Fragment()
        f2.add_subfragment(f1)

        f2._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f1.ports, SignalDict([
            (s, "o")
        ]))

        f3 = Instance("foo", o_y=s, i_x=s)
        f4 = Fragment()
        f4.add_subfragment(f3)

        f4._propagate_ports(ports=(), all_undef_as_ports=True)
        self.assertEqual(f3.ports, SignalDict([
            (s, "o")
        ]))

    def test_clk_rst(self):
        sync = ClockDomain()
        f = Fragment()
        f.add_domains(sync)

        f = f.prepare(ports=(ClockSignal("sync"), ResetSignal("sync")))
        self.assertEqual(f.ports, SignalDict([
            (sync.clk, "i"),
            (sync.rst, "i"),
        ]))

    def test_port_wrong(self):
        f = Fragment()
        with self.assertRaisesRegex(TypeError,
                r"^Only signals may be added as ports, not \(const 1'd1\)$"):
            f.prepare(ports=(Const(1),))

    def test_port_not_iterable(self):
        f = Fragment()
        with self.assertRaisesRegex(TypeError,
                r"^`ports` must be either a list or a tuple, not 1$"):
            f.prepare(ports=1)
        with self.assertRaisesRegex(TypeError,
                (r"^`ports` must be either a list or a tuple, not \(const 1'd1\)"
                    r" \(did you mean `ports=\(<signal>,\)`, rather than `ports=<signal>`\?\)$")):
            f.prepare(ports=Const(1))

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

    def test_propagate_up_local(self):
        cd = ClockDomain(local=True)

        f1 = Fragment()
        f2 = Fragment()
        f1.add_subfragment(f2)
        f2.add_domains(cd)

        f1._propagate_domains_up()
        self.assertEqual(f1.domains, {})

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

        with self.assertRaisesRegex(DomainError,
                (r"^Domain 'sync' is defined by subfragments 'a', <unnamed #1> of fragment "
                    r"'top'; it is necessary to either rename subfragment domains explicitly, "
                    r"or give names to subfragments$")):
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

        with self.assertRaisesRegex(DomainError,
                (r"^Domain 'sync' is defined by subfragments #0, #1 of fragment 'top', some "
                    r"of which have identical names; it is necessary to either rename subfragment "
                    r"domains explicitly, or give distinct names to subfragments$")):
            f._propagate_domains_up()

    def test_domain_conflict_rename_drivers(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        fb.add_driver(ResetSignal("sync"), None)
        f = Fragment()
        f.add_subfragment(fa, "a")
        f.add_subfragment(fb, "b")

        f._propagate_domains_up()
        fb_new, _ = f.subfragments[1]
        self.assertEqual(fb_new.drivers, OrderedDict({
            None: SignalSet((ResetSignal("b_sync"),))
        }))

    def test_domain_conflict_rename_drivers_before_creating_missing(self):
        cda = ClockDomain("sync")
        cdb = ClockDomain("sync")
        s = Signal()

        fa = Fragment()
        fa.add_domains(cda)
        fb = Fragment()
        fb.add_domains(cdb)
        f = Fragment()
        f.add_subfragment(fa, "a")
        f.add_subfragment(fb, "b")
        f.add_driver(s, "b_sync")

        f._propagate_domains(lambda name: ClockDomain(name))

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

        new_domains = f1._propagate_domains(missing_domain=lambda name: None)
        self.assertEqual(f1.domains, {"cd": cd})
        self.assertEqual(f2.domains, {"cd": cd})
        self.assertEqual(new_domains, [])

    def test_propagate_missing(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_driver(s1, "sync")

        with self.assertRaisesRegex(DomainError,
                r"^Domain 'sync' is used but not defined$"):
            f1._propagate_domains(missing_domain=lambda name: None)

    def test_propagate_create_missing(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_driver(s1, "sync")
        f2 = Fragment()
        f1.add_subfragment(f2)

        new_domains = f1._propagate_domains(missing_domain=lambda name: ClockDomain(name))
        self.assertEqual(f1.domains.keys(), {"sync"})
        self.assertEqual(f2.domains.keys(), {"sync"})
        self.assertEqual(f1.domains["sync"], f2.domains["sync"])
        self.assertEqual(new_domains, [f1.domains["sync"]])

    def test_propagate_create_missing_fragment(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_driver(s1, "sync")

        cd = ClockDomain("sync")
        f2 = Fragment()
        f2.add_domains(cd)

        new_domains = f1._propagate_domains(missing_domain=lambda name: f2)
        self.assertEqual(f1.domains.keys(), {"sync"})
        self.assertEqual(f1.domains["sync"], f2.domains["sync"])
        self.assertEqual(new_domains, [])
        self.assertEqual(f1.subfragments, [
            (f2, "cd_sync")
        ])

    def test_propagate_create_missing_fragment_many_domains(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_driver(s1, "sync")

        cd_por  = ClockDomain("por")
        cd_sync = ClockDomain("sync")
        f2 = Fragment()
        f2.add_domains(cd_por, cd_sync)

        new_domains = f1._propagate_domains(missing_domain=lambda name: f2)
        self.assertEqual(f1.domains.keys(), {"sync", "por"})
        self.assertEqual(f2.domains.keys(), {"sync", "por"})
        self.assertEqual(f1.domains["sync"], f2.domains["sync"])
        self.assertEqual(new_domains, [])
        self.assertEqual(f1.subfragments, [
            (f2, "cd_sync")
        ])

    def test_propagate_create_missing_fragment_wrong(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_driver(s1, "sync")

        f2 = Fragment()
        f2.add_domains(ClockDomain("foo"))

        with self.assertRaisesRegex(DomainError,
                (r"^Fragment returned by missing domain callback does not define requested "
                    r"domain 'sync' \(defines 'foo'\)\.$")):
            f1._propagate_domains(missing_domain=lambda name: f2)


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

        with self.assertRaisesRegex(DriverConflict,
               r"^Signal '\(sig s1\)' is driven from multiple fragments: top, top.<unnamed #1>$"):
            self.f1._resolve_hierarchy_conflicts(mode="error")

    def test_conflict_self_sub_warning(self):
        self.setUp_self_sub()

        with self.assertWarnsRegex(DriverConflict,
                (r"^Signal '\(sig s1\)' is driven from multiple fragments: top, top.<unnamed #1>; "
                    r"hierarchy will be flattened$")):
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

        with self.assertRaisesRegex(DriverConflict,
                r"^Memory 'm' is accessed from multiple fragments: top\.<unnamed #0>, "
                    r"top\.<unnamed #1>$"):
            self.f1._resolve_hierarchy_conflicts(mode="error")

    def test_conflict_memory_warning(self):
        self.setUp_memory()

        with self.assertWarnsRegex(DriverConflict,
                (r"^Memory 'm' is accessed from multiple fragments: top.<unnamed #0>, "
                    r"top.<unnamed #1>; hierarchy will be flattened$")):
            self.f1._resolve_hierarchy_conflicts(mode="warn")

    def test_explicit_flatten(self):
        self.f1 = Fragment()
        self.f2 = Fragment()
        self.f2.flatten = True
        self.f1.add_subfragment(self.f2)

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [])

    def test_no_conflict_local_domains(self):
        f1 = Fragment()
        cd1 = ClockDomain("d", local=True)
        f1.add_domains(cd1)
        f1.add_driver(ClockSignal("d"))
        f2 = Fragment()
        cd2 = ClockDomain("d", local=True)
        f2.add_domains(cd2)
        f2.add_driver(ClockSignal("d"))
        f3 = Fragment()
        f3.add_subfragment(f1)
        f3.add_subfragment(f2)
        f3.prepare()


class InstanceTestCase(FHDLTestCase):
    def test_construct(self):
        s1 = Signal()
        s2 = Signal()
        s3 = Signal()
        s4 = Signal()
        s5 = Signal()
        s6 = Signal()
        inst = Instance("foo",
            ("a", "ATTR1", 1),
            ("p", "PARAM1", 0x1234),
            ("i", "s1", s1),
            ("o", "s2", s2),
            ("io", "s3", s3),
            a_ATTR2=2,
            p_PARAM2=0x5678,
            i_s4=s4,
            o_s5=s5,
            io_s6=s6,
        )
        self.assertEqual(inst.attrs, OrderedDict([
            ("ATTR1", 1),
            ("ATTR2", 2),
        ]))
        self.assertEqual(inst.parameters, OrderedDict([
            ("PARAM1", 0x1234),
            ("PARAM2", 0x5678),
        ]))
        self.assertEqual(inst.named_ports, OrderedDict([
            ("s1", (s1, "i")),
            ("s2", (s2, "o")),
            ("s3", (s3, "io")),
            ("s4", (s4, "i")),
            ("s5", (s5, "o")),
            ("s6", (s6, "io")),
        ]))

    def test_cast_ports(self):
        inst = Instance("foo",
            ("i", "s1", 1),
            ("o", "s2", 2),
            ("io", "s3", 3),
            i_s4=4,
            o_s5=5,
            io_s6=6,
        )
        self.assertRepr(inst.named_ports["s1"][0], "(const 1'd1)")
        self.assertRepr(inst.named_ports["s2"][0], "(const 2'd2)")
        self.assertRepr(inst.named_ports["s3"][0], "(const 2'd3)")
        self.assertRepr(inst.named_ports["s4"][0], "(const 3'd4)")
        self.assertRepr(inst.named_ports["s5"][0], "(const 3'd5)")
        self.assertRepr(inst.named_ports["s6"][0], "(const 3'd6)")

    def test_wrong_construct_arg(self):
        s = Signal()
        with self.assertRaisesRegex(NameError,
                (r"^Instance argument \('', 's1', \(sig s\)\) should be a tuple "
                    r"\(kind, name, value\) where kind is one of \"a\", \"p\", \"i\", \"o\", or \"io\"$")):
            Instance("foo", ("", "s1", s))

    def test_wrong_construct_kwarg(self):
        s = Signal()
        with self.assertRaisesRegex(NameError,
                (r"^Instance keyword argument x_s1=\(sig s\) does not start with one of "
                    r"\"a_\", \"p_\", \"i_\", \"o_\", or \"io_\"$")):
            Instance("foo", x_s1=s)

    def setUp_cpu(self):
        self.rst = Signal()
        self.stb = Signal()
        self.pins = Signal(8)
        self.datal = Signal(4)
        self.datah = Signal(4)
        self.inst = Instance("cpu",
            p_RESET=0x1234,
            i_clk=ClockSignal(),
            i_rst=self.rst,
            o_stb=self.stb,
            o_data=Cat(self.datal, self.datah),
            io_pins=self.pins[:]
        )
        self.wrap = Fragment()
        self.wrap.add_subfragment(self.inst)

    def test_init(self):
        self.setUp_cpu()
        f = self.inst
        self.assertEqual(f.type, "cpu")
        self.assertEqual(f.parameters, OrderedDict([("RESET", 0x1234)]))
        self.assertEqual(list(f.named_ports.keys()), ["clk", "rst", "stb", "data", "pins"])
        self.assertEqual(f.ports, SignalDict([]))

    def test_prepare(self):
        self.setUp_cpu()
        f = self.wrap.prepare()
        sync_clk = f.domains["sync"].clk
        self.assertEqual(f.ports, SignalDict([
            (sync_clk, "i"),
            (self.rst, "i"),
            (self.pins, "io"),
        ]))

    def test_prepare_explicit_ports(self):
        self.setUp_cpu()
        f = self.wrap.prepare(ports=[self.rst, self.stb])
        sync_clk = f.domains["sync"].clk
        sync_rst = f.domains["sync"].rst
        self.assertEqual(f.ports, SignalDict([
            (sync_clk, "i"),
            (sync_rst, "i"),
            (self.rst, "i"),
            (self.stb, "o"),
            (self.pins, "io"),
        ]))

    def test_prepare_slice_in_port(self):
        s = Signal(2)
        f = Fragment()
        f.add_subfragment(Instance("foo", o_O=s[0]))
        f.add_subfragment(Instance("foo", o_O=s[1]))
        fp = f.prepare(ports=[s], missing_domain=lambda name: None)
        self.assertEqual(fp.ports, SignalDict([
            (s, "o"),
        ]))

    def test_prepare_attrs(self):
        self.setUp_cpu()
        self.inst.attrs["ATTR"] = 1
        f = self.inst.prepare()
        self.assertEqual(f.attrs, OrderedDict([
            ("ATTR", 1),
        ]))
