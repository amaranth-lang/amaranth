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
            (cell 0 0 (top (input 's1' 2:3) (output 'c1' 0.2)))
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
            (cell 0 0 (top (input 's1' 2:3) (output 'c1' 1.0)))
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
            (cell 0 0 (top (input 's1' 2:3) (output 'c1' 5.0) (output 'c2' 2.0) (output 'c3' 1.0)))
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
            (cell 0 0 (top (input 'b' 2:3) (output 'a' 1'd0) (inout 'c' 3:4)))
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
            (cell 0 0 (top (input 'clk' 2:3) (input 'rst' 3:4) (output 'ctr' 5.0:4)))
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
            (cell 0 0 (top (input 'clk' 2:3) (input 'rst' 3:4) (output 'ctr' 5.0:4)))
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
                (input 'a' 2:6)
                (input 'b' 6:10)
                (output 'c' 1.4:7)))
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
                (input 'a' 2:6)
                (output 'c' 1.0:4)
                (output 'd' 1.4:8)
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

    def test_nir_simple(self):
        f = Fragment()
        i = Signal(3)
        o = Signal(4)
        io = Signal(5)
        f.add_subfragment(Instance("gadget",
            i_i=i,
            o_o=o,
            io_io=io,
            p_param="TEST",
            a_attr=1234,
        ), "my_gadget")
        nl = build_netlist(f, [i, o, io])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i' 0.2:5)
                (inout 'io' 0.5:10)
                (output 'o' 1.0:4)
            )
            (cell 0 0 (top
                (input 'i' 2:5)
                (output 'o' 1.0:4)
                (inout 'io' 5:10)
            ))
            (cell 1 0 (instance 'gadget' 'my_gadget'
                (param 'param' 'TEST')
                (attr 'attr' 1234)
                (input 'i' 0.2:5)
                (output 'o' 0:4)
                (inout 'io' 0.5:10)
            ))
        )
        """)

    def test_nir_out_slice(self):
        f = Fragment()
        o = Signal(6)
        f.add_subfragment(Instance("test",
            o_o=o[:2],
        ), "t1")
        f.add_subfragment(Instance("test",
            o_o=o[2:4],
        ), "t2")
        nl = build_netlist(f, [o])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o' (cat 1.0:2 2.0:2 2'd0))
            )
            (cell 0 0 (top
                (output 'o' (cat 1.0:2 2.0:2 2'd0))
            ))
            (cell 1 0 (instance 'test' 't1'
                (output 'o' 0:2)
            ))
            (cell 2 0 (instance 'test' 't2'
                (output 'o' 0:2)
            ))
        )
        """)

    def test_nir_out_concat(self):
        f = Fragment()
        o1 = Signal(4)
        o2 = Signal(4)
        f.add_subfragment(Instance("test",
            o_o=Cat(o1, o2),
        ))
        nl = build_netlist(f, [o1, o2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o1' 1.0:4)
                (output 'o2' 1.4:8)
            )
            (cell 0 0 (top
                (output 'o1' 1.0:4)
                (output 'o2' 1.4:8)
            ))
            (cell 1 0 (instance 'test' 'U$0'
                (output 'o' 0:8)
            ))
        )
        """)

    def test_nir_operator(self):
        f = Fragment()
        i = Signal(3)
        o = Signal(4)
        io = Signal(5)
        f.add_subfragment(Instance("gadget",
            i_i=i.as_signed(),
            o_o=o.as_signed(),
            io_io=io.as_signed(),
        ), "my_gadget")
        nl = build_netlist(f, [i, o, io])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i' 0.2:5)
                (inout 'io' 0.5:10)
                (output 'o' 1.0:4)
            )
            (cell 0 0 (top
                (input 'i' 2:5)
                (output 'o' 1.0:4)
                (inout 'io' 5:10)
            ))
            (cell 1 0 (instance 'gadget' 'my_gadget'
                (input 'i' 0.2:5)
                (output 'o' 0:4)
                (inout 'io' 0.5:10)
            ))
        )
        """)

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
                (input 'o' 6:10)
                (input 'oe' 10:11)
                (output 'i' 1.0:4)
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
                (input 's2' 2:10)
                (output 's1' 0.2:10)
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
                (input 's2' 2:12)
                (output 's1' 0.2:10)
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
                (input 's2' 2:8)
                (output 's1' (cat 0.2:8 2'd0))
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
                (input 's2' 2:8)
                (output 's1' (cat 0.2:8 0.7 0.7))
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
                (input 's2' 2:6)
                (output 's1' 1.0:8)
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
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 10.0:8)
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
                (input 's2' 2:6)
                (input 's3' 6:8)
                (output 's1' 6.0:8)
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
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 6.0:16)
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
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 7.0:17)
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
                (input 's4' 2:14)
                (output 's1' 0.2:6)
                (output 's2' 0.6:10)
                (output 's3' 0.10:14)
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
                (input 's4' 2:8)
                (output 's1' 0.2:6)
                (output 's2' (cat 0.6:8 0.7 0.7))
                (output 's3' (cat 0.7 0.7 0.7 0.7))
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
                (input 's3' 2:10)
                (output 's1' 0.2:10)
                (output 's2' 0.2:10)
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
                (input 's4' 2:10)
                (input 's5' 10:18)
                (output 's1' 5.0:8)
                (output 's2' 6.0:8)
                (output 's3' 7.0:8)
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
                (input 's2' 2:6)
                (output 's1' 1.0:12)
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
                (input 's1' 2:6)
                (input 's5' 6:10)
                (input 's6' 10:18)
                (output 's2' 1.0:4)
                (output 's3' 0.13:17)
                (output 's4' 2.0:4)
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
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 10.0:8)
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
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 4.0:8)
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
                (input 's4' 2:10)
                (input 's5' 10:18)
                (output 's1' 5.0:8)
                (output 's2' 6.0:8)
                (output 's3' 7.0:8)
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
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 8.0:8)
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
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 8.0:12)
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
                (input 's3' 2:10)
                (output 's1' 1.0:8)
                (output 's2' 2.0:8)
            ))
            (cell 1 0 (assignment_list 8'd0 (1 2:7 0.2:7)))
            (cell 2 0 (assignment_list 8'd0 (1 2:7 0.2:7)))
        )
        """)

class RhsTestCase(FHDLTestCase):
    def test_const(self):
        o1 = Signal(8)
        o2 = Signal(8)
        m = Module()
        m.d.comb += o1.eq(13)
        m.d.comb += o2.eq(-13)
        nl = build_netlist(Fragment.get(m, None), [o1, o2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o1' 8'd13)
                (output 'o2' 8'd243)
            )
            (cell 0 0 (top
                (output 'o1' 8'd13)
                (output 'o2' 8'd243)
            ))
        )
        """)

    def test_operator_signed(self):
        o1 = Signal(8)
        o2 = Signal(8)
        i1 = Signal(unsigned(4))
        i2 = Signal(signed(4))
        m = Module()
        m.d.comb += o1.eq(i1.as_signed())
        m.d.comb += o2.eq(i2.as_unsigned())
        nl = build_netlist(Fragment.get(m, None), [i1, i2, o1, o2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i1' 0.2:6)
                (input 'i2' 0.6:10)
                (output 'o1' (cat 0.2:6 0.5 0.5 0.5 0.5))
                (output 'o2' (cat 0.6:10 4'd0))
            )
            (cell 0 0 (top
                (input 'i1' 2:6)
                (input 'i2' 6:10)
                (output 'o1' (cat 0.2:6 0.5 0.5 0.5 0.5))
                (output 'o2' (cat 0.6:10 4'd0))
            ))
        )
        """)

    def test_operator_unary(self):
        o1 = Signal(8)
        o2 = Signal(8)
        o3 = Signal(8)
        o4 = Signal(8)
        o5 = Signal(8)
        o6 = Signal(8)
        o7 = Signal(2)
        o8 = Signal(2)
        o9 = Signal(2)
        o10 = Signal(2)
        o11 = Signal(2)
        o12 = Signal(2)
        o13 = Signal(2)
        o14 = Signal(2)
        i1 = Signal(unsigned(4))
        i2 = Signal(signed(4))
        m = Module()
        m.d.comb += o1.eq(+i1)
        m.d.comb += o2.eq(+i2)
        m.d.comb += o3.eq(-i1)
        m.d.comb += o4.eq(-i2)
        m.d.comb += o5.eq(~i1)
        m.d.comb += o6.eq(~i2)
        m.d.comb += o7.eq(i1.all())
        m.d.comb += o8.eq(i2.all())
        m.d.comb += o9.eq(i1.any())
        m.d.comb += o10.eq(i2.any())
        m.d.comb += o11.eq(i1.xor())
        m.d.comb += o12.eq(i2.xor())
        m.d.comb += o13.eq(i1.bool())
        m.d.comb += o14.eq(i2.bool())
        nl = build_netlist(Fragment.get(m, None),
                           [i1, i2, o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i1' 0.2:6)
                (input 'i2' 0.6:10)
                (output 'o1' (cat 0.2:6 4'd0))
                (output 'o2' (cat 0.6:10 0.9 0.9 0.9 0.9))
                (output 'o3' (cat 1.0:5 1.4 1.4 1.4))
                (output 'o4' (cat 2.0:5 2.4 2.4 2.4))
                (output 'o5' (cat 3.0:4 4'd0))
                (output 'o6' (cat 4.0:4 4.3 4.3 4.3 4.3))
                (output 'o7' (cat 5.0 1'd0))
                (output 'o8' (cat 6.0 1'd0))
                (output 'o9' (cat 7.0 1'd0))
                (output 'o10' (cat 8.0 1'd0))
                (output 'o11' (cat 9.0 1'd0))
                (output 'o12' (cat 10.0 1'd0))
                (output 'o13' (cat 11.0 1'd0))
                (output 'o14' (cat 12.0 1'd0))
            )
            (cell 0 0 (top
                (input 'i1' 2:6)
                (input 'i2' 6:10)
                (output 'o1' (cat 0.2:6 4'd0))
                (output 'o2' (cat 0.6:10 0.9 0.9 0.9 0.9))
                (output 'o3' (cat 1.0:5 1.4 1.4 1.4))
                (output 'o4' (cat 2.0:5 2.4 2.4 2.4))
                (output 'o5' (cat 3.0:4 4'd0))
                (output 'o6' (cat 4.0:4 4.3 4.3 4.3 4.3))
                (output 'o7' (cat 5.0 1'd0))
                (output 'o8' (cat 6.0 1'd0))
                (output 'o9' (cat 7.0 1'd0))
                (output 'o10' (cat 8.0 1'd0))
                (output 'o11' (cat 9.0 1'd0))
                (output 'o12' (cat 10.0 1'd0))
                (output 'o13' (cat 11.0 1'd0))
                (output 'o14' (cat 12.0 1'd0))
            ))
            (cell 1 0 (- (cat 0.2:6 1'd0)))
            (cell 2 0 (- (cat 0.6:10 0.9)))
            (cell 3 0 (~ 0.2:6))
            (cell 4 0 (~ 0.6:10))
            (cell 5 0 (r& 0.2:6))
            (cell 6 0 (r& 0.6:10))
            (cell 7 0 (r| 0.2:6))
            (cell 8 0 (r| 0.6:10))
            (cell 9 0 (r^ 0.2:6))
            (cell 10 0 (r^ 0.6:10))
            (cell 11 0 (b 0.2:6))
            (cell 12 0 (b 0.6:10))
        )
        """)

    def test_operator_binary_bitwise(self):
        i8u = Signal(8)
        i9u = Signal(9)
        i8s = Signal(signed(8))
        i9s = Signal(signed(9))
        i1 = Signal()
        o1 = Signal(12)
        o2 = Signal(12)
        o3 = Signal(12)
        o4 = Signal(12)
        o5 = Signal(12)
        o6 = Signal(12)
        o7 = Signal(12)
        o8 = Signal(12)
        o9 = Signal(12)
        o10 = Signal(12)
        o11 = Signal(12)
        o12 = Signal(12)
        o13 = Signal(12)
        o14 = Signal(12)
        o15 = Signal(12)
        o16 = Signal(12)
        m = Module()
        m.d.comb += o1.eq(i8u & i8u)
        m.d.comb += o2.eq(i8u & i9u)
        m.d.comb += o3.eq(i8u & i8s)
        m.d.comb += o4.eq(i8u & i9s)
        m.d.comb += o5.eq(i9u | i8u)
        m.d.comb += o6.eq(i9u | i9u)
        m.d.comb += o7.eq(i9u | i8s)
        m.d.comb += o8.eq(i9u | i9s)
        m.d.comb += o9.eq(i8s ^ i8u)
        m.d.comb += o10.eq(i8s ^ i9u)
        m.d.comb += o11.eq(i8s ^ i8s)
        m.d.comb += o12.eq(i8s ^ i9s)
        m.d.comb += o13.eq(Mux(i1, i9s, i8u))
        m.d.comb += o14.eq(Mux(i1, i9s, i9u))
        m.d.comb += o15.eq(Mux(i1, i9s, i8s))
        m.d.comb += o16.eq(Mux(i1, i9s, i9s))
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i9u, i8s, i9s, i1,
            o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i9u' 0.10:19)
                (input 'i8s' 0.19:27)
                (input 'i9s' 0.27:36)
                (input 'i1' 0.36)
                (output 'o1' (cat 1.0:8 4'd0))
                (output 'o2' (cat 2.0:9 3'd0))
                (output 'o3' (cat 3.0:9 3.8 3.8 3.8))
                (output 'o4' (cat 4.0:9 4.8 4.8 4.8))
                (output 'o5' (cat 5.0:9 3'd0))
                (output 'o6' (cat 6.0:9 3'd0))
                (output 'o7' (cat 7.0:10 7.9 7.9))
                (output 'o8' (cat 8.0:10 8.9 8.9))
                (output 'o9' (cat 9.0:9 9.8 9.8 9.8))
                (output 'o10' (cat 10.0:10 10.9 10.9))
                (output 'o11' (cat 11.0:8 11.7 11.7 11.7 11.7))
                (output 'o12' (cat 12.0:9 12.8 12.8 12.8))
                (output 'o13' (cat 13.0:9 13.8 13.8 13.8))
                (output 'o14' (cat 14.0:10 14.9 14.9))
                (output 'o15' (cat 15.0:9 15.8 15.8 15.8))
                (output 'o16' (cat 16.0:9 16.8 16.8 16.8))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i9u' 10:19)
                (input 'i8s' 19:27)
                (input 'i9s' 27:36)
                (input 'i1' 36:37)
                (output 'o1' (cat 1.0:8 4'd0))
                (output 'o2' (cat 2.0:9 3'd0))
                (output 'o3' (cat 3.0:9 3.8 3.8 3.8))
                (output 'o4' (cat 4.0:9 4.8 4.8 4.8))
                (output 'o5' (cat 5.0:9 3'd0))
                (output 'o6' (cat 6.0:9 3'd0))
                (output 'o7' (cat 7.0:10 7.9 7.9))
                (output 'o8' (cat 8.0:10 8.9 8.9))
                (output 'o9' (cat 9.0:9 9.8 9.8 9.8))
                (output 'o10' (cat 10.0:10 10.9 10.9))
                (output 'o11' (cat 11.0:8 11.7 11.7 11.7 11.7))
                (output 'o12' (cat 12.0:9 12.8 12.8 12.8))
                (output 'o13' (cat 13.0:9 13.8 13.8 13.8))
                (output 'o14' (cat 14.0:10 14.9 14.9))
                (output 'o15' (cat 15.0:9 15.8 15.8 15.8))
                (output 'o16' (cat 16.0:9 16.8 16.8 16.8))
            ))
            (cell 1 0 (& 0.2:10 0.2:10))
            (cell 2 0 (& (cat 0.2:10 1'd0) 0.10:19))
            (cell 3 0 (& (cat 0.2:10 1'd0) (cat 0.19:27 0.26)))
            (cell 4 0 (& (cat 0.2:10 1'd0) 0.27:36))
            (cell 5 0 (| 0.10:19 (cat 0.2:10 1'd0)))
            (cell 6 0 (| 0.10:19 0.10:19))
            (cell 7 0 (| (cat 0.10:19 1'd0) (cat 0.19:27 0.26 0.26)))
            (cell 8 0 (| (cat 0.10:19 1'd0) (cat 0.27:36 0.35)))
            (cell 9 0 (^ (cat 0.19:27 0.26) (cat 0.2:10 1'd0)))
            (cell 10 0 (^ (cat 0.19:27 0.26 0.26) (cat 0.10:19 1'd0)))
            (cell 11 0 (^ 0.19:27 0.19:27))
            (cell 12 0 (^ (cat 0.19:27 0.26) 0.27:36))
            (cell 13 0 (m 0.36 0.27:36 (cat 0.2:10 1'd0)))
            (cell 14 0 (m 0.36 (cat 0.27:36 0.35) (cat 0.10:19 1'd0)))
            (cell 15 0 (m 0.36 0.27:36 (cat 0.19:27 0.26)))
            (cell 16 0 (m 0.36 0.27:36 0.27:36))
        )
        """)

    def test_operator_binary_add(self):
        i8u = Signal(8)
        i9u = Signal(9)
        i8s = Signal(signed(8))
        i9s = Signal(signed(9))
        o1 = Signal(12)
        o2 = Signal(12)
        o3 = Signal(12)
        o4 = Signal(12)
        o5 = Signal(12)
        o6 = Signal(12)
        o7 = Signal(12)
        o8 = Signal(12)
        o9 = Signal(12)
        o10 = Signal(12)
        o11 = Signal(12)
        o12 = Signal(12)
        o13 = Signal(12)
        o14 = Signal(12)
        o15 = Signal(12)
        o16 = Signal(12)
        m = Module()
        m.d.comb += o1.eq(i8u + i8u)
        m.d.comb += o2.eq(i8u + i9u)
        m.d.comb += o3.eq(i8u + i8s)
        m.d.comb += o4.eq(i8u + i9s)
        m.d.comb += o5.eq(i9u + i8u)
        m.d.comb += o6.eq(i9u + i9u)
        m.d.comb += o7.eq(i9u + i8s)
        m.d.comb += o8.eq(i9u + i9s)
        m.d.comb += o9.eq(i8s + i8u)
        m.d.comb += o10.eq(i8s + i9u)
        m.d.comb += o11.eq(i8s + i8s)
        m.d.comb += o12.eq(i8s + i9s)
        m.d.comb += o13.eq(i9s + i8u)
        m.d.comb += o14.eq(i9s + i9u)
        m.d.comb += o15.eq(i9s + i8s)
        m.d.comb += o16.eq(i9s + i9s)
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i9u, i8s, i9s,
            o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i9u' 0.10:19)
                (input 'i8s' 0.19:27)
                (input 'i9s' 0.27:36)
                (output 'o1' (cat 1.0:9 3'd0))
                (output 'o2' (cat 2.0:10 2'd0))
                (output 'o3' (cat 3.0:10 3.9 3.9))
                (output 'o4' (cat 4.0:10 4.9 4.9))
                (output 'o5' (cat 5.0:10 2'd0))
                (output 'o6' (cat 6.0:10 2'd0))
                (output 'o7' (cat 7.0:11 7.10))
                (output 'o8' (cat 8.0:11 8.10))
                (output 'o9' (cat 9.0:10 9.9 9.9))
                (output 'o10' (cat 10.0:11 10.10))
                (output 'o11' (cat 11.0:9 11.8 11.8 11.8))
                (output 'o12' (cat 12.0:10 12.9 12.9))
                (output 'o13' (cat 13.0:10 13.9 13.9))
                (output 'o14' (cat 14.0:11 14.10))
                (output 'o15' (cat 15.0:10 15.9 15.9))
                (output 'o16' (cat 16.0:10 16.9 16.9))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i9u' 10:19)
                (input 'i8s' 19:27)
                (input 'i9s' 27:36)
                (output 'o1' (cat 1.0:9 3'd0))
                (output 'o2' (cat 2.0:10 2'd0))
                (output 'o3' (cat 3.0:10 3.9 3.9))
                (output 'o4' (cat 4.0:10 4.9 4.9))
                (output 'o5' (cat 5.0:10 2'd0))
                (output 'o6' (cat 6.0:10 2'd0))
                (output 'o7' (cat 7.0:11 7.10))
                (output 'o8' (cat 8.0:11 8.10))
                (output 'o9' (cat 9.0:10 9.9 9.9))
                (output 'o10' (cat 10.0:11 10.10))
                (output 'o11' (cat 11.0:9 11.8 11.8 11.8))
                (output 'o12' (cat 12.0:10 12.9 12.9))
                (output 'o13' (cat 13.0:10 13.9 13.9))
                (output 'o14' (cat 14.0:11 14.10))
                (output 'o15' (cat 15.0:10 15.9 15.9))
                (output 'o16' (cat 16.0:10 16.9 16.9))
            ))
            (cell 1 0 (+ (cat 0.2:10 1'd0) (cat 0.2:10 1'd0)))
            (cell 2 0 (+ (cat 0.2:10 2'd0) (cat 0.10:19 1'd0)))
            (cell 3 0 (+ (cat 0.2:10 2'd0) (cat 0.19:27 0.26 0.26)))
            (cell 4 0 (+ (cat 0.2:10 2'd0) (cat 0.27:36 0.35)))
            (cell 5 0 (+ (cat 0.10:19 1'd0) (cat 0.2:10 2'd0)))
            (cell 6 0 (+ (cat 0.10:19 1'd0) (cat 0.10:19 1'd0)))
            (cell 7 0 (+ (cat 0.10:19 2'd0) (cat 0.19:27 0.26 0.26 0.26)))
            (cell 8 0 (+ (cat 0.10:19 2'd0) (cat 0.27:36 0.35 0.35)))
            (cell 9 0 (+ (cat 0.19:27 0.26 0.26) (cat 0.2:10 2'd0)))
            (cell 10 0 (+ (cat 0.19:27 0.26 0.26 0.26) (cat 0.10:19 2'd0)))
            (cell 11 0 (+ (cat 0.19:27 0.26) (cat 0.19:27 0.26)))
            (cell 12 0 (+ (cat 0.19:27 0.26 0.26) (cat 0.27:36 0.35)))
            (cell 13 0 (+ (cat 0.27:36 0.35) (cat 0.2:10 2'd0)))
            (cell 14 0 (+ (cat 0.27:36 0.35 0.35) (cat 0.10:19 2'd0)))
            (cell 15 0 (+ (cat 0.27:36 0.35) (cat 0.19:27 0.26 0.26)))
            (cell 16 0 (+ (cat 0.27:36 0.35) (cat 0.27:36 0.35)))
        )
        """)

    def test_operator_binary_sub(self):
        i8u = Signal(8)
        i9u = Signal(9)
        i8s = Signal(signed(8))
        i9s = Signal(signed(9))
        o1 = Signal(12)
        o2 = Signal(12)
        o3 = Signal(12)
        o4 = Signal(12)
        o5 = Signal(12)
        o6 = Signal(12)
        o7 = Signal(12)
        o8 = Signal(12)
        o9 = Signal(12)
        o10 = Signal(12)
        o11 = Signal(12)
        o12 = Signal(12)
        o13 = Signal(12)
        o14 = Signal(12)
        o15 = Signal(12)
        o16 = Signal(12)
        m = Module()
        m.d.comb += o1.eq(i8u - i8u)
        m.d.comb += o2.eq(i8u - i9u)
        m.d.comb += o3.eq(i8u - i8s)
        m.d.comb += o4.eq(i8u - i9s)
        m.d.comb += o5.eq(i9u - i8u)
        m.d.comb += o6.eq(i9u - i9u)
        m.d.comb += o7.eq(i9u - i8s)
        m.d.comb += o8.eq(i9u - i9s)
        m.d.comb += o9.eq(i8s - i8u)
        m.d.comb += o10.eq(i8s - i9u)
        m.d.comb += o11.eq(i8s - i8s)
        m.d.comb += o12.eq(i8s - i9s)
        m.d.comb += o13.eq(i9s - i8u)
        m.d.comb += o14.eq(i9s - i9u)
        m.d.comb += o15.eq(i9s - i8s)
        m.d.comb += o16.eq(i9s - i9s)
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i9u, i8s, i9s,
            o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i9u' 0.10:19)
                (input 'i8s' 0.19:27)
                (input 'i9s' 0.27:36)
                (output 'o1' (cat 1.0:9 1.8 1.8 1.8))
                (output 'o2' (cat 2.0:10 2.9 2.9))
                (output 'o3' (cat 3.0:10 3.9 3.9))
                (output 'o4' (cat 4.0:10 4.9 4.9))
                (output 'o5' (cat 5.0:10 5.9 5.9))
                (output 'o6' (cat 6.0:10 6.9 6.9))
                (output 'o7' (cat 7.0:11 7.10))
                (output 'o8' (cat 8.0:11 8.10))
                (output 'o9' (cat 9.0:10 9.9 9.9))
                (output 'o10' (cat 10.0:11 10.10))
                (output 'o11' (cat 11.0:9 11.8 11.8 11.8))
                (output 'o12' (cat 12.0:10 12.9 12.9))
                (output 'o13' (cat 13.0:10 13.9 13.9))
                (output 'o14' (cat 14.0:11 14.10))
                (output 'o15' (cat 15.0:10 15.9 15.9))
                (output 'o16' (cat 16.0:10 16.9 16.9))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i9u' 10:19)
                (input 'i8s' 19:27)
                (input 'i9s' 27:36)
                (output 'o1' (cat 1.0:9 1.8 1.8 1.8))
                (output 'o2' (cat 2.0:10 2.9 2.9))
                (output 'o3' (cat 3.0:10 3.9 3.9))
                (output 'o4' (cat 4.0:10 4.9 4.9))
                (output 'o5' (cat 5.0:10 5.9 5.9))
                (output 'o6' (cat 6.0:10 6.9 6.9))
                (output 'o7' (cat 7.0:11 7.10))
                (output 'o8' (cat 8.0:11 8.10))
                (output 'o9' (cat 9.0:10 9.9 9.9))
                (output 'o10' (cat 10.0:11 10.10))
                (output 'o11' (cat 11.0:9 11.8 11.8 11.8))
                (output 'o12' (cat 12.0:10 12.9 12.9))
                (output 'o13' (cat 13.0:10 13.9 13.9))
                (output 'o14' (cat 14.0:11 14.10))
                (output 'o15' (cat 15.0:10 15.9 15.9))
                (output 'o16' (cat 16.0:10 16.9 16.9))
            ))
            (cell 1 0 (- (cat 0.2:10 1'd0) (cat 0.2:10 1'd0)))
            (cell 2 0 (- (cat 0.2:10 2'd0) (cat 0.10:19 1'd0)))
            (cell 3 0 (- (cat 0.2:10 2'd0) (cat 0.19:27 0.26 0.26)))
            (cell 4 0 (- (cat 0.2:10 2'd0) (cat 0.27:36 0.35)))
            (cell 5 0 (- (cat 0.10:19 1'd0) (cat 0.2:10 2'd0)))
            (cell 6 0 (- (cat 0.10:19 1'd0) (cat 0.10:19 1'd0)))
            (cell 7 0 (- (cat 0.10:19 2'd0) (cat 0.19:27 0.26 0.26 0.26)))
            (cell 8 0 (- (cat 0.10:19 2'd0) (cat 0.27:36 0.35 0.35)))
            (cell 9 0 (- (cat 0.19:27 0.26 0.26) (cat 0.2:10 2'd0)))
            (cell 10 0 (- (cat 0.19:27 0.26 0.26 0.26) (cat 0.10:19 2'd0)))
            (cell 11 0 (- (cat 0.19:27 0.26) (cat 0.19:27 0.26)))
            (cell 12 0 (- (cat 0.19:27 0.26 0.26) (cat 0.27:36 0.35)))
            (cell 13 0 (- (cat 0.27:36 0.35) (cat 0.2:10 2'd0)))
            (cell 14 0 (- (cat 0.27:36 0.35 0.35) (cat 0.10:19 2'd0)))
            (cell 15 0 (- (cat 0.27:36 0.35) (cat 0.19:27 0.26 0.26)))
            (cell 16 0 (- (cat 0.27:36 0.35) (cat 0.27:36 0.35)))
        )
        """)

    def test_operator_binary_mul(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        i10u = Signal(10)
        i10s = Signal(signed(10))
        o1 = Signal(24)
        o2 = Signal(24)
        o3 = Signal(24)
        o4 = Signal(24)
        m = Module()
        m.d.comb += o1.eq(i8u * i10u)
        m.d.comb += o2.eq(i8u * i10s)
        m.d.comb += o3.eq(i8s * i10u)
        m.d.comb += o4.eq(i8s * i10s)
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i8s, i10u, i10s,
            o1, o2, o3, o4,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i8s' 0.10:18)
                (input 'i10u' 0.18:28)
                (input 'i10s' 0.28:38)
                (output 'o1' (cat 1.0:18 6'd0))
                (output 'o2' (cat 2.0:18 2.17 2.17 2.17 2.17 2.17 2.17))
                (output 'o3' (cat 3.0:18 3.17 3.17 3.17 3.17 3.17 3.17))
                (output 'o4' (cat 4.0:18 4.17 4.17 4.17 4.17 4.17 4.17))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i8s' 10:18)
                (input 'i10u' 18:28)
                (input 'i10s' 28:38)
                (output 'o1' (cat 1.0:18 6'd0))
                (output 'o2' (cat 2.0:18 2.17 2.17 2.17 2.17 2.17 2.17))
                (output 'o3' (cat 3.0:18 3.17 3.17 3.17 3.17 3.17 3.17))
                (output 'o4' (cat 4.0:18 4.17 4.17 4.17 4.17 4.17 4.17))
            ))
            (cell 1 0 (* (cat 0.2:10 10'd0) (cat 0.18:28 8'd0)))
            (cell 2 0 (* (cat 0.2:10 10'd0) (cat 0.28:38 0.37 0.37 0.37 0.37 0.37 0.37 0.37 0.37)))
            (cell 3 0 (* (cat 0.10:18 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17) (cat 0.18:28 8'd0)))
            (cell 4 0 (* (cat 0.10:18 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17) (cat 0.28:38 0.37 0.37 0.37 0.37 0.37 0.37 0.37 0.37)))
        )
        """)

    def test_operator_binary_divmod(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        i6u = Signal(6)
        i6s = Signal(signed(6))
        m = Module()
        o1 = Signal(10)
        o2 = Signal(10)
        o3 = Signal(10)
        o4 = Signal(10)
        o5 = Signal(10)
        o6 = Signal(10)
        o7 = Signal(10)
        o8 = Signal(10)
        o9 = Signal(10)
        o10 = Signal(10)
        o11 = Signal(10)
        o12 = Signal(10)
        o13 = Signal(10)
        o14 = Signal(10)
        o15 = Signal(10)
        o16 = Signal(10)
        m.d.comb += o1.eq(i8u // i6u)
        m.d.comb += o2.eq(i8u % i6u)
        m.d.comb += o3.eq(i8u // i6s)
        m.d.comb += o4.eq(i8u % i6s)
        m.d.comb += o5.eq(i8s // i6u)
        m.d.comb += o6.eq(i8s % i6u)
        m.d.comb += o7.eq(i8s // i6s)
        m.d.comb += o8.eq(i8s % i6s)
        m.d.comb += o9.eq(i6u // i8u)
        m.d.comb += o10.eq(i6u % i8u)
        m.d.comb += o11.eq(i6u // i8s)
        m.d.comb += o12.eq(i6u % i8s)
        m.d.comb += o13.eq(i6s // i8u)
        m.d.comb += o14.eq(i6s % i8u)
        m.d.comb += o15.eq(i6s // i8s)
        m.d.comb += o16.eq(i6s % i8s)
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i8s, i6u, i6s,
            o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i8s' 0.10:18)
                (input 'i6u' 0.18:24)
                (input 'i6s' 0.24:30)
                (output 'o1' (cat 1.0:8 2'd0))
                (output 'o2' (cat 2.0:6 4'd0))
                (output 'o3' (cat 3.0:9 3.8))
                (output 'o4' (cat 4.0:6 4.5 4.5 4.5 4.5))
                (output 'o5' (cat 5.0:8 5.7 5.7))
                (output 'o6' (cat 6.0:6 4'd0))
                (output 'o7' (cat 7.0:9 7.8))
                (output 'o8' (cat 8.0:6 8.5 8.5 8.5 8.5))
                (output 'o9' (cat 9.0:6 4'd0))
                (output 'o10' (cat 10.0:8 2'd0))
                (output 'o11' (cat 11.0:7 11.6 11.6 11.6))
                (output 'o12' (cat 12.0:8 12.7 12.7))
                (output 'o13' (cat 13.0:6 13.5 13.5 13.5 13.5))
                (output 'o14' (cat 14.0:8 2'd0))
                (output 'o15' (cat 15.0:7 15.6 15.6 15.6))
                (output 'o16' (cat 16.0:8 16.7 16.7))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i8s' 10:18)
                (input 'i6u' 18:24)
                (input 'i6s' 24:30)
                (output 'o1' (cat 1.0:8 2'd0))
                (output 'o2' (cat 2.0:6 4'd0))
                (output 'o3' (cat 3.0:9 3.8))
                (output 'o4' (cat 4.0:6 4.5 4.5 4.5 4.5))
                (output 'o5' (cat 5.0:8 5.7 5.7))
                (output 'o6' (cat 6.0:6 4'd0))
                (output 'o7' (cat 7.0:9 7.8))
                (output 'o8' (cat 8.0:6 8.5 8.5 8.5 8.5))
                (output 'o9' (cat 9.0:6 4'd0))
                (output 'o10' (cat 10.0:8 2'd0))
                (output 'o11' (cat 11.0:7 11.6 11.6 11.6))
                (output 'o12' (cat 12.0:8 12.7 12.7))
                (output 'o13' (cat 13.0:6 13.5 13.5 13.5 13.5))
                (output 'o14' (cat 14.0:8 2'd0))
                (output 'o15' (cat 15.0:7 15.6 15.6 15.6))
                (output 'o16' (cat 16.0:8 16.7 16.7))
            ))
            (cell 1 0 (u// 0.2:10 (cat 0.18:24 2'd0)))
            (cell 2 0 (u% 0.2:10 (cat 0.18:24 2'd0)))
            (cell 3 0 (s// (cat 0.2:10 1'd0) (cat 0.24:30 0.29 0.29 0.29)))
            (cell 4 0 (s% (cat 0.2:10 1'd0) (cat 0.24:30 0.29 0.29 0.29)))
            (cell 5 0 (s// 0.10:18 (cat 0.18:24 2'd0)))
            (cell 6 0 (s% 0.10:18 (cat 0.18:24 2'd0)))
            (cell 7 0 (s// (cat 0.10:18 0.17) (cat 0.24:30 0.29 0.29 0.29)))
            (cell 8 0 (s% 0.10:18 (cat 0.24:30 0.29 0.29)))
            (cell 9 0 (u// (cat 0.18:24 2'd0) 0.2:10))
            (cell 10 0 (u% (cat 0.18:24 2'd0) 0.2:10))
            (cell 11 0 (s// (cat 0.18:24 2'd0) 0.10:18))
            (cell 12 0 (s% (cat 0.18:24 2'd0) 0.10:18))
            (cell 13 0 (s// (cat 0.24:30 0.29 0.29 0.29) (cat 0.2:10 1'd0)))
            (cell 14 0 (s% (cat 0.24:30 0.29 0.29 0.29) (cat 0.2:10 1'd0)))
            (cell 15 0 (s// (cat 0.24:30 0.29 0.29) 0.10:18))
            (cell 16 0 (s% (cat 0.24:30 0.29 0.29) 0.10:18))
        )
        """)

    def test_operator_binary_shift(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        i4 = Signal(4)
        o1 = Signal(32)
        o2 = Signal(32)
        o3 = Signal(12)
        o4 = Signal(12)
        m = Module()
        m.d.comb += o1.eq(i8u << i4)
        m.d.comb += o2.eq(i8s << i4)
        m.d.comb += o3.eq(i8u >> i4)
        m.d.comb += o4.eq(i8s >> i4)
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i8s, i4, o1, o2, o3, o4,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i8s' 0.10:18)
                (input 'i4' 0.18:22)
                (output 'o1' (cat 1.0:23 9'd0))
                (output 'o2' (cat 2.0:23 2.22 2.22 2.22 2.22 2.22 2.22 2.22 2.22 2.22))
                (output 'o3' (cat 3.0:8 4'd0))
                (output 'o4' (cat 4.0:8 4.7 4.7 4.7 4.7))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i8s' 10:18)
                (input 'i4' 18:22)
                (output 'o1' (cat 1.0:23 9'd0))
                (output 'o2' (cat 2.0:23 2.22 2.22 2.22 2.22 2.22 2.22 2.22 2.22 2.22))
                (output 'o3' (cat 3.0:8 4'd0))
                (output 'o4' (cat 4.0:8 4.7 4.7 4.7 4.7))
            ))
            (cell 1 0 (<< (cat 0.2:10 15'd0) 0.18:22))
            (cell 2 0 (<< (cat 0.10:18 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17 0.17) 0.18:22))
            (cell 3 0 (u>> 0.2:10 0.18:22))
            (cell 4 0 (s>> 0.10:18 0.18:22))
        )
        """)

    def test_operator_binary_eq(self):
        i8u = Signal(8)
        i9u = Signal(9)
        i8s = Signal(signed(8))
        i9s = Signal(signed(9))
        o1 = Signal(2)
        o2 = Signal(2)
        o3 = Signal(2)
        o4 = Signal(2)
        o5 = Signal(2)
        o6 = Signal(2)
        o7 = Signal(2)
        o8 = Signal(2)
        o9 = Signal(2)
        o10 = Signal(2)
        o11 = Signal(2)
        o12 = Signal(2)
        o13 = Signal(2)
        o14 = Signal(2)
        o15 = Signal(2)
        o16 = Signal(2)
        m = Module()
        m.d.comb += o1.eq(i8u == i8u)
        m.d.comb += o2.eq(i8u != i9u)
        m.d.comb += o3.eq(i8u != i8s)
        m.d.comb += o4.eq(i8u == i9s)
        m.d.comb += o5.eq(i9u != i8u)
        m.d.comb += o6.eq(i9u == i9u)
        m.d.comb += o7.eq(i9u == i8s)
        m.d.comb += o8.eq(i9u != i9s)
        m.d.comb += o9.eq(i8s != i8u)
        m.d.comb += o10.eq(i8s == i9u)
        m.d.comb += o11.eq(i8s == i8s)
        m.d.comb += o12.eq(i8s != i9s)
        m.d.comb += o13.eq(i9s == i8u)
        m.d.comb += o14.eq(i9s != i9u)
        m.d.comb += o15.eq(i9s != i8s)
        m.d.comb += o16.eq(i9s == i9s)
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i9u, i8s, i9s,
            o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i9u' 0.10:19)
                (input 'i8s' 0.19:27)
                (input 'i9s' 0.27:36)
                (output 'o1' (cat 1.0 1'd0))
                (output 'o2' (cat 2.0 1'd0))
                (output 'o3' (cat 3.0 1'd0))
                (output 'o4' (cat 4.0 1'd0))
                (output 'o5' (cat 5.0 1'd0))
                (output 'o6' (cat 6.0 1'd0))
                (output 'o7' (cat 7.0 1'd0))
                (output 'o8' (cat 8.0 1'd0))
                (output 'o9' (cat 9.0 1'd0))
                (output 'o10' (cat 10.0 1'd0))
                (output 'o11' (cat 11.0 1'd0))
                (output 'o12' (cat 12.0 1'd0))
                (output 'o13' (cat 13.0 1'd0))
                (output 'o14' (cat 14.0 1'd0))
                (output 'o15' (cat 15.0 1'd0))
                (output 'o16' (cat 16.0 1'd0))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i9u' 10:19)
                (input 'i8s' 19:27)
                (input 'i9s' 27:36)
                (output 'o1' (cat 1.0 1'd0))
                (output 'o2' (cat 2.0 1'd0))
                (output 'o3' (cat 3.0 1'd0))
                (output 'o4' (cat 4.0 1'd0))
                (output 'o5' (cat 5.0 1'd0))
                (output 'o6' (cat 6.0 1'd0))
                (output 'o7' (cat 7.0 1'd0))
                (output 'o8' (cat 8.0 1'd0))
                (output 'o9' (cat 9.0 1'd0))
                (output 'o10' (cat 10.0 1'd0))
                (output 'o11' (cat 11.0 1'd0))
                (output 'o12' (cat 12.0 1'd0))
                (output 'o13' (cat 13.0 1'd0))
                (output 'o14' (cat 14.0 1'd0))
                (output 'o15' (cat 15.0 1'd0))
                (output 'o16' (cat 16.0 1'd0))
            ))
            (cell 1 0 (== 0.2:10 0.2:10))
            (cell 2 0 (!= (cat 0.2:10 1'd0) 0.10:19))
            (cell 3 0 (!= (cat 0.2:10 1'd0) (cat 0.19:27 0.26)))
            (cell 4 0 (== (cat 0.2:10 1'd0) 0.27:36))
            (cell 5 0 (!= 0.10:19 (cat 0.2:10 1'd0)))
            (cell 6 0 (== 0.10:19 0.10:19))
            (cell 7 0 (== (cat 0.10:19 1'd0) (cat 0.19:27 0.26 0.26)))
            (cell 8 0 (!= (cat 0.10:19 1'd0) (cat 0.27:36 0.35)))
            (cell 9 0 (!= (cat 0.19:27 0.26) (cat 0.2:10 1'd0)))
            (cell 10 0 (== (cat 0.19:27 0.26 0.26) (cat 0.10:19 1'd0)))
            (cell 11 0 (== 0.19:27 0.19:27))
            (cell 12 0 (!= (cat 0.19:27 0.26) 0.27:36))
            (cell 13 0 (== 0.27:36 (cat 0.2:10 1'd0)))
            (cell 14 0 (!= (cat 0.27:36 0.35) (cat 0.10:19 1'd0)))
            (cell 15 0 (!= 0.27:36 (cat 0.19:27 0.26)))
            (cell 16 0 (== 0.27:36 0.27:36))
        )
        """)

    def test_operator_binary_ord(self):
        i8u = Signal(8)
        i9u = Signal(9)
        i8s = Signal(signed(8))
        i9s = Signal(signed(9))
        o1 = Signal(2)
        o2 = Signal(2)
        o3 = Signal(2)
        o4 = Signal(2)
        o5 = Signal(2)
        o6 = Signal(2)
        o7 = Signal(2)
        o8 = Signal(2)
        o9 = Signal(2)
        o10 = Signal(2)
        o11 = Signal(2)
        o12 = Signal(2)
        o13 = Signal(2)
        o14 = Signal(2)
        o15 = Signal(2)
        o16 = Signal(2)
        m = Module()
        m.d.comb += o1.eq(i8u < i8u)
        m.d.comb += o2.eq(i8u < i9u)
        m.d.comb += o3.eq(i8u < i8s)
        m.d.comb += o4.eq(i8u < i9s)
        m.d.comb += o5.eq(i9u > i8u)
        m.d.comb += o6.eq(i9u > i9u)
        m.d.comb += o7.eq(i9u > i8s)
        m.d.comb += o8.eq(i9u > i9s)
        m.d.comb += o9.eq(i8s <= i8u)
        m.d.comb += o10.eq(i8s <= i9u)
        m.d.comb += o11.eq(i8s <= i8s)
        m.d.comb += o12.eq(i8s <= i9s)
        m.d.comb += o13.eq(i9s >= i8u)
        m.d.comb += o14.eq(i9s >= i9u)
        m.d.comb += o15.eq(i9s >= i8s)
        m.d.comb += o16.eq(i9s >= i9s)
        nl = build_netlist(Fragment.get(m, None), [
            i8u, i9u, i8s, i9s,
            o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12, o13, o14, o15, o16,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i9u' 0.10:19)
                (input 'i8s' 0.19:27)
                (input 'i9s' 0.27:36)
                (output 'o1' (cat 1.0 1'd0))
                (output 'o2' (cat 2.0 1'd0))
                (output 'o3' (cat 3.0 1'd0))
                (output 'o4' (cat 4.0 1'd0))
                (output 'o5' (cat 5.0 1'd0))
                (output 'o6' (cat 6.0 1'd0))
                (output 'o7' (cat 7.0 1'd0))
                (output 'o8' (cat 8.0 1'd0))
                (output 'o9' (cat 9.0 1'd0))
                (output 'o10' (cat 10.0 1'd0))
                (output 'o11' (cat 11.0 1'd0))
                (output 'o12' (cat 12.0 1'd0))
                (output 'o13' (cat 13.0 1'd0))
                (output 'o14' (cat 14.0 1'd0))
                (output 'o15' (cat 15.0 1'd0))
                (output 'o16' (cat 16.0 1'd0))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i9u' 10:19)
                (input 'i8s' 19:27)
                (input 'i9s' 27:36)
                (output 'o1' (cat 1.0 1'd0))
                (output 'o2' (cat 2.0 1'd0))
                (output 'o3' (cat 3.0 1'd0))
                (output 'o4' (cat 4.0 1'd0))
                (output 'o5' (cat 5.0 1'd0))
                (output 'o6' (cat 6.0 1'd0))
                (output 'o7' (cat 7.0 1'd0))
                (output 'o8' (cat 8.0 1'd0))
                (output 'o9' (cat 9.0 1'd0))
                (output 'o10' (cat 10.0 1'd0))
                (output 'o11' (cat 11.0 1'd0))
                (output 'o12' (cat 12.0 1'd0))
                (output 'o13' (cat 13.0 1'd0))
                (output 'o14' (cat 14.0 1'd0))
                (output 'o15' (cat 15.0 1'd0))
                (output 'o16' (cat 16.0 1'd0))
            ))
            (cell 1 0 (u< 0.2:10 0.2:10))
            (cell 2 0 (u< (cat 0.2:10 1'd0) 0.10:19))
            (cell 3 0 (s< (cat 0.2:10 1'd0) (cat 0.19:27 0.26)))
            (cell 4 0 (s< (cat 0.2:10 1'd0) 0.27:36))
            (cell 5 0 (u> 0.10:19 (cat 0.2:10 1'd0)))
            (cell 6 0 (u> 0.10:19 0.10:19))
            (cell 7 0 (s> (cat 0.10:19 1'd0) (cat 0.19:27 0.26 0.26)))
            (cell 8 0 (s> (cat 0.10:19 1'd0) (cat 0.27:36 0.35)))
            (cell 9 0 (s<= (cat 0.19:27 0.26) (cat 0.2:10 1'd0)))
            (cell 10 0 (s<= (cat 0.19:27 0.26 0.26) (cat 0.10:19 1'd0)))
            (cell 11 0 (s<= 0.19:27 0.19:27))
            (cell 12 0 (s<= (cat 0.19:27 0.26) 0.27:36))
            (cell 13 0 (s>= 0.27:36 (cat 0.2:10 1'd0)))
            (cell 14 0 (s>= (cat 0.27:36 0.35) (cat 0.10:19 1'd0)))
            (cell 15 0 (s>= 0.27:36 (cat 0.19:27 0.26)))
            (cell 16 0 (s>= 0.27:36 0.27:36))
        )
        """)

    def test_operator_mux(self):
        i8a = Signal(8)
        i8b = Signal(8)
        i1 = Signal()
        i4 = Signal(4)
        o1 = Signal(8)
        o2 = Signal(8)
        m = Module()
        m.d.comb += o1.eq(Mux(i1, i8a, i8b))
        m.d.comb += o2.eq(Mux(i4, i8a, i8b))
        nl = build_netlist(Fragment.get(m, None), [i8a, i8b, i1, i4, o1, o2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8a' 0.2:10)
                (input 'i8b' 0.10:18)
                (input 'i1' 0.18)
                (input 'i4' 0.19:23)
                (output 'o1' 1.0:8)
                (output 'o2' 3.0:8)
            )
            (cell 0 0 (top
                (input 'i8a' 2:10)
                (input 'i8b' 10:18)
                (input 'i1' 18:19)
                (input 'i4' 19:23)
                (output 'o1' 1.0:8)
                (output 'o2' 3.0:8)
            ))
            (cell 1 0 (m 0.18 0.2:10 0.10:18))
            (cell 2 0 (b 0.19:23))
            (cell 3 0 (m 2.0 0.2:10 0.10:18))
        )
        """)

    def test_slice(self):
        i = Signal(8)
        o = Signal(8)
        m = Module()
        m.d.comb += o.eq(i[2:5])
        nl = build_netlist(Fragment.get(m, None), [i, o])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i' 0.2:10)
                (output 'o' (cat 0.4:7 5'd0))
            )
            (cell 0 0 (top
                (input 'i' 2:10)
                (output 'o' (cat 0.4:7 5'd0))
            ))
        )
        """)

    def test_part(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        i4 = Signal(4)
        o1 = Signal(4)
        o2 = Signal(4)
        o3 = Signal(4)
        o4 = Signal(4)
        m = Module()
        m.d.comb += o1.eq(i8u.bit_select(i4, 3))
        m.d.comb += o2.eq(i8s.bit_select(i4, 3))
        m.d.comb += o3.eq(i8u.word_select(i4, 3))
        m.d.comb += o4.eq(i8s.word_select(i4, 3))
        nl = build_netlist(Fragment.get(m, None), [i8u, i8s, i4, o1, o2, o3, o4])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8u' 0.2:10)
                (input 'i8s' 0.10:18)
                (input 'i4' 0.18:22)
                (output 'o1' (cat 1.0:3 1'd0))
                (output 'o2' (cat 2.0:3 1'd0))
                (output 'o3' (cat 3.0:3 1'd0))
                (output 'o4' (cat 4.0:3 1'd0))
            )
            (cell 0 0 (top
                (input 'i8u' 2:10)
                (input 'i8s' 10:18)
                (input 'i4' 18:22)
                (output 'o1' (cat 1.0:3 1'd0))
                (output 'o2' (cat 2.0:3 1'd0))
                (output 'o3' (cat 3.0:3 1'd0))
                (output 'o4' (cat 4.0:3 1'd0))
            ))
            (cell 1 0 (part 0.2:10 unsigned 0.18:22 3 1))
            (cell 2 0 (part 0.10:18 signed 0.18:22 3 1))
            (cell 3 0 (part 0.2:10 unsigned 0.18:22 3 3))
            (cell 4 0 (part 0.10:18 signed 0.18:22 3 3))
        )
        """)

    def test_cat(self):
        i1 = Signal()
        i2 = Signal(8)
        i3 = Signal(3)
        o = Signal(16)
        m = Module()
        m.d.comb += o.eq(Cat(i1, i2, i3))
        nl = build_netlist(Fragment.get(m, None), [i1, i2, i3, o])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i1' 0.2)
                (input 'i2' 0.3:11)
                (input 'i3' 0.11:14)
                (output 'o' (cat 0.2:14 4'd0))
            )
            (cell 0 0 (top
                (input 'i1' 2:3)
                (input 'i2' 3:11)
                (input 'i3' 11:14)
                (output 'o' (cat 0.2:14 4'd0))
            ))
        )
        """)

    def test_arrayproxy(self):
        i8ua = Signal(8)
        i8ub = Signal(8)
        i8uc = Signal(8)
        i8sa = Signal(signed(8))
        i8sb = Signal(signed(8))
        i8sc = Signal(signed(8))
        i4 = Signal(4)
        o1 = Signal(10)
        o2 = Signal(10)
        o3 = Signal(10)
        o4 = Signal(10)
        m = Module()
        m.d.comb += o1.eq(Array([i8ua, i8ub, i8uc])[i4])
        m.d.comb += o2.eq(Array([i8ua, i8ub, i8sc])[i4])
        m.d.comb += o3.eq(Array([i8sa, i8sb, i8sc])[i4])
        m.d.comb += o4.eq(Array([i8sa, i8sb, i4])[i4])
        nl = build_netlist(Fragment.get(m, None), [i8ua, i8ub, i8uc, i8sa, i8sb, i8sc, i4, o1, o2, o3, o4])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8ua' 0.2:10)
                (input 'i8ub' 0.10:18)
                (input 'i8uc' 0.18:26)
                (input 'i8sa' 0.26:34)
                (input 'i8sb' 0.34:42)
                (input 'i8sc' 0.42:50)
                (input 'i4' 0.50:54)
                (output 'o1' (cat 1.0:8 2'd0))
                (output 'o2' (cat 2.0:9 2.8))
                (output 'o3' (cat 3.0:8 3.7 3.7))
                (output 'o4' (cat 4.0:8 4.7 4.7))
            )
            (cell 0 0 (top
                (input 'i8ua' 2:10)
                (input 'i8ub' 10:18)
                (input 'i8uc' 18:26)
                (input 'i8sa' 26:34)
                (input 'i8sb' 34:42)
                (input 'i8sc' 42:50)
                (input 'i4' 50:54)
                (output 'o1' (cat 1.0:8 2'd0))
                (output 'o2' (cat 2.0:9 2.8))
                (output 'o3' (cat 3.0:8 3.7 3.7))
                (output 'o4' (cat 4.0:8 4.7 4.7))
            ))
            (cell 1 0 (array_mux 8 0.50:54 (0.2:10 0.10:18 0.18:26)))
            (cell 2 0 (array_mux 9 0.50:54 ((cat 0.2:10 1'd0) (cat 0.10:18 1'd0) (cat 0.42:50 0.49))))
            (cell 3 0 (array_mux 8 0.50:54 (0.26:34 0.34:42 0.42:50)))
            (cell 4 0 (array_mux 8 0.50:54 (0.26:34 0.34:42 (cat 0.50:54 4'd0))))
        )
        """)

    def test_anyvalue(self):
        o1 = Signal(12)
        o2 = Signal(12)
        o3 = Signal(12)
        o4 = Signal(12)
        m = Module()
        m.d.comb += o1.eq(AnyConst(8))
        m.d.comb += o2.eq(AnyConst(signed(8)))
        m.d.comb += o3.eq(AnySeq(8))
        m.d.comb += o4.eq(AnySeq(signed(8)))
        nl = build_netlist(Fragment.get(m, None), [o1, o2, o3, o4])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o1' (cat 1.0:8 4'd0))
                (output 'o2' (cat 2.0:8 2.7 2.7 2.7 2.7))
                (output 'o3' (cat 3.0:8 4'd0))
                (output 'o4' (cat 4.0:8 4.7 4.7 4.7 4.7))
            )
            (cell 0 0 (top
                (output 'o1' (cat 1.0:8 4'd0))
                (output 'o2' (cat 2.0:8 2.7 2.7 2.7 2.7))
                (output 'o3' (cat 3.0:8 4'd0))
                (output 'o4' (cat 4.0:8 4.7 4.7 4.7 4.7))
            ))
            (cell 1 0 (anyconst 8))
            (cell 2 0 (anyconst 8))
            (cell 3 0 (anyseq 8))
            (cell 4 0 (anyseq 8))
        )
        """)

    def test_initial(self):
        o1 = Signal(12)
        m = Module()
        m.d.comb += o1.eq(Initial())
        nl = build_netlist(Fragment.get(m, None), [o1])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o1' (cat 1.0 11'd0))
            )
            (cell 0 0 (top
                (output 'o1' (cat 1.0 11'd0))
            ))
            (cell 1 0 (initial))
        )
        """)

class SwitchTestCase(FHDLTestCase):
    def test_comb(self):
        o1 = Signal(8)
        o2 = Signal(8, init=123)
        i = Signal(4)
        i2 = Signal(4)
        m = Module()
        with m.If(i[0]):
            m.d.comb += o1.eq(1)
        with m.Elif(i[1]):
            m.d.comb += o1[2:4].eq(2)
            m.d.comb += o2.eq(3)
        with m.If(i[2]):
            with m.Switch(i2):
                with m.Case(1):
                    m.d.comb += o2.eq(4)
                with m.Case(2, 4):
                    m.d.comb += o2.eq(5)
                with m.Case('11--'):
                    m.d.comb += o2.eq(6)
                    with m.If(i[3]):
                        m.d.comb += o1.eq(7)
        nl = build_netlist(Fragment.get(m, None), [i, i2, o1, o2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i' 0.2:6)
                (input 'i2' 0.6:10)
                (output 'o1' 12.0:8)
                (output 'o2' 13.0:8)
            )
            (cell 0 0 (top
                (input 'i' 2:6)
                (input 'i2' 6:10)
                (output 'o1' 12.0:8)
                (output 'o2' 13.0:8)
            ))
            (cell 1 0 (matches 0.2:4 -1))
            (cell 2 0 (matches 0.2:4 1-))
            (cell 3 0 (priority_match 1 (cat 1.0 2.0)))
            (cell 4 0 (matches 0.4 1))
            (cell 5 0 (priority_match 1 4.0))
            (cell 6 0 (matches 0.6:10 0001))
            (cell 7 0 (matches 0.6:10 0010 0100))
            (cell 8 0 (matches 0.6:10 11--))
            (cell 9 0 (priority_match 5.0 (cat 6.0 7.0 8.0)))
            (cell 10 0 (matches 0.5 1))
            (cell 11 0 (priority_match 9.2 10.0))
            (cell 12 0 (assignment_list 8'd0
                (3.0 0:8 8'd1)
                (3.1 2:4 2'd2)
                (11.0 0:8 8'd7)
            ))
            (cell 13 0 (assignment_list 8'd123
                (3.1 0:8 8'd3)
                (9.0 0:8 8'd4)
                (9.1 0:8 8'd5)
                (9.2 0:8 8'd6)
            ))
        )
        """)

    def test_sync(self):
        o1 = Signal(8, reset_less=True)
        o2 = Signal(8, init=123)
        o3 = Signal(8, init=45, reset_less=True)
        o4 = Signal(8, init=67)
        o5 = Signal(8, init=89)
        i1 = Signal(8)
        i2 = Signal()
        m = Module()
        m.domains.a = ClockDomain()
        m.domains.b = ClockDomain(async_reset=True)
        m.domains.c = ClockDomain(reset_less=True, clk_edge="neg")
        with m.If(i2):
            m.d.a += o1.eq(i1)
            m.d.a += o2.eq(i1)
            m.d.b += o3.eq(i1)
            m.d.b += o4.eq(i1)
            m.d.c += o5.eq(i1)
        nl = build_netlist(Fragment.get(m, None), [
            i1, i2, o1, o2, o3, o4, o5,
            ClockSignal("a"), ResetSignal("a"),
            ClockSignal("b"), ResetSignal("b"),
            ClockSignal("c"),
        ])
        # TODO: inefficiency in NIR emitter:
        # matches and priority_match duplicated between clock domains — add cache?
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i1' 0.2:10)
                (input 'i2' 0.10)
                (input 'a_clk' 0.11)
                (input 'a_rst' 0.12)
                (input 'b_clk' 0.13)
                (input 'b_rst' 0.14)
                (input 'c_clk' 0.15)
                (output 'o1' 8.0:8)
                (output 'o2' 12.0:8)
                (output 'o3' 14.0:8)
                (output 'o4' 16.0:8)
                (output 'o5' 18.0:8)
            )
            (cell 0 0 (top
                (input 'i1' 2:10)
                (input 'i2' 10:11)
                (input 'a_clk' 11:12)
                (input 'a_rst' 12:13)
                (input 'b_clk' 13:14)
                (input 'b_rst' 14:15)
                (input 'c_clk' 15:16)
                (output 'o1' 8.0:8)
                (output 'o2' 12.0:8)
                (output 'o3' 14.0:8)
                (output 'o4' 16.0:8)
                (output 'o5' 18.0:8)
            ))
            (cell 1 0 (matches 0.10 1))
            (cell 2 0 (priority_match 1 1.0))
            (cell 3 0 (matches 0.10 1))
            (cell 4 0 (priority_match 1 3.0))
            (cell 5 0 (matches 0.10 1))
            (cell 6 0 (priority_match 1 5.0))
            (cell 7 0 (assignment_list 8.0:8 (2.0 0:8 0.2:10)))
            (cell 8 0 (flipflop 7.0:8 0 pos 0.11 0))
            (cell 9 0 (matches 0.12 1))
            (cell 10 0 (priority_match 1 9.0))
            (cell 11 0 (assignment_list 12.0:8 (2.0 0:8 0.2:10) (10.0 0:8 8'd123)))
            (cell 12 0 (flipflop 11.0:8 123 pos 0.11 0))
            (cell 13 0 (assignment_list 14.0:8 (4.0 0:8 0.2:10)))
            (cell 14 0 (flipflop 13.0:8 45 pos 0.13 0))
            (cell 15 0 (assignment_list 16.0:8 (4.0 0:8 0.2:10)))
            (cell 16 0 (flipflop 15.0:8 67 pos 0.13 0.14))
            (cell 17 0 (assignment_list 18.0:8 (6.0 0:8 0.2:10)))
            (cell 18 0 (flipflop 17.0:8 89 neg 0.15 0))
        )
        """)

    def test_assert(self):
        m = Module()
        i = Signal(6)
        m.domains.a = ClockDomain()
        m.domains.b = ClockDomain(async_reset=True)
        m.domains.c = ClockDomain(reset_less=True, clk_edge="neg")
        with m.If(i[5]):
            m.d.comb += Assert(i[0])
            m.d.comb += Assume(i[1], name="a")
            m.d.a += Assert(i[2])
            m.d.b += Assume(i[3], name="b")
            m.d.c += Cover(i[4], name="c")
            m.d.comb += Cover(i, name="d")
        nl = build_netlist(Fragment.get(m, None), [
            i,
            ClockSignal("a"), ResetSignal("a"),
            ClockSignal("b"), ResetSignal("b"),
            ClockSignal("c"),
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i' 0.2:8)
                (input 'a_clk' 0.8)
                (input 'a_rst' 0.9)
                (input 'b_clk' 0.10)
                (input 'b_rst' 0.11)
                (input 'c_clk' 0.12)
            )
            (cell 0 0 (top
                (input 'i' 2:8)
                (input 'a_clk' 8:9)
                (input 'a_rst' 9:10)
                (input 'b_clk' 10:11)
                (input 'b_rst' 11:12)
                (input 'c_clk' 12:13)
            ))
            (cell 1 0 (matches 0.7 1))
            (cell 2 0 (priority_match 1 1.0))
            (cell 3 0 (assignment_list 1'd0 (2.0 0:1 1'd1)))
            (cell 4 0 (assert None 0.2 3.0))
            (cell 5 0 (assignment_list 1'd0 (2.0 0:1 1'd1)))
            (cell 6 0 (assume 'a' 0.3 5.0))
            (cell 7 0 (b 0.2:8))
            (cell 8 0 (assignment_list 1'd0 (2.0 0:1 1'd1)))
            (cell 9 0 (cover 'd' 7.0 8.0))
            (cell 10 0 (matches 0.7 1))
            (cell 11 0 (priority_match 1 10.0))
            (cell 12 0 (assignment_list 1'd0 (11.0 0:1 1'd1)))
            (cell 13 0 (assert None 0.4 12.0 pos 0.8))
            (cell 14 0 (matches 0.7 1))
            (cell 15 0 (priority_match 1 14.0))
            (cell 16 0 (assignment_list 1'd0 (15.0 0:1 1'd1)))
            (cell 17 0 (assume 'b' 0.5 16.0 pos 0.10))
            (cell 18 0 (matches 0.7 1))
            (cell 19 0 (priority_match 1 18.0))
            (cell 20 0 (assignment_list 1'd0 (19.0 0:1 1'd1)))
            (cell 21 0 (cover 'c' 0.6 20.0 neg 0.12))


        )
        """)
