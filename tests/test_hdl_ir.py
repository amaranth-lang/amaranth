# amaranth: UnusedElaboratable=no

from collections import OrderedDict

from amaranth.hdl._ast import *
from amaranth.hdl._cd import *
from amaranth.hdl._dsl import *
from amaranth.hdl._ir import *
from amaranth.hdl._mem import *

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
        nl = build_netlist(f, ports=[])
        self.assertRepr(nl, """
        (
            (module 0 None ('top'))
            (cell 0 0 (top ))
        )
        """)

    def test_loopback(self):
        f = Fragment()
        f.add_statements(
            "comb",
            self.c1.eq(self.s1),
        )
        nl = build_netlist(f, ports=[self.c1, self.s1])
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 's1' 0.2) (output 'c1' 0.2))
            (cell 0 0 (top (output 'c1' 0.2) (input 's1' 2:3)))
        )
        """)

    def test_subfragment_simple(self):
        f1 = Fragment()
        f2 = Fragment()
        f2.add_statements(
            "comb",
            self.c1.eq(~self.s1),
        )
        f1.add_subfragment(f2, "f2")
        nl = build_netlist(f1, ports=[self.c1, self.s1])
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 's1' 0.2) (output 'c1' 1.0))
            (module 1 0 ('top' 'f2') (input 's1' 0.2) (output 'c1' 1.0))
            (cell 0 0 (top (output 'c1' 1.0) (input 's1' 2:3)))
            (cell 1 1 (~ 0.2))
        )
        """)

    def test_tree(self):
        f = Fragment()
        f1 = Fragment()
        f.add_subfragment(f1, "f1")
        f11 = Fragment()
        f1.add_subfragment(f11, "f11")
        f111 = Fragment()
        f11.add_subfragment(f111, "f111")
        f1111 = Fragment()
        f111.add_subfragment(f1111, "f1111")
        f12 = Fragment()
        f1.add_subfragment(f12, "f12")
        f13 = Fragment()
        f1.add_subfragment(f13, "f13")
        f131 = Fragment()
        f13.add_subfragment(f131, "f131")
        f2 = Fragment()
        f.add_subfragment(f2, "f2")
        f2.add_statements(
            "comb",
            self.s2.eq(~self.s1),
        )
        f131.add_statements(
            "comb",
            self.s3.eq(~self.s2),
            Assert(~self.s1),
        )
        f12.add_statements(
            "comb",
            self.c1.eq(~self.s3),
        )
        f1111.add_statements(
            "comb",
            self.c2.eq(~self.s3),
            Assert(self.s1),
        )
        f111.add_statements(
            "comb",
            self.c3.eq(~self.c2),
        )
        nl = build_netlist(f, ports=[self.c1, self.c2, self.c3, self.s1])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's1' 0.2)
                (output 'c1' 5.0)
                (output 'c2' 2.0)
                (output 'c3' 1.0))
            (module 1 0 ('top' 'f1')
                (input 'port$0$2' 0.2)
                (output 'port$1$0' 1.0)
                (output 'port$2$0' 2.0)
                (output 'port$5$0' 5.0)
                (input 'port$10$0' 10.0))
            (module 2 1 ('top' 'f1' 'f11')
                (input 'port$0$2' 0.2)
                (output 'port$1$0' 1.0)
                (output 'port$2$0' 2.0)
                (input 'port$6$0' 6.0))
            (module 3 2 ('top' 'f1' 'f11' 'f111')
                (input 'port$0$2' 0.2)
                (output 'c3' 1.0)
                (output 'c2' 2.0)
                (input 'port$6$0' 6.0))
            (module 4 3 ('top' 'f1' 'f11' 'f111' 'f1111')
                (input 's1' 0.2)
                (output 'c2' 2.0)
                (input 's3' 6.0))
            (module 5 1 ('top' 'f1' 'f12')
                (output 'c1' 5.0)
                (input 's3' 6.0))
            (module 6 1 ('top' 'f1' 'f13')
                (input 'port$0$2' 0.2)
                (output 'port$6$0' 6.0)
                (input 'port$10$0' 10.0))
            (module 7 6 ('top' 'f1' 'f13' 'f131')
                (input 's1' 0.2)
                (output 's3' 6.0)
                (input 's2' 10.0))
            (module 8 0 ('top' 'f2')
                (input 's1' 0.2)
                (output 's2' 10.0))
            (cell 0 0 (top (output 'c1' 5.0) (output 'c2' 2.0) (output 'c3' 1.0) (input 's1' 2:3)))
            (cell 1 3 (~ 2.0))
            (cell 2 4 (~ 6.0))
            (cell 3 4 (assignment_list 1'd0 (1 0:1 1'd1)))
            (cell 4 4 (assert None 0.2 3.0))
            (cell 5 5 (~ 6.0))
            (cell 6 7 (~ 10.0))
            (cell 7 7 (~ 0.2))
            (cell 8 7 (assignment_list 1'd0 (1 0:1 1'd1)))
            (cell 9 7 (assert None 7.0 8.0))
            (cell 10 8 (~ 0.2))
        )
        """)

    def test_port_dict(self):
        f = Fragment()
        nl = build_netlist(f, ports={
            "a": (self.s1, PortDirection.Output),
            "b": (self.s2, PortDirection.Input),
            "c": (self.s3, PortDirection.Inout),
        })
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 'b' 0.2) (inout 'c' 0.3) (output 'a' 1'd0))
            (cell 0 0 (top (output 'a' 1'd0) (input 'b' 2:3) (inout 'c' 3:4)))
        )
        """)

    def test_port_domain(self):
        f = Fragment()
        cd_sync = ClockDomain()
        ctr = Signal(4)
        f.add_domains(cd_sync)
        f.add_driver(ctr, "sync")
        f.add_statements("sync", ctr.eq(ctr + 1))
        nl = build_netlist(f, ports=[
            ClockSignal("sync"),
            ResetSignal("sync"),
            ctr,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 'clk' 0.2) (input 'rst' 0.3) (output 'ctr' 5.0:4))
            (cell 0 0 (top (output 'ctr' 5.0:4) (input 'clk' 2:3) (input 'rst' 3:4)))
            (cell 1 0 (+ (cat 5.0:4 1'd0) 5'd1))
            (cell 2 0 (matches 0.3 1))
            (cell 3 0 (priority_match 1 2.0))
            (cell 4 0 (assignment_list 5.0:4 (1 0:4 1.0:4) (3.0 0:4 4'd0)))
            (cell 5 0 (flipflop 4.0:4 0 pos 0.2 0))
        )
        """)

    def test_port_autodomain(self):
        f = Fragment()
        ctr = Signal(4)
        f.add_driver(ctr, "sync")
        f.add_statements("sync", ctr.eq(ctr + 1))
        nl = build_netlist(f, ports=[ctr])
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 'clk' 0.2) (input 'rst' 0.3) (output 'ctr' 5.0:4))
            (cell 0 0 (top (output 'ctr' 5.0:4) (input 'clk' 2:3) (input 'rst' 3:4)))
            (cell 1 0 (+ (cat 5.0:4 1'd0) 5'd1))
            (cell 2 0 (matches 0.3 1))
            (cell 3 0 (priority_match 1 2.0))
            (cell 4 0 (assignment_list 5.0:4 (1 0:4 1.0:4) (3.0 0:4 4'd0)))
            (cell 5 0 (flipflop 4.0:4 0 pos 0.2 0))
        )
        """)

    def test_port_partial(self):
        f = Fragment()
        f1 = Fragment()
        f.add_subfragment(f1, "f1")
        a = Signal(4)
        b = Signal(4)
        c = Signal(3)
        f1.add_driver(c)
        f1.add_statements("comb", c.eq((a * b).shift_right(4)))
        nl = build_netlist(f, ports=[a, b, c])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'a' 0.2:6)
                (input 'b' 0.6:10)
                (output 'c' 1.4:7))
            (module 1 0 ('top' 'f1')
                (input 'a' 0.2:6)
                (input 'b' 0.6:10)
                (output 'c' 1.4:7))
            (cell 0 0 (top
                (output 'c' 1.4:7)
                (input 'a' 2:6)
                (input 'b' 6:10)))
            (cell 1 1 (* (cat 0.2:6 4'd0) (cat 0.6:10 4'd0)))
        )
        """)


    def test_port_instance(self):
        f = Fragment()
        f1 = Fragment()
        f.add_subfragment(f1, "f1")
        a = Signal(4)
        b = Signal(4)
        c = Signal(4)
        d = Signal(4)
        f1.add_subfragment(Instance("t",
            p_p = "meow",
            a_a = True,
            i_aa=a,
            io_bb=b,
            o_cc=c,
            o_dd=d,
        ), "i")
        nl = build_netlist(f, ports=[a, b, c, d])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'a' 0.2:6)
                (inout 'b' 0.6:10)
                (output 'c' 1.0:4)
                (output 'd' 1.4:8))
            (module 1 0 ('top' 'f1')
                (input 'port$0$2' 0.2:6)
                (inout 'port$0$6' 0.6:10)
                (output 'port$1$0' 1.0:4)
                (output 'port$1$4' 1.4:8))
            (cell 0 0 (top
                (output 'c' 1.0:4)
                (output 'd' 1.4:8)
                (input 'a' 2:6)
                (inout 'b' 6:10)))
            (cell 1 1 (instance 't' 'i'
                (param 'p' 'meow')
                (attr 'a' True)
                (input 'aa' 0.2:6)
                (output 'cc' 0:4)
                (output 'dd' 4:8)
                (inout 'bb' 0.6:10)))
        )
        """)

    def test_port_wrong(self):
        f = Fragment()
        a = Signal()
        with self.assertRaisesRegex(TypeError,
                r"^Only signals may be added as ports, not \(const 1'd1\)$"):
            build_netlist(f, ports=(Const(1),))
        with self.assertRaisesRegex(TypeError,
                r"^Port name must be a string, not 1$"):
            build_netlist(f, ports={1: (a, PortDirection.Input)})
        with self.assertRaisesRegex(TypeError,
                r"^Port direction must be a `PortDirection` instance or None, not 'i'$"):
            build_netlist(f, ports={"a": (a, "i")})

    def test_port_not_iterable(self):
        f = Fragment()
        with self.assertRaisesRegex(TypeError,
                r"^`ports` must be a dict, a list or a tuple, not 1$"):
            build_netlist(f, ports=1)
        with self.assertRaisesRegex(TypeError,
                (r"^`ports` must be a dict, a list or a tuple, not \(const 1'd1\)"
                    r" \(did you mean `ports=\(<signal>,\)`, rather than `ports=<signal>`\?\)$")):
            build_netlist(f, ports=Const(1))

class FragmentDomainsTestCase(FHDLTestCase):
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
        (fa, _, _), (fb, _, _) = f.subfragments
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
        fb.add_driver(ResetSignal("sync"), "comb")
        f = Fragment()
        f.add_subfragment(fa, "a")
        f.add_subfragment(fb, "b")

        f._propagate_domains_up()
        fb_new, _, _ = f.subfragments[1]
        self.assertEqual(fb_new.drivers, OrderedDict({
            "comb": SignalSet((ResetSignal("b_sync"),))
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
        f1.add_statements("sync", s1.eq(1))

        with self.assertRaisesRegex(DomainError,
                r"^Domain 'sync' is used but not defined$"):
            f1._propagate_domains(missing_domain=lambda name: None)

    def test_propagate_create_missing(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_statements("sync", s1.eq(1))
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
        f1.add_statements("sync", s1.eq(1))

        cd = ClockDomain("sync")
        f2 = Fragment()
        f2.add_domains(cd)

        new_domains = f1._propagate_domains(missing_domain=lambda name: f2)
        self.assertEqual(f1.domains.keys(), {"sync"})
        self.assertEqual(f1.domains["sync"], f2.domains["sync"])
        self.assertEqual(new_domains, [])
        self.assertEqual(f1.subfragments, [
            (f2, "cd_sync", None)
        ])

    def test_propagate_create_missing_fragment_many_domains(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_statements("sync", s1.eq(1))

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
            (f2, "cd_sync", None)
        ])

    def test_propagate_create_missing_fragment_wrong(self):
        s1 = Signal()
        f1 = Fragment()
        f1.add_statements("sync", s1.eq(1))

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
        self.f1.add_statements("sync", self.c1.eq(0))
        self.f1.add_driver(self.s1)
        self.f1.add_driver(self.c1, "sync")

        self.f1a = Fragment()
        self.f1.add_subfragment(self.f1a, "f1a")

        self.f2 = Fragment()
        self.f2.add_statements("sync", self.c2.eq(1))
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
        self.assertEqual([(f, n) for f, n, _ in self.f1.subfragments], [
            (self.f1a, "f1a"),
            (self.f1b, "f1b"),
            (self.f2a, "f2a"),
        ])
        self.assertRepr(self.f1.statements["sync"], """
        (
            (eq (sig c1) (const 1'd0))
            (eq (sig c2) (const 1'd1))
        )
        """)
        self.assertEqual(self.f1.drivers, {
            "comb": SignalSet((self.s1,)),
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
        self.f2.add_statements("comb", self.c1.eq(0))
        self.f1.add_subfragment(self.f2)

        self.f3 = Fragment()
        self.f3.add_driver(self.s1)
        self.f3.add_statements("comb", self.c2.eq(1))
        self.f1.add_subfragment(self.f3)

    def test_conflict_sub_sub(self):
        self.setUp_sub_sub()

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [])
        self.assertRepr(self.f1.statements["comb"], """
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
        self.f2.add_statements("comb", self.c1.eq(0))
        self.f1.add_subfragment(self.f2)

        self.f3 = Fragment()
        self.f3.add_driver(self.s1)
        self.f3.add_statements("comb", self.c2.eq(1))
        self.f2.add_subfragment(self.f3)

    def test_conflict_self_subsub(self):
        self.setUp_self_subsub()

        self.f1._resolve_hierarchy_conflicts(mode="silent")
        self.assertEqual(self.f1.subfragments, [])
        self.assertRepr(self.f1.statements["comb"], """
        (
            (eq (sig c1) (const 1'd0))
            (eq (sig c2) (const 1'd1))
        )
        """)

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

    def test_prepare_attrs(self):
        self.setUp_cpu()
        self.inst.attrs["ATTR"] = 1
        design = self.inst.prepare()
        self.assertEqual(design.fragment.attrs, OrderedDict([
            ("ATTR", 1),
        ]))


class NamesTestCase(FHDLTestCase):
    def test_assign_names_to_signals(self):
        i = Signal()
        rst = Signal()
        o1 = Signal()
        o2 = Signal()
        o3 = Signal()
        i1 = Signal(name="i")

        f = Fragment()
        f.add_domains(cd_sync := ClockDomain())
        f.add_domains(cd_sync_norst := ClockDomain(reset_less=True))
        f.add_statements("comb", [o1.eq(0)])
        f.add_driver(o1, domain="comb")
        f.add_statements("sync", [o2.eq(i1)])
        f.add_driver(o2, domain="sync")
        f.add_statements("sync_norst", [o3.eq(i1)])
        f.add_driver(o3, domain="sync_norst")

        ports = {
            "i": (i, PortDirection.Input),
            "rst": (rst, PortDirection.Input),
            "o1": (o1, PortDirection.Output),
            "o2": (o2, PortDirection.Output),
            "o3": (o3, PortDirection.Output),
        }
        design = f.prepare(ports)
        self.assertEqual(design.signal_names[design.fragment], SignalDict([
            (i, "i"),
            (rst, "rst"),
            (o1, "o1"),
            (o2, "o2"),
            (o3, "o3"),
            (cd_sync.clk, "clk"),
            (cd_sync.rst, "rst$6"),
            (cd_sync_norst.clk, "sync_norst_clk"),
            (i1, "i$8"),
        ]))

    def test_assign_names_to_fragments(self):
        f = Fragment()
        f.add_subfragment(a := Fragment())
        f.add_subfragment(b := Fragment(), name="b")

        design = Design(f, ports=(), hierarchy=("top",))
        self.assertEqual(design.fragment_names, {
            f: ("top",),
            a: ("top", "U$0"),
            b: ("top", "b")
        })

    def test_assign_names_to_fragments_rename_top(self):
        f = Fragment()
        f.add_subfragment(a := Fragment())
        f.add_subfragment(b := Fragment(), name="b")

        design = Design(f, ports=[], hierarchy=("bench", "cpu"))
        self.assertEqual(design.fragment_names, {
            f: ("bench", "cpu",),
            a: ("bench", "cpu", "U$0"),
            b: ("bench", "cpu", "b")
        })

    def test_assign_names_to_fragments_collide_with_signal(self):
        f = Fragment()
        f.add_subfragment(a_f := Fragment(), name="a")
        a_s = Signal(name="a")

        design = Design(f, ports=[("a", a_s, None)], hierarchy=("top",))
        self.assertEqual(design.fragment_names, {
            f: ("top",),
            a_f: ("top", "a$U$0")
        })

    def test_assign_names_to_fragments_duplicate(self):
        f = Fragment()
        f.add_subfragment(a1_f := Fragment(), name="a")
        f.add_subfragment(a2_f := Fragment(), name="a")

        design = Design(f, ports=[], hierarchy=("top",))
        self.assertEqual(design.fragment_names, {
            f: ("top",),
            a1_f: ("top", "a"),
            a2_f: ("top", "a$U$1"),
        })


class ElaboratesTo(Elaboratable):
    def __init__(self, lower):
        self.lower = lower

    def elaborate(self, platform):
        return self.lower


class OriginsTestCase(FHDLTestCase):
    def test_origins(self):
        elab1 = ElaboratesTo(elab2 := ElaboratesTo(m := Module()))
        frag = Fragment.get(elab1, platform=None)
        self.assertEqual(len(frag.origins), 3)
        self.assertIsInstance(frag.origins, tuple)
        self.assertIs(frag.origins[0], elab1)
        self.assertIs(frag.origins[1], elab2)
        self.assertIs(frag.origins[2], m)

    def test_origins_disable(self):
        inst = Instance("test")
        del inst.origins
        elab = ElaboratesTo(inst)
        frag = Fragment.get(elab, platform=None)
        self.assertFalse(hasattr(frag, "_origins"))


class IOBufferTestCase(FHDLTestCase):
    def test_nir_i(self):
        pad = Signal(4)
        i = Signal(4)
        f = Fragment()
        f.add_subfragment(IOBufferInstance(pad, i=i))
        nl = build_netlist(f, ports=[pad, i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (inout 'pad' 0.2:6)
                (output 'i' 1.0:4)
            )
            (cell 0 0 (top
                (output 'i' 1.0:4)
                (inout 'pad' 2:6)
            ))
            (cell 1 0 (iob 0.2:6 4'd0 0))
        )
        """)

    def test_nir_o(self):
        pad = Signal(4)
        o = Signal(4)
        f = Fragment()
        f.add_subfragment(IOBufferInstance(pad, o=o))
        nl = build_netlist(f, ports=[pad, o])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.6:10)
                (inout 'pad' 0.2:6)
            )
            (cell 0 0 (top
                (input 'o' 6:10)
                (inout 'pad' 2:6)
            ))
            (cell 1 0 (iob 0.2:6 0.6:10 1))
        )
        """)

    def test_nir_oe(self):
        pad = Signal(4)
        o = Signal(4)
        oe = Signal()
        f = Fragment()
        f.add_subfragment(IOBufferInstance(pad, o=o, oe=oe))
        nl = build_netlist(f, ports=[pad, o, oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.6:10)
                (input 'oe' 0.10)
                (inout 'pad' 0.2:6)
            )
            (cell 0 0 (top
                (input 'o' 6:10)
                (input 'oe' 10:11)
                (inout 'pad' 2:6)
            ))
            (cell 1 0 (iob 0.2:6 0.6:10 0.10))
        )
        """)

    def test_nir_io(self):
        pad = Signal(4)
        i = Signal(4)
        o = Signal(4)
        oe = Signal()
        f = Fragment()
        f.add_subfragment(IOBufferInstance(pad, i=i, o=o, oe=oe))
        nl = build_netlist(f, ports=[pad, i, o, oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.6:10)
                (input 'oe' 0.10)
                (inout 'pad' 0.2:6)
                (output 'i' 1.0:4)
            )
            (cell 0 0 (top
                (output 'i' 1.0:4)
                (input 'o' 6:10)
                (input 'oe' 10:11)
                (inout 'pad' 2:6)
            ))
            (cell 1 0 (iob 0.2:6 0.6:10 0.10))
        )
        """)

    def test_wrong_i(self):
        pad = Signal(4)
        i = Signal()
        with self.assertRaisesRegex(ValueError,
                r"^`pad` length \(4\) doesn't match `i` length \(1\)"):
            IOBufferInstance(pad, i=i)

    def test_wrong_o(self):
        pad = Signal(4)
        o = Signal()
        with self.assertRaisesRegex(ValueError,
                r"^`pad` length \(4\) doesn't match `o` length \(1\)"):
            IOBufferInstance(pad, o=o)

    def test_wrong_oe(self):
        pad = Signal(4)
        o = Signal(4)
        oe = Signal(4)
        with self.assertRaisesRegex(ValueError,
                r"^`oe` length \(4\) must be 1"):
            IOBufferInstance(pad, o=o, oe=oe)

    def test_wrong_oe_without_o(self):
        pad = Signal(4)
        oe = Signal()
        with self.assertRaisesRegex(ValueError,
                r"^`oe` must not be used if `o` is not used"):
            IOBufferInstance(pad, oe=oe)


class AssignTestCase(FHDLTestCase):
    def test_simple(self):
        s1 = Signal(8)
        s2 = Signal(8)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:10)
                (output 's1' 0.2:10)
            )
            (cell 0 0 (top
                (output 's1' 0.2:10)
                (input 's2' 2:10)
            ))
        )
        """)

    def test_simple_trunc(self):
        s1 = Signal(8)
        s2 = Signal(10)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:12)
                (output 's1' 0.2:10)
            )
            (cell 0 0 (top
                (output 's1' 0.2:10)
                (input 's2' 2:12)
            ))
        )
        """)

    def test_simple_zext(self):
        s1 = Signal(8)
        s2 = Signal(6)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:8)
                (output 's1' (cat 0.2:8 2'd0))
            )
            (cell 0 0 (top
                (output 's1' (cat 0.2:8 2'd0))
                (input 's2' 2:8)
            ))
        )
        """)

    def test_simple_sext(self):
        s1 = Signal(8)
        s2 = Signal(signed(6))
        f = Fragment()
        f.add_statements(
            "comb",
            s1.eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:8)
                (output 's1' (cat 0.2:8 0.7 0.7))
            )
            (cell 0 0 (top
                (output 's1' (cat 0.2:8 0.7 0.7))
                (input 's2' 2:8)
            ))
        )
        """)

    def test_simple_slice(self):
        s1 = Signal(8)
        s2 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1[2:6].eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (output 's1' 1.0:8)
            )
            (cell 0 0 (top
                (output 's1' 1.0:8)
                (input 's2' 2:6)
            ))
            (cell 1 0 (assignment_list 8'd0 (1 2:6 0.2:6)))
        )
        """)

    def test_simple_part(self):
        s1 = Signal(8)
        s2 = Signal(4)
        s3 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.bit_select(s3, 4).eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 10.0:8)
            )
            (cell 0 0 (top
                (output 's1' 10.0:8)
                (input 's2' 2:6)
                (input 's3' 6:10)
            ))
            (cell 1 0 (matches 0.6:10 0000))
            (cell 2 0 (matches 0.6:10 0001))
            (cell 3 0 (matches 0.6:10 0010))
            (cell 4 0 (matches 0.6:10 0011))
            (cell 5 0 (matches 0.6:10 0100))
            (cell 6 0 (matches 0.6:10 0101))
            (cell 7 0 (matches 0.6:10 0110))
            (cell 8 0 (matches 0.6:10 0111))
            (cell 9 0 (priority_match 1 (cat 1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0)))
            (cell 10 0 (assignment_list 8'd0
                (9.0 0:4 0.2:6)
                (9.1 1:5 0.2:6)
                (9.2 2:6 0.2:6)
                (9.3 3:7 0.2:6)
                (9.4 4:8 0.2:6)
                (9.5 5:8 0.2:5)
                (9.6 6:8 0.2:4)
                (9.7 7:8 0.2)
            ))
        )
        """)

    def test_simple_part_short(self):
        s1 = Signal(8)
        s2 = Signal(4)
        s3 = Signal(2)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.bit_select(s3, 4).eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:8)
                (output 's1' 6.0:8)
            )
            (cell 0 0 (top
                (output 's1' 6.0:8)
                (input 's2' 2:6)
                (input 's3' 6:8)
            ))
            (cell 1 0 (matches 0.6:8 00))
            (cell 2 0 (matches 0.6:8 01))
            (cell 3 0 (matches 0.6:8 10))
            (cell 4 0 (matches 0.6:8 11))
            (cell 5 0 (priority_match 1 (cat 1.0 2.0 3.0 4.0)))
            (cell 6 0 (assignment_list 8'd0
                (5.0 0:4 0.2:6)
                (5.1 1:5 0.2:6)
                (5.2 2:6 0.2:6)
                (5.3 3:7 0.2:6)
            ))
        )
        """)

    def test_simple_part_word(self):
        s1 = Signal(16)
        s2 = Signal(4)
        s3 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.word_select(s3, 4).eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 6.0:16)
            )
            (cell 0 0 (top
                (output 's1' 6.0:16)
                (input 's2' 2:6)
                (input 's3' 6:10)
            ))
            (cell 1 0 (matches 0.6:10 0000))
            (cell 2 0 (matches 0.6:10 0001))
            (cell 3 0 (matches 0.6:10 0010))
            (cell 4 0 (matches 0.6:10 0011))
            (cell 5 0 (priority_match 1 (cat 1.0 2.0 3.0 4.0)))
            (cell 6 0 (assignment_list 16'd0
                (5.0 0:4 0.2:6)
                (5.1 4:8 0.2:6)
                (5.2 8:12 0.2:6)
                (5.3 12:16 0.2:6)
            ))
        )
        """)

    def test_simple_part_word_misalign(self):
        s1 = Signal(17)
        s2 = Signal(4)
        s3 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.word_select(s3, 4).eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 7.0:17)
            )
            (cell 0 0 (top
                (output 's1' 7.0:17)
                (input 's2' 2:6)
                (input 's3' 6:10)
            ))
            (cell 1 0 (matches 0.6:10 0000))
            (cell 2 0 (matches 0.6:10 0001))
            (cell 3 0 (matches 0.6:10 0010))
            (cell 4 0 (matches 0.6:10 0011))
            (cell 5 0 (matches 0.6:10 0100))
            (cell 6 0 (priority_match 1 (cat 1.0 2.0 3.0 4.0 5.0)))
            (cell 7 0 (assignment_list 17'd0
                (6.0 0:4 0.2:6)
                (6.1 4:8 0.2:6)
                (6.2 8:12 0.2:6)
                (6.3 12:16 0.2:6)
                (6.4 16:17 0.2)
            ))
        )
        """)

    def test_simple_concat(self):
        s1 = Signal(4)
        s2 = Signal(4)
        s3 = Signal(4)
        s4 = Signal(12)
        f = Fragment()
        f.add_statements(
            "comb",
            Cat(s1, s2, s3).eq(s4)
        )
        f.add_driver(s1, "comb")
        f.add_driver(s2, "comb")
        f.add_driver(s3, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3, s4])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's4' 0.2:14)
                (output 's1' 0.2:6)
                (output 's2' 0.6:10)
                (output 's3' 0.10:14)
            )
            (cell 0 0 (top
                (output 's1' 0.2:6)
                (output 's2' 0.6:10)
                (output 's3' 0.10:14)
                (input 's4' 2:14)
            ))
        )
        """)

    def test_simple_concat_narrow(self):
        s1 = Signal(4)
        s2 = Signal(4)
        s3 = Signal(4)
        s4 = Signal(signed(6))
        f = Fragment()
        f.add_statements(
            "comb",
            Cat(s1, s2, s3).eq(s4)
        )
        f.add_driver(s1, "comb")
        f.add_driver(s2, "comb")
        f.add_driver(s3, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3, s4])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's4' 0.2:8)
                (output 's1' 0.2:6)
                (output 's2' (cat 0.6:8 0.7 0.7))
                (output 's3' (cat 0.7 0.7 0.7 0.7))
            )
            (cell 0 0 (top
                (output 's1' 0.2:6)
                (output 's2' (cat 0.6:8 0.7 0.7))
                (output 's3' (cat 0.7 0.7 0.7 0.7))
                (input 's4' 2:8)
            ))
        )
        """)

    def test_simple_operator(self):
        s1 = Signal(8)
        s2 = Signal(8)
        s3 = Signal(8)
        f = Fragment()
        f.add_statements("comb", [
            s1.as_signed().eq(s3),
            s2.as_unsigned().eq(s3),
        ])
        f.add_driver(s1, "comb")
        f.add_driver(s2, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's3' 0.2:10)
                (output 's1' 0.2:10)
                (output 's2' 0.2:10)
            )
            (cell 0 0 (top
                (output 's1' 0.2:10)
                (output 's2' 0.2:10)
                (input 's3' 2:10)
            ))
        )
        """)

    def test_simple_array(self):
        s1 = Signal(8)
        s2 = Signal(8)
        s3 = Signal(8)
        s4 = Signal(8)
        s5 = Signal(8)
        f = Fragment()
        f.add_statements("comb", [
            Array([s1, s2, s3])[s4].eq(s5),
        ])
        f.add_driver(s1, "comb")
        f.add_driver(s2, "comb")
        f.add_driver(s3, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3, s4, s5])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's4' 0.2:10)
                (input 's5' 0.10:18)
                (output 's1' 5.0:8)
                (output 's2' 6.0:8)
                (output 's3' 7.0:8)
            )
            (cell 0 0 (top
                (output 's1' 5.0:8)
                (output 's2' 6.0:8)
                (output 's3' 7.0:8)
                (input 's4' 2:10)
                (input 's5' 10:18)
            ))
            (cell 1 0 (matches 0.2:10 00000000))
            (cell 2 0 (matches 0.2:10 00000001))
            (cell 3 0 (matches 0.2:10 00000010))
            (cell 4 0 (priority_match 1 (cat 1.0 2.0 3.0)))
            (cell 5 0 (assignment_list 8'd0 (4.0 0:8 0.10:18)))
            (cell 6 0 (assignment_list 8'd0 (4.1 0:8 0.10:18)))
            (cell 7 0 (assignment_list 8'd0 (4.2 0:8 0.10:18)))
        )
        """)

    def test_sliced_slice(self):
        s1 = Signal(12)
        s2 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1[1:11][2:6].eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (output 's1' 1.0:12)
            )
            (cell 0 0 (top
                (output 's1' 1.0:12)
                (input 's2' 2:6)
            ))
            (cell 1 0 (assignment_list 12'd0 (1 3:7 0.2:6)))
        )
        """)

    def test_sliced_concat(self):
        s1 = Signal(4)
        s2 = Signal(4)
        s3 = Signal(4)
        s4 = Signal(4)
        s5 = Signal(4)
        s6 = Signal(8)
        f = Fragment()
        f.add_statements(
            "comb",
            Cat(s1, s2, s3, s4, s5)[5:14].eq(s6)
        )
        f.add_driver(s1, "comb")
        f.add_driver(s2, "comb")
        f.add_driver(s3, "comb")
        f.add_driver(s4, "comb")
        f.add_driver(s5, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3, s4, s5, s6])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's1' 0.2:6)
                (input 's5' 0.6:10)
                (input 's6' 0.10:18)
                (output 's2' 1.0:4)
                (output 's3' 0.13:17)
                (output 's4' 2.0:4)
            )
            (cell 0 0 (top
                (output 's2' 1.0:4)
                (output 's3' 0.13:17)
                (output 's4' 2.0:4)
                (input 's1' 2:6)
                (input 's5' 6:10)
                (input 's6' 10:18)
            ))
            (cell 1 0 (assignment_list 4'd0 (1 1:4 0.10:13)))
            (cell 2 0 (assignment_list 4'd0 (1 0:2 (cat 0.17 1'd0))))
        )
        """)

    def test_sliced_part(self):
        s1 = Signal(8)
        s2 = Signal(4)
        s3 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.bit_select(s3, 6)[2:4].eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 10.0:8)
            )
            (cell 0 0 (top
                (output 's1' 10.0:8)
                (input 's2' 2:6)
                (input 's3' 6:10)
            ))
            (cell 1 0 (matches 0.6:10 0000))
            (cell 2 0 (matches 0.6:10 0001))
            (cell 3 0 (matches 0.6:10 0010))
            (cell 4 0 (matches 0.6:10 0011))
            (cell 5 0 (matches 0.6:10 0100))
            (cell 6 0 (matches 0.6:10 0101))
            (cell 7 0 (matches 0.6:10 0110))
            (cell 8 0 (matches 0.6:10 0111))
            (cell 9 0 (priority_match 1 (cat 1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0)))
            (cell 10 0 (assignment_list 8'd0
                (9.0 2:4 0.2:4)
                (9.1 3:5 0.2:4)
                (9.2 4:6 0.2:4)
                (9.3 5:7 0.2:4)
                (9.4 6:8 0.2:4)
                (9.5 7:8 0.2)
            ))
        )
        """)

    def test_sliced_part_word(self):
        s1 = Signal(8)
        s2 = Signal(4)
        s3 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.word_select(s3, 4)[1:3].eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 4.0:8)
            )
            (cell 0 0 (top
                (output 's1' 4.0:8)
                (input 's2' 2:6)
                (input 's3' 6:10)
            ))
            (cell 1 0 (matches 0.6:10 0000))
            (cell 2 0 (matches 0.6:10 0001))
            (cell 3 0 (priority_match 1 (cat 1.0 2.0)))
            (cell 4 0 (assignment_list 8'd0
                (3.0 1:3 0.2:4)
                (3.1 5:7 0.2:4)
            ))
        )
        """)

    def test_sliced_array(self):
        s1 = Signal(8)
        s2 = Signal(8)
        s3 = Signal(8)
        s4 = Signal(8)
        s5 = Signal(8)
        f = Fragment()
        f.add_statements("comb", [
            Array([s1, s2, s3])[s4][2:7].eq(s5),
        ])
        f.add_driver(s1, "comb")
        f.add_driver(s2, "comb")
        f.add_driver(s3, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3, s4, s5])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's4' 0.2:10)
                (input 's5' 0.10:18)
                (output 's1' 5.0:8)
                (output 's2' 6.0:8)
                (output 's3' 7.0:8)
            )
            (cell 0 0 (top
                (output 's1' 5.0:8)
                (output 's2' 6.0:8)
                (output 's3' 7.0:8)
                (input 's4' 2:10)
                (input 's5' 10:18)
            ))
            (cell 1 0 (matches 0.2:10 00000000))
            (cell 2 0 (matches 0.2:10 00000001))
            (cell 3 0 (matches 0.2:10 00000010))
            (cell 4 0 (priority_match 1 (cat 1.0 2.0 3.0)))
            (cell 5 0 (assignment_list 8'd0 (4.0 2:7 0.10:15)))
            (cell 6 0 (assignment_list 8'd0 (4.1 2:7 0.10:15)))
            (cell 7 0 (assignment_list 8'd0 (4.2 2:7 0.10:15)))
        )
        """)

    def test_part_slice(self):
        s1 = Signal(8)
        s2 = Signal(4)
        s3 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1[1:7].bit_select(s3, 4).eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 8.0:8)
            )
            (cell 0 0 (top
                (output 's1' 8.0:8)
                (input 's2' 2:6)
                (input 's3' 6:10)
            ))
            (cell 1 0 (matches 0.6:10 0000))
            (cell 2 0 (matches 0.6:10 0001))
            (cell 3 0 (matches 0.6:10 0010))
            (cell 4 0 (matches 0.6:10 0011))
            (cell 5 0 (matches 0.6:10 0100))
            (cell 6 0 (matches 0.6:10 0101))
            (cell 7 0 (priority_match 1 (cat 1.0 2.0 3.0 4.0 5.0 6.0)))
            (cell 8 0 (assignment_list 8'd0
                (7.0 1:5 0.2:6)
                (7.1 2:6 0.2:6)
                (7.2 3:7 0.2:6)
                (7.3 4:7 0.2:5)
                (7.4 5:7 0.2:4)
                (7.5 6:7 0.2)
            ))
        )
        """)

    def test_sliced_part_slice(self):
        s1 = Signal(12)
        s2 = Signal(4)
        s3 = Signal(4)
        f = Fragment()
        f.add_statements(
            "comb",
            s1[3:9].bit_select(s3, 4)[1:3].eq(s2)
        )
        f.add_driver(s1, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 8.0:12)
            )
            (cell 0 0 (top
                (output 's1' 8.0:12)
                (input 's2' 2:6)
                (input 's3' 6:10)
            ))
            (cell 1 0 (matches 0.6:10 0000))
            (cell 2 0 (matches 0.6:10 0001))
            (cell 3 0 (matches 0.6:10 0010))
            (cell 4 0 (matches 0.6:10 0011))
            (cell 5 0 (matches 0.6:10 0100))
            (cell 6 0 (matches 0.6:10 0101))
            (cell 7 0 (priority_match 1 (cat 1.0 2.0 3.0 4.0 5.0 6.0)))
            (cell 8 0 (assignment_list 12'd0
                (7.0 4:6 0.2:4)
                (7.1 5:7 0.2:4)
                (7.2 6:8 0.2:4)
                (7.3 7:9 0.2:4)
                (7.4 8:9 0.2)
            ))
        )
        """)

    def test_sliced_operator(self):
        s1 = Signal(8)
        s2 = Signal(8)
        s3 = Signal(8)
        f = Fragment()
        f.add_statements("comb", [
            s1.as_signed()[2:7].eq(s3),
            s2.as_unsigned()[2:7].eq(s3),
        ])
        f.add_driver(s1, "comb")
        f.add_driver(s2, "comb")
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's3' 0.2:10)
                (output 's1' 1.0:8)
                (output 's2' 2.0:8)
            )
            (cell 0 0 (top
                (output 's1' 1.0:8)
                (output 's2' 2.0:8)
                (input 's3' 2:10)
            ))
            (cell 1 0 (assignment_list 8'd0 (1 2:7 0.2:7)))
            (cell 2 0 (assignment_list 8'd0 (1 2:7 0.2:7)))
        )
        """)
