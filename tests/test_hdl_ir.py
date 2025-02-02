# amaranth: UnusedElaboratable=no

from collections import OrderedDict

from amaranth.hdl._ast import *
from amaranth.hdl._cd import *
from amaranth.hdl._dsl import *
from amaranth.hdl._ir import *
from amaranth.hdl._mem import *
from amaranth.hdl._nir import SignalField, CombinationalCycle
from amaranth.hdl._xfrm import *

from amaranth.lib import enum, data

from .utils import *


class ElaboratesToNone(Elaboratable):
    def elaborate(self, platform):
        return


class ElaboratesToSelf(Elaboratable):
    def elaborate(self, platform):
        return self


class FragmentGetTestCase(FHDLTestCase):
    def test_get_wrong_none(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object None is not an 'Elaboratable' nor 'Fragment'$"):
            Fragment.get(None, platform=None)

        with self.assertWarnsRegex(UserWarning,
                r"^\.elaborate\(\) returned None; missing return statement\?$"):
            with self.assertRaisesRegex(TypeError,
                    r"^Object None is not an 'Elaboratable' nor 'Fragment'$"):
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


class DuplicateElaboratableTestCase(FHDLTestCase):
    def test_duplicate(self):
        sub = Module()
        m = Module()
        m.submodules.a = sub
        m.submodules.b = sub
        with self.assertRaisesRegex(DuplicateElaboratable,
                r"^Elaboratable .* is included twice in the hierarchy, as "
                r"top\.a and top\.b$"):
            Fragment.get(m, None).prepare()


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
            (cell 0 0 (top))
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
                (input 's1' 0.2)
                (output 'c3' 1.0)
                (output 'c2' 2.0)
                (output 'c1' 5.0)
                (input 's2' 10.0))
            (module 2 1 ('top' 'f1' 'f11')
                (input 's1' 0.2)
                (output 'c3' 1.0)
                (output 'c2' 2.0)
                (input 's3' 6.0))
            (module 3 2 ('top' 'f1' 'f11' 'f111')
                (input 's1' 0.2)
                (output 'c3' 1.0)
                (output 'c2' 2.0)
                (input 's3' 6.0))
            (module 4 3 ('top' 'f1' 'f11' 'f111' 'f1111')
                (input 's1' 0.2)
                (output 'c2' 2.0)
                (input 's3' 6.0))
            (module 5 1 ('top' 'f1' 'f12')
                (output 'c1' 5.0)
                (input 's3' 6.0))
            (module 6 1 ('top' 'f1' 'f13')
                (input 's1' 0.2)
                (output 's3' 6.0)
                (input 's2' 10.0))
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
            (cell 4 4 (assert 0.2 3.0 None))
            (cell 5 5 (~ 6.0))
            (cell 6 7 (~ 10.0))
            (cell 7 7 (~ 0.2))
            (cell 8 7 (assignment_list 1'd0 (1 0:1 1'd1)))
            (cell 9 7 (assert 7.0 8.0 None))
            (cell 10 8 (~ 0.2))
        )
        """)

    def test_port_dict(self):
        f = Fragment()
        nl = build_netlist(f, ports={
            "a": (self.s1, PortDirection.Output),
            "b": (self.s2, PortDirection.Input),
            "c": (IOPort(1, name="io3"), PortDirection.Inout),
        })
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 'b' 0.2) (output 'a' 1'd0) (io inout 'c' 0.0))
            (cell 0 0 (top (input 'b' 2:3) (output 'a' 1'd0)))
        )
        """)

    def test_port_domain(self):
        f = Fragment()
        cd_sync = ClockDomain()
        ctr = Signal(4)
        f.add_domains(cd_sync)
        f.add_statements("sync", ctr.eq(ctr + 1))
        nl = build_netlist(f, ports=[
            ClockSignal("sync"),
            ResetSignal("sync"),
            ctr,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 'clk' 0.2) (input 'rst' 0.3) (output 'ctr' 4.0:4))
            (cell 0 0 (top (input 'clk' 2:3) (input 'rst' 3:4) (output 'ctr' 4.0:4)))
            (cell 1 0 (+ (cat 4.0:4 1'd0) 5'd1))
            (cell 2 0 (match 1 0.3 1))
            (cell 3 0 (assignment_list 1.0:4 (2.0 0:4 4'd0)))
            (cell 4 0 (flipflop 3.0:4 0 pos 0.2 0))
        )
        """)

    def test_port_autodomain(self):
        f = Fragment()
        ctr = Signal(4)
        f.add_statements("sync", ctr.eq(ctr + 1))
        nl = build_netlist(f, ports=[ctr])
        self.assertRepr(nl, """
        (
            (module 0 None ('top') (input 'clk' 0.2) (input 'rst' 0.3) (output 'ctr' 4.0:4))
            (cell 0 0 (top (input 'clk' 2:3) (input 'rst' 3:4) (output 'ctr' 4.0:4)))
            (cell 1 0 (+ (cat 4.0:4 1'd0) 5'd1))
            (cell 2 0 (match 1 0.3 1))
            (cell 3 0 (assignment_list 1.0:4 (2.0 0:4 4'd0)))
            (cell 4 0 (flipflop 3.0:4 0 pos 0.2 0))
        )
        """)

    def test_port_partial(self):
        f = Fragment()
        f1 = Fragment()
        f.add_subfragment(f1, "f1")
        a = Signal(4)
        b = Signal(4)
        c = Signal(3)
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

    def test_port_io(self):
        io = IOPort(8)
        f = Fragment()
        f1 = Fragment()
        f1.add_subfragment(Instance("t", i_io=io[:2]), "i")
        f.add_subfragment(f1, "f1")
        f2 = Fragment()
        f2.add_subfragment(Instance("t", o_io=io[2:4]), "i")
        f.add_subfragment(f2, "f2")
        f3 = Fragment()
        f3.add_subfragment(Instance("t", io_io=io[4:6]), "i")
        f.add_subfragment(f3, "f3")
        nl = build_netlist(f, ports=[])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (io inout 'io' 0.0:8)
            )
            (module 1 0 ('top' 'f1')
                (io input 'ioport$0$0' 0.0:2)
            )
            (module 2 0 ('top' 'f2')
                (io output 'ioport$0$2' 0.2:4)
            )
            (module 3 0 ('top' 'f3')
                (io inout 'ioport$0$4' 0.4:6)
            )
            (cell 0 0 (top))
            (cell 1 1 (instance 't' 'i' (io input 'io' 0.0:2)))
            (cell 2 2 (instance 't' 'i' (io output 'io' 0.2:4)))
            (cell 3 3 (instance 't' 'i' (io inout 'io' 0.4:6)))
        )
        """)

    def test_port_io_part(self):
        io = IOPort(4)
        f = Fragment()
        f1 = Fragment()
        f1.add_subfragment(Instance("t", i_i=io[0], o_o=io[1], io_io=io[2]), "i")
        f.add_subfragment(f1, "f1")
        nl = build_netlist(f, ports=[])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (io inout 'io' 0.0:4)
            )
            (module 1 0 ('top' 'f1')
                (io input 'ioport$0$0' 0.0)
                (io output 'ioport$0$1' 0.1)
                (io inout 'ioport$0$2' 0.2)
            )
            (cell 0 0 (top))
            (cell 1 1 (instance 't' 'i'
                 (io input 'i' 0.0)
                 (io output 'o' 0.1)
                 (io inout 'io' 0.2)
            ))
        )
        """)

    def test_port_instance(self):
        f = Fragment()
        f1 = Fragment()
        f.add_subfragment(f1, "f1")
        a = Signal(4)
        b = Signal(4)
        c = Signal(4)
        ioa = IOPort(4)
        iob = IOPort(4)
        ioc = IOPort(4)
        f1.add_subfragment(Instance("t",
            p_p = "meow",
            a_a = True,
            i_aa=a,
            o_bb=b,
            o_cc=c,
            i_aaa=ioa,
            o_bbb=iob,
            io_ccc=ioc,
        ), "i")
        nl = build_netlist(f, ports=[a, b, c])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'a' 0.2:6)
                (output 'b' 1.0:4)
                (output 'c' 1.4:8)
                (io input 'ioa' 0.0:4)
                (io output 'iob' 1.0:4)
                (io inout 'ioc' 2.0:4)
            )
            (module 1 0 ('top' 'f1')
                (input 'a' 0.2:6)
                (output 'b' 1.0:4)
                (output 'c' 1.4:8)
                (io input 'ioa' 0.0:4)
                (io output 'iob' 1.0:4)
                (io inout 'ioc' 2.0:4)
            )
            (cell 0 0 (top
                (input 'a' 2:6)
                (output 'b' 1.0:4)
                (output 'c' 1.4:8)
            ))
            (cell 1 1 (instance 't' 'i'
                (param 'p' 'meow')
                (attr 'a' True)
                (input 'aa' 0.2:6)
                (output 'bb' 0:4)
                (output 'cc' 4:8)
                (io input 'aaa' 0.0:4)
                (io output 'bbb' 1.0:4)
                (io inout 'ccc' 2.0:4)
            ))
        )
        """)

    def test_port_wrong(self):
        f = Fragment()
        a = Signal()
        with self.assertRaisesRegex(TypeError,
                r"^Only signals and IO ports may be added as ports, not \(const 1'd1\)$"):
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
        f.add_statements("b_sync", s.eq(1))

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
    def test_no_conflict_local_domains(self):
        f1 = Fragment()
        cd1 = ClockDomain("d")
        f1.add_domains(cd1)
        f1.add_statements("comb", ClockSignal("d").eq(1))
        f2 = Fragment()
        cd2 = ClockDomain("d")
        f2.add_domains(cd2)
        f2.add_statements("comb", ClockSignal("d").eq(1))
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
        io1 = IOPort(1)
        io2 = IOPort(1)
        io3 = IOPort(1)
        io4 = IOPort(1)
        io5 = IOPort(1)
        io6 = IOPort(1)
        inst = Instance("foo",
            ("a", "ATTR1", 1),
            ("p", "PARAM1", 0x1234),
            ("i", "s1", s1),
            ("o", "s2", s2),
            ("i", "io1", io1),
            ("o", "io2", io2),
            ("io", "io3", io3),
            a_ATTR2=2,
            p_PARAM2=0x5678,
            i_s3=s3,
            o_s4=s4,
            i_io4=io4,
            o_io5=io5,
            io_io6=io6,
        )
        self.assertEqual(inst.attrs, OrderedDict([
            ("ATTR1", 1),
            ("ATTR2", 2),
        ]))
        self.assertEqual(inst.parameters, OrderedDict([
            ("PARAM1", 0x1234),
            ("PARAM2", 0x5678),
        ]))
        self.assertEqual(inst.ports, OrderedDict([
            ("s1", (s1, "i")),
            ("s2", (s2, "o")),
            ("io1", (io1, "i")),
            ("io2", (io2, "o")),
            ("io3", (io3, "io")),
            ("s3", (s3, "i")),
            ("s4", (s4, "o")),
            ("io4", (io4, "i")),
            ("io5", (io5, "o")),
            ("io6", (io6, "io")),
        ]))

    def test_cast_ports(self):
        inst = Instance("foo",
            ("i", "s1", 1),
            ("io", "s2", Cat()),
            i_s3=3,
            io_s4=Cat(),
        )
        self.assertRepr(inst.ports["s1"][0], "(const 1'd1)")
        self.assertRepr(inst.ports["s2"][0], "(io-cat )")
        self.assertRepr(inst.ports["s3"][0], "(const 2'd3)")
        self.assertRepr(inst.ports["s4"][0], "(io-cat )")

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
        self.pins = IOPort(8)
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
        self.assertEqual(list(f.ports.keys()), ["clk", "rst", "stb", "data", "pins"])

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
        ioa = IOPort(5)
        iob = IOPort(6)
        ioc = IOPort(7)
        f.add_subfragment(Instance("gadget",
            i_i=i,
            o_o=o,
            i_ioa=ioa,
            o_iob=iob,
            io_ioc=ioc,
            p_param="TEST",
            a_attr=1234,
        ), "my_gadget")
        nl = build_netlist(f, [i, o])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i' 0.2:5)
                (output 'o' 1.0:4)
                (io input 'ioa' 0.0:5)
                (io output 'iob' 1.0:6)
                (io inout 'ioc' 2.0:7)
            )
            (cell 0 0 (top
                (input 'i' 2:5)
                (output 'o' 1.0:4)
            ))
            (cell 1 0 (instance 'gadget' 'my_gadget'
                (param 'param' 'TEST')
                (attr 'attr' 1234)
                (input 'i' 0.2:5)
                (output 'o' 0:4)
                (io input 'ioa' 0.0:5)
                (io output 'iob' 1.0:6)
                (io inout 'ioc' 2.0:7)
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

    def test_nir_io_slice(self):
        f = Fragment()
        io = IOPort(8)
        f.add_subfragment(Instance("test",
            i_i=io[:2],
            o_o=io[2:4],
            io_io=io[4:6],
        ), "t1")
        nl = build_netlist(f, [])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (io inout 'io' 0.0:8)
            )
            (cell 0 0 (top))
            (cell 1 0 (instance 'test' 't1'
                (io input 'i' 0.0:2)
                (io output 'o' 0.2:4)
                (io inout 'io' 0.4:6)
            ))
        )
        """)

    def test_nir_io_concat(self):
        f = Fragment()
        io1 = IOPort(4)
        io2 = IOPort(4)
        f.add_subfragment(Instance("test",
            io_io=Cat(io1, io2),
        ))
        nl = build_netlist(f, [io1, io2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (io inout 'io1' 0.0:4)
                (io inout 'io2' 1.0:4)
            )
            (cell 0 0 (top))
            (cell 1 0 (instance 'test' 'U$0'
                (io inout 'io' (io-cat 0.0:4 1.0:4))
            ))
        )
        """)

    def test_nir_operator(self):
        f = Fragment()
        i = Signal(3)
        o = Signal(4)
        f.add_subfragment(Instance("gadget",
            i_i=i.as_signed(),
            o_o=o.as_signed(),
        ), "my_gadget")
        nl = build_netlist(f, [i, o])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i' 0.2:5)
                (output 'o' 1.0:4)
            )
            (cell 0 0 (top
                (input 'i' 2:5)
                (output 'o' 1.0:4)
            ))
            (cell 1 0 (instance 'gadget' 'my_gadget'
                (input 'i' 0.2:5)
                (output 'o' 0:4)
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
        o4 = Signal(name="")
        i1 = Signal(name="i")

        f = Fragment()
        f.add_domains(cd_sync := ClockDomain())
        f.add_domains(cd_sync_norst := ClockDomain(reset_less=True))
        f.add_statements("comb", [o1.eq(0)])
        f.add_statements("sync", [o2.eq(i1)])
        f.add_statements("sync_norst", [o3.eq(i1)])

        ports = {
            "i": (i, PortDirection.Input),
            "rst": (rst, PortDirection.Input),
            "o1": (o1, PortDirection.Output),
            "o2": (o2, PortDirection.Output),
            "o3": (o3, PortDirection.Output),
            "o4": (o4, PortDirection.Output),
        }
        design = f.prepare(ports)
        self.assertEqual(design.fragments[design.fragment].signal_names, SignalDict([
            (i, "i"),
            (rst, "rst"),
            (o1, "o1"),
            (o2, "o2"),
            (o3, "o3"),
            # (o4, "o4"), # Signal has a private name.
            (cd_sync.clk, "clk"),
            (cd_sync.rst, "rst$7"),
            (cd_sync_norst.clk, "sync_norst_clk"),
            (i1, "i$8"),
        ]))

    def test_wrong_private_unnamed_toplevel_ports(self):
        s = Signal(name="")
        f = Fragment()
        with self.assertRaisesRegex(TypeError,
                r"^Signals with private names cannot be used in unnamed top-level ports$"):
            Design(f, ports=((None, s, None),), hierarchy=("top",))

    def test_assign_names_to_fragments(self):
        f = Fragment()
        f.add_subfragment(a := Fragment())
        f.add_subfragment(b := Fragment(), name="b")

        design = Design(f, ports=(), hierarchy=("top",))
        self.assertEqual(design.fragments[f].name, ("top",))
        self.assertEqual(design.fragments[a].name, ("top", "U$0"))
        self.assertEqual(design.fragments[b].name, ("top", "b"))

    def test_assign_names_to_fragments_rename_top(self):
        f = Fragment()
        f.add_subfragment(a := Fragment())
        f.add_subfragment(b := Fragment(), name="b")

        design = Design(f, ports=[], hierarchy=("bench", "cpu"))
        self.assertEqual(design.fragments[f].name, ("bench", "cpu",))
        self.assertEqual(design.fragments[a].name, ("bench", "cpu", "U$0"))
        self.assertEqual(design.fragments[b].name, ("bench", "cpu", "b"))

    def test_assign_names_to_fragments_collide_with_signal(self):
        f = Fragment()
        f.add_subfragment(a_f := Fragment(), name="a")
        a_s = Signal(name="a")

        design = Design(f, ports=[("a", a_s, None)], hierarchy=("top",))
        self.assertEqual(design.fragments[f].name, ("top",))
        self.assertEqual(design.fragments[a_f].name, ("top", "a$1"))

    def test_assign_names_to_fragments_duplicate(self):
        f = Fragment()
        f.add_subfragment(a1_f := Fragment(), name="a")
        f.add_subfragment(a2_f := Fragment(), name="a")

        design = Design(f, ports=[], hierarchy=("top",))
        self.assertEqual(design.fragments[f].name, ("top",))
        self.assertEqual(design.fragments[a1_f].name, ("top", "a"))
        self.assertEqual(design.fragments[a2_f].name, ("top", "a$1"))


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
        port = IOPort(4)
        i = Signal(4)
        f = Fragment()
        f.add_subfragment(IOBufferInstance(port, i=i))
        nl = build_netlist(f, ports=[i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'i' 1.0:4)
                (io input 'port' 0.0:4)
            )
            (cell 0 0 (top
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (iob input 0.0:4))
        )
        """)

    def test_nir_o(self):
        port = IOPort(4)
        o = Signal(4)
        f = Fragment()
        f.add_subfragment(IOBufferInstance(port, o=o))
        nl = build_netlist(f, ports=[o])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (io output 'port' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
            ))
            (cell 1 0 (iob output 0.0:4 0.2:6 1))
        )
        """)

    def test_nir_oe(self):
        port = IOPort(4)
        o = Signal(4)
        oe = Signal()
        f = Fragment()
        f.add_subfragment(IOBufferInstance(port, o=o, oe=oe))
        nl = build_netlist(f, ports=[ o, oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (io output 'port' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
            ))
            (cell 1 0 (iob output 0.0:4 0.2:6 0.6))
        )
        """)

    def test_nir_io(self):
        port = IOPort(4)
        i = Signal(4)
        o = Signal(4)
        oe = Signal()
        f = Fragment()
        f.add_subfragment(IOBufferInstance(port, i=i, o=o, oe=oe))
        nl = build_netlist(f, ports=[i, o, oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (output 'i' 1.0:4)
                (io inout 'port' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (iob inout 0.0:4 0.2:6 0.6))
        )
        """)

    def test_wrong_port(self):
        port = Signal(4)
        i = Signal(4)
        with self.assertRaisesRegex(TypeError,
                r"^Object \(sig port\) cannot be converted to an IO value"):
            IOBufferInstance(port, i=i)

    def test_wrong_i(self):
        port = IOPort(4)
        i = Signal()
        with self.assertRaisesRegex(ValueError,
                r"^'port' length \(4\) doesn't match 'i' length \(1\)"):
            IOBufferInstance(port, i=i)

    def test_wrong_o(self):
        port = IOPort(4)
        o = Signal()
        with self.assertRaisesRegex(ValueError,
                r"^'port' length \(4\) doesn't match 'o' length \(1\)"):
            IOBufferInstance(port, o=o)

    def test_wrong_oe(self):
        port = IOPort(4)
        o = Signal(4)
        oe = Signal(4)
        with self.assertRaisesRegex(ValueError,
                r"^'oe' length \(4\) must be 1"):
            IOBufferInstance(port, o=o, oe=oe)

    def test_wrong_oe_without_o(self):
        port = IOPort(4)
        oe = Signal()
        with self.assertRaisesRegex(ValueError,
                r"^'oe' must not be used if 'o' is not used"):
            IOBufferInstance(port, oe=oe)

    def test_conflict(self):
        port = IOPort(4)
        i1 = Signal(4)
        i2 = Signal(4)
        f = Fragment()
        f.add_subfragment(IOBufferInstance(port, i=i1))
        f.add_subfragment(IOBufferInstance(port, i=i2))
        with self.assertRaisesRegex(DriverConflict,
                r"^Bit 0 of I/O port \(io-port port\) used twice, at .*test_hdl_ir.py:\d+ and "
                r".*test_hdl_ir.py:\d+$"):
            build_netlist(f, ports=[i1, i2])


class AssignTestCase(FHDLTestCase):
    def test_simple(self):
        s1 = Signal(8)
        s2 = Signal(8)
        f = Fragment()
        f.add_statements(
            "comb",
            s1.eq(s2)
        )
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 2.0:8)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 2.0:8)
            ))
            (cell 1 0 (match 1 0.6:10 0000 0001 0010 0011 0100 0101 0110 0111))
            (cell 2 0 (assignment_list 8'd0
                (1.0 0:4 0.2:6)
                (1.1 1:5 0.2:6)
                (1.2 2:6 0.2:6)
                (1.3 3:7 0.2:6)
                (1.4 4:8 0.2:6)
                (1.5 5:8 0.2:5)
                (1.6 6:8 0.2:4)
                (1.7 7:8 0.2)
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:8)
                (output 's1' 2.0:8)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:8)
                (output 's1' 2.0:8)
            ))
            (cell 1 0 (match 1 0.6:8 00 01 10 11))
            (cell 2 0 (assignment_list 8'd0
                (1.0 0:4 0.2:6)
                (1.1 1:5 0.2:6)
                (1.2 2:6 0.2:6)
                (1.3 3:7 0.2:6)
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 2.0:16)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 2.0:16)
            ))
            (cell 1 0 (match 1 0.6:10 0000 0001 0010 0011))
            (cell 2 0 (assignment_list 16'd0
                (1.0 0:4 0.2:6)
                (1.1 4:8 0.2:6)
                (1.2 8:12 0.2:6)
                (1.3 12:16 0.2:6)
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 2.0:17)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 2.0:17)
            ))
            (cell 1 0 (match 1 0.6:10 0000 0001 0010 0011 0100))
            (cell 2 0 (assignment_list 17'd0
                (1.0 0:4 0.2:6)
                (1.1 4:8 0.2:6)
                (1.2 8:12 0.2:6)
                (1.3 12:16 0.2:6)
                (1.4 16:17 0.2)
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
        nl = build_netlist(f, ports=[s1, s2, s3, s4, s5])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's4' 0.2:10)
                (input 's5' 0.10:18)
                (output 's1' 2.0:8)
                (output 's2' 3.0:8)
                (output 's3' 4.0:8)
            )
            (cell 0 0 (top
                (input 's4' 2:10)
                (input 's5' 10:18)
                (output 's1' 2.0:8)
                (output 's2' 3.0:8)
                (output 's3' 4.0:8)
            ))
            (cell 1 0 (match 1 0.2:10 00000000 00000001 00000010))
            (cell 2 0 (assignment_list 8'd0 (1.0 0:8 0.10:18)))
            (cell 3 0 (assignment_list 8'd0 (1.1 0:8 0.10:18)))
            (cell 4 0 (assignment_list 8'd0 (1.2 0:8 0.10:18)))
        )
        """)

    def test_switchvalue(self):
        s1 = Signal(8)
        s2 = Signal(8)
        s3 = Signal(8)
        s4 = Signal(8)
        s5 = Signal(8)
        s6 = Signal(8)
        s7 = Signal(8)
        f = Fragment()
        f.add_statements("comb", [
            SwitchValue(s5[:4], [
                (1, s1),
                ((2, 3), s2),
                ((), s3),
                ('11--', s4),
            ]).eq(s6),
            SwitchValue(s5[4:], [
                (4, s1),
                (5, s2),
                (6, s3),
                (None, s4),
            ]).eq(s7),
        ])
        nl = build_netlist(f, ports=[s1, s2, s3, s4, s5, s6, s7])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's5' 0.2:10)
                (input 's6' 0.10:18)
                (input 's7' 0.18:26)
                (output 's1' 3.0:8)
                (output 's2' 4.0:8)
                (output 's3' 5.0:8)
                (output 's4' 6.0:8)
            )
            (cell 0 0 (top
                (input 's5' 2:10)
                (input 's6' 10:18)
                (input 's7' 18:26)
                (output 's1' 3.0:8)
                (output 's2' 4.0:8)
                (output 's3' 5.0:8)
                (output 's4' 6.0:8)
            ))
            (cell 1 0 (match 1 0.2:6 0001 {0010 0011} {} 11--))
            (cell 2 0 (match 1 0.6:10 0100 0101 0110 ----))
            (cell 3 0 (assignment_list 8'd0 (1.0 0:8 0.10:18) (2.0 0:8 0.18:26)))
            (cell 4 0 (assignment_list 8'd0 (1.1 0:8 0.10:18) (2.1 0:8 0.18:26)))
            (cell 5 0 (assignment_list 8'd0 (1.2 0:8 0.10:18) (2.2 0:8 0.18:26)))
            (cell 6 0 (assignment_list 8'd0 (1.3 0:8 0.10:18) (2.3 0:8 0.18:26)))
        )
        """)

    def test_mux_en(self):
        s1 = Signal(8)
        s2 = Signal(8)
        s3 = Signal(8)
        s4 = Signal(8)
        en = Signal()
        m = Module()
        with m.If(en):
            m.d.comb += Mux(s1, s2, s3).eq(s4)
        nl = build_netlist(Fragment.get(m, None), ports=[s1, s2, s3, s4, en])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's1' 0.2:10)
                (input 's4' 0.10:18)
                (input 'en' 0.18)
                (output 's2' 4.0:8)
                (output 's3' 3.0:8)
            )
            (cell 0 0 (top
                (input 's1' 2:10)
                (input 's4' 10:18)
                (input 'en' 18:19)
                (output 's2' 4.0:8)
                (output 's3' 3.0:8)
            ))
            (cell 1 0 (match 1 0.18 1))
            (cell 2 0 (match 1.0 0.2:10 00000000 --------))
            (cell 3 0 (assignment_list 8'd0 (2.0 0:8 0.10:18)))
            (cell 4 0 (assignment_list 8'd0 (2.1 0:8 0.10:18)))
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 2.0:8)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 2.0:8)
            ))
            (cell 1 0 (match 1 0.6:10 0000 0001 0010 0011 0100 0101 0110 0111))
            (cell 2 0 (assignment_list 8'd0
                (1.0 2:4 0.2:4)
                (1.1 3:5 0.2:4)
                (1.2 4:6 0.2:4)
                (1.3 5:7 0.2:4)
                (1.4 6:8 0.2:4)
                (1.5 7:8 0.2)
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 2.0:8)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 2.0:8)
            ))
            (cell 1 0 (match 1 0.6:10 0000 0001))
            (cell 2 0 (assignment_list 8'd0
                (1.0 1:3 0.2:4)
                (1.1 5:7 0.2:4)
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
        nl = build_netlist(f, ports=[s1, s2, s3, s4, s5])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's4' 0.2:10)
                (input 's5' 0.10:18)
                (output 's1' 2.0:8)
                (output 's2' 3.0:8)
                (output 's3' 4.0:8)
            )
            (cell 0 0 (top
                (input 's4' 2:10)
                (input 's5' 10:18)
                (output 's1' 2.0:8)
                (output 's2' 3.0:8)
                (output 's3' 4.0:8)
            ))
            (cell 1 0 (match 1 0.2:10 00000000 00000001 00000010))
            (cell 2 0 (assignment_list 8'd0 (1.0 2:7 0.10:15)))
            (cell 3 0 (assignment_list 8'd0 (1.1 2:7 0.10:15)))
            (cell 4 0 (assignment_list 8'd0 (1.2 2:7 0.10:15)))
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 2.0:8)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 2.0:8)
            ))
            (cell 1 0 (match 1 0.6:10 0000 0001 0010 0011 0100 0101))
            (cell 2 0 (assignment_list 8'd0
                (1.0 1:5 0.2:6)
                (1.1 2:6 0.2:6)
                (1.2 3:7 0.2:6)
                (1.3 4:7 0.2:5)
                (1.4 5:7 0.2:4)
                (1.5 6:7 0.2)
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
        nl = build_netlist(f, ports=[s1, s2, s3])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 's2' 0.2:6)
                (input 's3' 0.6:10)
                (output 's1' 2.0:12)
            )
            (cell 0 0 (top
                (input 's2' 2:6)
                (input 's3' 6:10)
                (output 's1' 2.0:12)
            ))
            (cell 1 0 (match 1 0.6:10 0000 0001 0010 0011 0100 0101))
            (cell 2 0 (assignment_list 12'd0
                (1.0 4:6 0.2:4)
                (1.1 5:7 0.2:4)
                (1.2 6:8 0.2:4)
                (1.3 7:9 0.2:4)
                (1.4 8:9 0.2)
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
                (output 'o1' (cat 2.0:8 2'd0))
                (output 'o2' (cat 4.0:9 4.8))
                (output 'o3' (cat 6.0:8 6.7 6.7))
                (output 'o4' (cat 8.0:8 8.7 8.7))
            )
            (cell 0 0 (top
                (input 'i8ua' 2:10)
                (input 'i8ub' 10:18)
                (input 'i8uc' 18:26)
                (input 'i8sa' 26:34)
                (input 'i8sb' 34:42)
                (input 'i8sc' 42:50)
                (input 'i4' 50:54)
                (output 'o1' (cat 2.0:8 2'd0))
                (output 'o2' (cat 4.0:9 4.8))
                (output 'o3' (cat 6.0:8 6.7 6.7))
                (output 'o4' (cat 8.0:8 8.7 8.7))
            ))
            (cell 1 0 (match 1 0.50:54 0000 0001 0010))
            (cell 2 0 (assignment_list 8'd0
                (1.0 0:8 0.2:10)
                (1.1 0:8 0.10:18)
                (1.2 0:8 0.18:26)
            ))
            (cell 3 0 (match 1 0.50:54 0000 0001 0010))
            (cell 4 0 (assignment_list 9'd0
                (3.0 0:9 (cat 0.2:10 1'd0))
                (3.1 0:9 (cat 0.10:18 1'd0))
                (3.2 0:9 (cat 0.42:50 0.49))
            ))
            (cell 5 0 (match 1 0.50:54 0000 0001 0010))
            (cell 6 0 (assignment_list 8'd0
                (5.0 0:8 0.26:34)
                (5.1 0:8 0.34:42)
                (5.2 0:8 0.42:50)
            ))
            (cell 7 0 (match 1 0.50:54 0000 0001 0010))
            (cell 8 0 (assignment_list 8'd0
                (7.0 0:8 0.26:34)
                (7.1 0:8 0.34:42)
                (7.2 0:8 (cat 0.50:54 4'd0))
            ))
        )
        """)

    def test_switchvalue(self):
        i8ua = Signal(8)
        i8ub = Signal(8)
        i8uc = Signal(8)
        i8ud = Signal(8)
        i4 = Signal(4)
        o1 = Signal(10)
        o2 = Signal(10)
        m = Module()
        m.d.comb += o1.eq(SwitchValue(i4, [
            (1, i8ua),
            ((2, 3), i8ub),
            ('11--', i8uc),
        ]))
        m.d.comb += o2.eq(SwitchValue(i4, [
            ((4, 5), i8ua),
            ((), i8ub),
            ((6, 7), i8uc),
            (None, i8ud),
        ]))
        nl = build_netlist(Fragment.get(m, None), [i8ua, i8ub, i8uc, i8ud, i4, o1, o2])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i8ua' 0.2:10)
                (input 'i8ub' 0.10:18)
                (input 'i8uc' 0.18:26)
                (input 'i8ud' 0.26:34)
                (input 'i4' 0.34:38)
                (output 'o1' (cat 2.0:8 2'd0))
                (output 'o2' (cat 4.0:8 2'd0))
            )
            (cell 0 0 (top
                (input 'i8ua' 2:10)
                (input 'i8ub' 10:18)
                (input 'i8uc' 18:26)
                (input 'i8ud' 26:34)
                (input 'i4' 34:38)
                (output 'o1' (cat 2.0:8 2'd0))
                (output 'o2' (cat 4.0:8 2'd0))
            ))
            (cell 1 0 (match 1 0.34:38 0001 {0010 0011} 11--))
            (cell 2 0 (assignment_list 8'd0
                (1.0 0:8 0.2:10)
                (1.1 0:8 0.10:18)
                (1.2 0:8 0.18:26)
            ))
            (cell 3 0 (match 1 0.34:38 {0100 0101} {} {0110 0111} ----))
            (cell 4 0 (assignment_list 8'd0
                (3.0 0:8 0.2:10)
                (3.1 0:8 0.10:18)
                (3.2 0:8 0.18:26)
                (3.3 0:8 0.26:34)
            ))
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
                (output 'o1' 5.0:8)
                (output 'o2' 6.0:8)
            )
            (cell 0 0 (top
                (input 'i' 2:6)
                (input 'i2' 6:10)
                (output 'o1' 5.0:8)
                (output 'o2' 6.0:8)
            ))
            (cell 1 0 (match 1 0.2:4 -1 1-))
            (cell 2 0 (match 1 0.4 1))
            (cell 3 0 (match 2.0 0.6:10 0001 {0010 0100} 11--))
            (cell 4 0 (match 3.2 0.5 1))
            (cell 5 0 (assignment_list 8'd0
                (1.0 0:8 8'd1)
                (1.1 2:4 2'd2)
                (4.0 0:8 8'd7)
            ))
            (cell 6 0 (assignment_list 8'd123
                (1.1 0:8 8'd3)
                (3.0 0:8 8'd4)
                (3.1 0:8 8'd5)
                (3.2 0:8 8'd6)
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
                (output 'o1' 3.0:8)
                (output 'o2' 6.0:8)
                (output 'o3' 8.0:8)
                (output 'o4' 10.0:8)
                (output 'o5' 12.0:8)
            )
            (cell 0 0 (top
                (input 'i1' 2:10)
                (input 'i2' 10:11)
                (input 'a_clk' 11:12)
                (input 'a_rst' 12:13)
                (input 'b_clk' 13:14)
                (input 'b_rst' 14:15)
                (input 'c_clk' 15:16)
                (output 'o1' 3.0:8)
                (output 'o2' 6.0:8)
                (output 'o3' 8.0:8)
                (output 'o4' 10.0:8)
                (output 'o5' 12.0:8)
            ))
            (cell 1 0 (match 1 0.10 1))
            (cell 2 0 (assignment_list 3.0:8 (1.0 0:8 0.2:10)))
            (cell 3 0 (flipflop 2.0:8 0 pos 0.11 0))
            (cell 4 0 (match 1 0.12 1))
            (cell 5 0 (assignment_list 6.0:8 (1.0 0:8 0.2:10) (4.0 0:8 8'd123)))
            (cell 6 0 (flipflop 5.0:8 123 pos 0.11 0))
            (cell 7 0 (assignment_list 8.0:8 (1.0 0:8 0.2:10)))
            (cell 8 0 (flipflop 7.0:8 45 pos 0.13 0))
            (cell 9 0 (assignment_list 10.0:8 (1.0 0:8 0.2:10)))
            (cell 10 0 (flipflop 9.0:8 67 pos 0.13 0.14))
            (cell 11 0 (assignment_list 12.0:8 (1.0 0:8 0.2:10)))
            (cell 12 0 (flipflop 11.0:8 89 neg 0.15 0))
        )
        """)

    def test_print(self):
        m = Module()
        a = Signal(6)
        b = Signal(signed(8))
        en = Signal()
        m.domains.a = ClockDomain()
        m.domains.b = ClockDomain(async_reset=True)
        m.domains.c = ClockDomain(reset_less=True, clk_edge="neg")
        with m.If(en):
            m.d.comb += Print(a, end="")
            m.d.comb += Print(b)
            m.d.a += Print(a, b)
            m.d.b += Print(Format("values: {:02x}, {:+d}", a, b))
            m.d.c += Print("meow")
        nl = build_netlist(Fragment.get(m, None), [
            a, b, en,
            ClockSignal("a"), ResetSignal("a"),
            ClockSignal("b"), ResetSignal("b"),
            ClockSignal("c"),
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'a' 0.2:8)
                (input 'b' 0.8:16)
                (input 'en' 0.16)
                (input 'a_clk' 0.17)
                (input 'a_rst' 0.18)
                (input 'b_clk' 0.19)
                (input 'b_rst' 0.20)
                (input 'c_clk' 0.21)
            )
            (cell 0 0 (top
                (input 'a' 2:8)
                (input 'b' 8:16)
                (input 'en' 16:17)
                (input 'a_clk' 17:18)
                (input 'a_rst' 18:19)
                (input 'b_clk' 19:20)
                (input 'b_rst' 20:21)
                (input 'c_clk' 21:22)
            ))
            (cell 1 0 (match 1 0.16 1))
            (cell 2 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 3 0 (print 2.0 ((u 0.2:8 ''))))
            (cell 4 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 5 0 (print 4.0 ((s 0.8:16 '') '\\n')))
            (cell 6 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 7 0 (print 6.0 pos 0.17 ((u 0.2:8 '') ' ' (s 0.8:16 '') '\\n')))
            (cell 8 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 9 0 (print 8.0 pos 0.19 ('values: ' (u 0.2:8 '02x') ', ' (s 0.8:16 '+d') '\\n')))
            (cell 10 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 11 0 (print 10.0 neg 0.21 ('meow\\n')))
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
            m.d.comb += Assume(i[1], "aaa")
            m.d.a += Assert(i[2])
            m.d.b += Assume(i[3], Format("value: {}", i))
            m.d.c += Cover(i[4], "c")
            m.d.comb += Cover(i, "d")
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
            (cell 1 0 (match 1 0.7 1))
            (cell 2 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 3 0 (assert 0.2 2.0 None))
            (cell 4 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 5 0 (assume 0.3 4.0 ('aaa')))
            (cell 6 0 (b 0.2:8))
            (cell 7 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 8 0 (cover 6.0 7.0 ('d')))
            (cell 9 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 10 0 (assert 0.4 9.0 pos 0.8 None))
            (cell 11 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 12 0 (assume 0.5 11.0 pos 0.10 ('value: ' (u 0.2:8 ''))))
            (cell 13 0 (assignment_list 1'd0 (1.0 0:1 1'd1)))
            (cell 14 0 (cover 0.6 13.0 neg 0.12 ('c')))
        )
        """)


class SplitDriverTestCase(FHDLTestCase):
    def test_split_domain(self):
        m = Module()
        o = Signal(10, init=0x123)
        i1 = Signal(2)
        i2 = Signal(2)
        i3 = Signal(2)
        i4 = Signal(2)
        cond = Signal()
        m.domains.a = ClockDomain()
        m.domains.b = ClockDomain()
        m.d.a += o[:2].eq(i1)
        m.d.b += o[2:4].eq(i2)
        with m.If(cond):
            m.d.a += o[4:6].eq(i3)
            m.d.comb += o[8:10].eq(i4)
        nl = build_netlist(Fragment.get(m, None), [
            o, i1, i2, i3, i4, cond,
            ClockSignal("a"), ResetSignal("a"),
            ClockSignal("b"), ResetSignal("b"),
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i1' 0.2:4)
                (input 'i2' 0.4:6)
                (input 'i3' 0.6:8)
                (input 'i4' 0.8:10)
                (input 'cond' 0.10)
                (input 'a_clk' 0.11)
                (input 'a_rst' 0.12)
                (input 'b_clk' 0.13)
                (input 'b_rst' 0.14)
                (output 'o' (cat 4.0:2 9.0:2 6.0:2 2'd0 10.0:2))
            )
            (cell 0 0 (top
                (input 'i1' 2:4)
                (input 'i2' 4:6)
                (input 'i3' 6:8)
                (input 'i4' 8:10)
                (input 'cond' 10:11)
                (input 'a_clk' 11:12)
                (input 'a_rst' 12:13)
                (input 'b_clk' 13:14)
                (input 'b_rst' 14:15)
                (output 'o' (cat 4.0:2 9.0:2 6.0:2 2'd0 10.0:2))
            ))
            (cell 1 0 (match 1 0.10 1))
            (cell 2 0 (match 1 0.12 1))
            (cell 3 0 (assignment_list 0.2:4 (2.0 0:2 2'd3)))
            (cell 4 0 (flipflop 3.0:2 3 pos 0.11 0))
            (cell 5 0 (assignment_list 6.0:2 (1.0 0:2 0.6:8) (2.0 0:2 2'd2)))
            (cell 6 0 (flipflop 5.0:2 2 pos 0.11 0))
            (cell 7 0 (match 1 0.14 1))
            (cell 8 0 (assignment_list 0.4:6 (7.0 0:2 2'd0)))
            (cell 9 0 (flipflop 8.0:2 0 pos 0.13 0))
            (cell 10 0 (assignment_list 2'd1 (1.0 0:2 0.8:10)))
        )
        """)

    def test_split_module(self):
        m = Module()
        m.submodules.m1 = m1 = Module()
        m.submodules.m2 = m2 = Module()

        i1 = Signal(4)
        i2 = Signal(4)
        i3 = Signal(2)
        cond = Signal()
        o = Signal(8)
        m1.d.comb += o[:4].eq(i1)
        m2.d.comb += o[4:].eq(i2)
        with m2.If(cond):
            m2.d.comb += o[5:7].eq(i3)

        nl = build_netlist(Fragment.get(m, None), [
            o, i1, i2, i3, cond,
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'i1' 0.2:6)
                (input 'i2' 0.6:10)
                (input 'i3' 0.10:12)
                (input 'cond' 0.12)
                (output 'o' (cat 0.2:6 2.0:4))
            )
            (module 1 0 ('top' 'm1')
                (input 'i1' 0.2:6)
                (input 'port$2$0' 2.0:4)
            )
            (module 2 0 ('top' 'm2')
                (input 'port$0$2' 0.2:6)
                (input 'i2' 0.6:10)
                (input 'i3' 0.10:12)
                (input 'cond' 0.12)
                (output 'port$2$0' 2.0:4)
            )
            (cell 0 0 (top
                (input 'i1' 2:6)
                (input 'i2' 6:10)
                (input 'i3' 10:12)
                (input 'cond' 12:13)
                (output 'o' (cat 0.2:6 2.0:4))
            ))
            (cell 1 2 (match 1 0.12 1))
            (cell 2 2 (assignment_list 0.6:10 (1.0 1:3 0.10:12)))
        )
        """)


class ConflictTestCase(FHDLTestCase):
    def test_domain_conflict(self):
        s = Signal()
        m = Module()
        m.d.sync += s.eq(1)
        m1 = Module()
        m1.d.comb += s.eq(2)
        m.submodules.m1 = m1
        with self.assertRaisesRegex(DriverConflict,
                r"^Signal \(sig s\) bit 0 driven from domain comb at "
                r".*test_hdl_ir.py:\d+ and domain sync at "
                r".*test_hdl_ir.py:\d+$"):
            build_netlist(Fragment.get(m, None), [])

    def test_module_conflict(self):
        s = Signal()
        m = Module()
        m.d.sync += s.eq(1)
        m1 = Module()
        m1.d.sync += s.eq(2)
        m.submodules.m1 = m1
        with self.assertRaisesRegex(DriverConflict,
                r"^Signal \(sig s\) bit 0 driven from module top\.m1 at "
                r".*test_hdl_ir.py:\d+ and module top at "
                r".*test_hdl_ir.py:\d+$"):
            build_netlist(Fragment.get(m, None), [])

    def test_instance_conflict(self):
        s = Signal()
        m = Module()
        m.d.sync += s.eq(1)
        m.submodules.t = Instance("tt", o_s=s)
        with self.assertRaisesRegex(DriverConflict,
                r"^Bit 0 of signal \(sig s\) has multiple drivers: "
                r".*test_hdl_ir.py:\d+ and .*test_hdl_ir.py:\d+$"):
            build_netlist(Fragment.get(m, None), [])


class UndrivenTestCase(FHDLTestCase):
    def test_undriven(self):
        o = Signal(8)
        m = Module()
        nl = build_netlist(Fragment.get(m, None), [
            ("o", o, PortDirection.Output),
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o' 8'd0)
            )
            (cell 0 0 (top
                (output 'o' 8'd0)
            ))
        )
        """)

    def test_undef_to_ff(self):
        o = Signal(8, init=0x55)
        m = Module()
        nl = build_netlist(Fragment.get(m, None), [
            ("o", o, PortDirection.Output),
        ], all_undef_to_ff=True)
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o' 1.0:8)
            )
            (cell 0 0 (top
                (output 'o' 1.0:8)
            ))
            (cell 1 0 (flipflop 1.0:8 85 pos 0 0))
        )
        """)

    def test_undef_to_ff_partial(self):
        o = Signal(8, init=0x55)
        m = Module()
        m.submodules.inst = Instance("t", o_o=o[2])
        nl = build_netlist(Fragment.get(m, None), [
            ("o", o, PortDirection.Output),
        ], all_undef_to_ff=True)
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'o' (cat 2.0:2 1.0 3.0:5))
            )
            (cell 0 0 (top
                (output 'o' (cat 2.0:2 1.0 3.0:5))
            ))
            (cell 1 0 (instance 't' 'inst' (output 'o' 0:1)))
            (cell 2 0 (flipflop 2.0:2 1 pos 0 0))
            (cell 3 0 (flipflop 3.0:5 10 pos 0 0))
        )
        """)


class FieldsTestCase(FHDLTestCase):
    def test_fields(self):
        class MyEnum(enum.Enum, shape=unsigned(2)):
            A = 0
            B = 1
            C = 2
        l = data.StructLayout({"a": MyEnum, "b": signed(3)})
        s1 = Signal(l)
        s2 = Signal(MyEnum)
        s3 = Signal(signed(3))
        s4 = Signal(unsigned(4))
        nl = build_netlist(Fragment.get(Module(), None), [
            s1.as_value(), s2.as_value(), s3, s4,
        ])
        self.assertEqual(nl.signal_fields[s1.as_value()], {
            (): SignalField(nl.signals[s1.as_value()], signed=False),
            ('a',): SignalField(nl.signals[s1.as_value()][0:2], signed=False, enum_name=MyEnum.__qualname__, enum_variants={
                0: "A",
                1: "B",
                2: "C",
            }),
            ('b',): SignalField(nl.signals[s1.as_value()][2:5], signed=True)
        })
        self.assertEqual(nl.signal_fields[s2.as_value()], {
            (): SignalField(nl.signals[s2.as_value()], signed=False, enum_name=MyEnum.__qualname__, enum_variants={
                0: "A",
                1: "B",
                2: "C",
            }),
        })
        self.assertEqual(nl.signal_fields[s3], {
            (): SignalField(nl.signals[s3], signed=True),
        })
        self.assertEqual(nl.signal_fields[s4], {
            (): SignalField(nl.signals[s4], signed=False),
        })


class CycleTestCase(FHDLTestCase):
    def test_cycle(self):
        a = Signal()
        b = Signal()
        m = Module()
        m.d.comb += [
            a.eq(~b),
            b.eq(~a),
        ]
        with self.assertRaisesRegex(CombinationalCycle,
                r"^Combinational cycle detected, path:\n"
                r".*test_hdl_ir.py:\d+: operator ~ bit 0\n"
                r".*test_hdl_ir.py:\d+: signal b bit 0\n"
                r".*test_hdl_ir.py:\d+: operator ~ bit 0\n"
                r".*test_hdl_ir.py:\d+: signal a bit 0\n"
                r"$"):
            build_netlist(Fragment.get(m, None), [])

    def test_assignment_cycle(self):
        a = Signal(2)
        m = Module()

        with m.If(a[0]):
            m.d.comb += a[0].eq(1)

        with self.assertRaisesRegex(CombinationalCycle,
                r"^Combinational cycle detected, path:\n"
                r".*test_hdl_ir.py:\d+: cell Match bit 0\n"
                r".*test_hdl_ir.py:\d+: signal a bit 0\n"
                r".*test_hdl_ir.py:\d+: cell AssignmentList bit 0\n"
                r"$"):
            build_netlist(Fragment.get(m, None), [])

        m = Module()

        with m.If(a[0]):
            m.d.comb += a[1].eq(1)

        # no cycle here, a[1] gets assigned and a[0] gets checked
        build_netlist(Fragment.get(m, None), [])


class DomainLookupTestCase(FHDLTestCase):
    def test_domain_lookup(self):
        m1 = Module()
        m1_a = m1.domains.a = ClockDomain("a")
        m1_b = m1.domains.b = ClockDomain("b")
        m1_c = m1.domains.c = ClockDomain("c")
        m2 = Module()
        m3 = Module()
        m3.d.sync += Print("m3")
        m4 = Module()
        m4.d.sync += Print("m4")
        m4_d = m4.domains.d = ClockDomain("d")
        m5 = Module()
        m5.d.sync += Print("m5")
        m5_d = m5.domains.d = ClockDomain("d")

        m1.submodules.m2 = xm2 = DomainRenamer({"a": "b"})(m2)
        m2.submodules.m3 = xm3 = DomainRenamer("a")(m3)
        m2.submodules.m4 = xm4 = DomainRenamer("b")(m4)
        m2.submodules.m5 = xm5 = DomainRenamer("c")(m5)

        design = Fragment.get(m1, None).prepare()

        self.assertIs(design.lookup_domain("a", m1), m1_a)
        self.assertIs(design.lookup_domain("b", m1), m1_b)
        self.assertIs(design.lookup_domain("c", m1), m1_c)
        self.assertIs(design.lookup_domain("a", xm2), m1_b)
        self.assertIs(design.lookup_domain("b", xm2), m1_b)
        self.assertIs(design.lookup_domain("c", xm2), m1_c)
        self.assertIs(design.lookup_domain("sync", xm3), m1_b)
        self.assertIs(design.lookup_domain("sync", xm4), m1_b)
        self.assertIs(design.lookup_domain("sync", xm5), m1_c)
        self.assertIs(design.lookup_domain("d", xm4), m4_d)
        self.assertIs(design.lookup_domain("d", xm5), m5_d)


class RequirePosedgeTestCase(FHDLTestCase):
    def test_require_ok(self):
        m = Module()
        m.domains.sync = ClockDomain()
        m.submodules += RequirePosedge("sync")
        Fragment.get(m, None).prepare()

    def test_require_fail(self):
        m = Module()
        m.domains.sync = ClockDomain(clk_edge="neg")
        m.submodules += RequirePosedge("sync")
        with self.assertRaisesRegex(DomainRequirementFailed,
                r"^Domain sync has a negedge clock, but posedge clock is required by top.U\$0 at .*$"):
            Fragment.get(m, None).prepare()

    def test_require_renamed(self):
        m = Module()
        m.domains.sync = ClockDomain(clk_edge="pos")
        m.domains.test = ClockDomain(clk_edge="neg")
        m.submodules += DomainRenamer("test")(RequirePosedge("sync"))
        with self.assertRaisesRegex(DomainRequirementFailed,
                r"^Domain test has a negedge clock, but posedge clock is required by top.U\$0 at .*$"):
            Fragment.get(m, None).prepare()
