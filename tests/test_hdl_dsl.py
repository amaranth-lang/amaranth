# amaranth: UnusedElaboratable=no

from collections import OrderedDict
from enum import Enum

from amaranth.hdl.ast import *
from amaranth.hdl.cd import *
from amaranth.hdl.dsl import *

from .utils import *


class DSLTestCase(FHDLTestCase):
    def setUp(self):
        self.s1 = Signal()
        self.s2 = Signal()
        self.s3 = Signal()
        self.c1 = Signal()
        self.c2 = Signal()
        self.c3 = Signal()
        self.w1 = Signal(4)

    def test_cant_inherit(self):
        with self.assertRaisesRegex(SyntaxError,
                (r"^Instead of inheriting from `Module`, inherit from `Elaboratable` and "
                    r"return a `Module` from the `elaborate\(self, platform\)` method$")):
            class ORGate(Module):
                pass

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
        with self.assertRaisesRegex(SyntaxError,
                (r"^Driver-driver conflict: trying to drive \(sig c1\) from d\.sync, but it "
                    r"is already driven from d\.comb$")):
            m.d.comb += self.c1.eq(1)
            m.d.sync += self.c1.eq(1)

    def test_d_wrong(self):
        m = Module()
        with self.assertRaisesRegex(AttributeError,
                r"^Cannot assign 'd\.pix' attribute; did you mean 'd.pix \+='\?$"):
            m.d.pix = None

    def test_d_asgn_wrong(self):
        m = Module()
        with self.assertRaisesRegex(SyntaxError,
                r"^Only assignments and property checks may be appended to d\.sync$"):
            m.d.sync += Switch(self.s1, {})

    def test_comb_wrong(self):
        m = Module()
        with self.assertRaisesRegex(AttributeError,
                r"^'Module' object has no attribute 'comb'; did you mean 'd\.comb'\?$"):
            m.comb += self.c1.eq(1)

    def test_sync_wrong(self):
        m = Module()
        with self.assertRaisesRegex(AttributeError,
                r"^'Module' object has no attribute 'sync'; did you mean 'd\.sync'\?$"):
            m.sync += self.c1.eq(1)

    def test_attr_wrong(self):
        m = Module()
        with self.assertRaisesRegex(AttributeError,
                r"^'Module' object has no attribute 'nonexistentattr'$"):
            m.nonexistentattr

    def test_d_suspicious(self):
        m = Module()
        with self.assertWarnsRegex(SyntaxWarning,
                (r"^Using '<module>\.d\.submodules' would add statements to clock domain "
                    r"'submodules'; did you mean <module>\.submodules instead\?$")):
            m.d.submodules += []

    def test_clock_signal(self):
        m = Module()
        m.d.comb += ClockSignal("pix").eq(ClockSignal())
        self.assertRepr(m._statements, """
        (
            (eq (clk pix) (clk sync))
        )
        """)

    def test_reset_signal(self):
        m = Module()
        m.d.comb += ResetSignal("pix").eq(1)
        self.assertRepr(m._statements, """
        (
            (eq (rst pix) (const 1'd1))
        )
        """)

    def test_sample_domain(self):
        m = Module()
        i = Signal()
        o1 = Signal()
        o2 = Signal()
        o3 = Signal()
        m.d.sync += o1.eq(Past(i))
        m.d.pix  += o2.eq(Past(i))
        m.d.pix  += o3.eq(Past(i, domain="sync"))
        f = m.elaborate(platform=None)
        self.assertRepr(f.statements, """
        (
            (eq (sig o1) (sample (sig i) @ sync[1]))
            (eq (sig o2) (sample (sig i) @ pix[1]))
            (eq (sig o3) (sample (sig i) @ sync[1]))
        )
        """)

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
                (case 1- (eq (sig c2) (const 1'd0)))
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
                (case 1- (eq (sig c2) (const 1'd0)))
                (default (eq (sig c3) (const 1'd1)))
            )
        )
        """)

    def test_If_If(self):
        m = Module()
        with m.If(self.s1):
            m.d.comb += self.c1.eq(1)
        with m.If(self.s2):
            m.d.comb += self.c2.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (cat (sig s1))
                (case 1 (eq (sig c1) (const 1'd1)))
            )
            (switch (cat (sig s2))
                (case 1 (eq (sig c2) (const 1'd1)))
            )
        )
        """)

    def test_If_nested_If(self):
        m = Module()
        with m.If(self.s1):
            m.d.comb += self.c1.eq(1)
            with m.If(self.s2):
                m.d.comb += self.c2.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (cat (sig s1))
                (case 1 (eq (sig c1) (const 1'd1))
                    (switch (cat (sig s2))
                        (case 1 (eq (sig c2) (const 1'd1)))
                    )
                )
            )
        )
        """)

    def test_If_dangling_Else(self):
        m = Module()
        with m.If(self.s1):
            m.d.comb += self.c1.eq(1)
            with m.If(self.s2):
                m.d.comb += self.c2.eq(1)
        with m.Else():
            m.d.comb += self.c3.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (cat (sig s1))
                (case 1
                    (eq (sig c1) (const 1'd1))
                    (switch (cat (sig s2))
                        (case 1 (eq (sig c2) (const 1'd1)))
                    )
                )
                (default
                    (eq (sig c3) (const 1'd1))
                )
            )
        )
        """)

    def test_Elif_wrong(self):
        m = Module()
        with self.assertRaisesRegex(SyntaxError,
                r"^Elif without preceding If$"):
            with m.Elif(self.s2):
                pass

    def test_Elif_wrong_nested(self):
        m = Module()
        with m.If(self.s1):
            with self.assertRaisesRegex(SyntaxError,
                    r"^Elif without preceding If$"):
                with m.Elif(self.s2):
                    pass

    def test_Else_wrong(self):
        m = Module()
        with self.assertRaisesRegex(SyntaxError,
                r"^Else without preceding If\/Elif$"):
            with m.Else():
                pass

    def test_Else_wrong_nested(self):
        m = Module()
        with m.If(self.s1):
            with self.assertRaisesRegex(SyntaxError,
                    r"^Else without preceding If/Elif$"):
                with m.Else():
                    pass

    def test_Elif_Elif_wrong_nested(self):
        m = Module()
        with m.If(self.s1):
            pass
        with m.Elif(self.s2):
            with self.assertRaisesRegex(SyntaxError,
                    r"^Elif without preceding If$"):
                with m.Elif(self.s3):
                    pass

    def test_Else_Else_wrong_nested(self):
        m = Module()
        with m.If(self.s1):
            pass
        with m.Else():
            with self.assertRaisesRegex(SyntaxError,
                    r"^Else without preceding If/Elif$"):
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

    def test_If_signed_suspicious(self):
        m = Module()
        with self.assertWarnsRegex(SyntaxWarning,
                (r"^Signed values in If\/Elif conditions usually result from inverting Python "
                    r"booleans with ~, which leads to unexpected results\. Replace `~flag` with "
                    r"`not flag`\. \(If this is a false positive, silence this warning with "
                    r"`m\.If\(x\)` → `m\.If\(x\.bool\(\)\)`\.\)$")):
            with m.If(~True):
                pass

    def test_Elif_signed_suspicious(self):
        m = Module()
        with m.If(0):
            pass
        with self.assertWarnsRegex(SyntaxWarning,
                (r"^Signed values in If\/Elif conditions usually result from inverting Python "
                    r"booleans with ~, which leads to unexpected results\. Replace `~flag` with "
                    r"`not flag`\. \(If this is a false positive, silence this warning with "
                    r"`m\.If\(x\)` → `m\.If\(x\.bool\(\)\)`\.\)$")):
            with m.Elif(~True):
                pass

    def test_if_If_Elif_Else(self):
        m = Module()
        with self.assertRaisesRegex(SyntaxError,
                r"^`if m\.If\(\.\.\.\):` does not work; use `with m\.If\(\.\.\.\)`$"):
            if m.If(0):
                pass
        with m.If(0):
            pass
        with self.assertRaisesRegex(SyntaxError,
                r"^`if m\.Elif\(\.\.\.\):` does not work; use `with m\.Elif\(\.\.\.\)`$"):
            if m.Elif(0):
                pass
        with self.assertRaisesRegex(SyntaxError,
                r"^`if m\.Else\(\.\.\.\):` does not work; use `with m\.Else\(\.\.\.\)`$"):
            if m.Else():
                pass

    def test_Switch(self):
        m = Module()
        with m.Switch(self.w1):
            with m.Case(3):
                m.d.comb += self.c1.eq(1)
            with m.Case("11--"):
                m.d.comb += self.c2.eq(1)
            with m.Case("1 0--"):
                m.d.comb += self.c2.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (sig w1)
                (case 0011 (eq (sig c1) (const 1'd1)))
                (case 11-- (eq (sig c2) (const 1'd1)))
                (case 10-- (eq (sig c2) (const 1'd1)))
            )
        )
        """)

    def test_Switch_default_Case(self):
        m = Module()
        with m.Switch(self.w1):
            with m.Case(3):
                m.d.comb += self.c1.eq(1)
            with m.Case():
                m.d.comb += self.c2.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (sig w1)
                (case 0011 (eq (sig c1) (const 1'd1)))
                (default (eq (sig c2) (const 1'd1)))
            )
        )
        """)

    def test_Switch_default_Default(self):
        m = Module()
        with m.Switch(self.w1):
            with m.Case(3):
                m.d.comb += self.c1.eq(1)
            with m.Default():
                m.d.comb += self.c2.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (sig w1)
                (case 0011 (eq (sig c1) (const 1'd1)))
                (default (eq (sig c2) (const 1'd1)))
            )
        )
        """)

    def test_Switch_const_test(self):
        m = Module()
        with m.Switch(1):
            with m.Case(1):
                m.d.comb += self.c1.eq(1)
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (const 1'd1)
                (case 1 (eq (sig c1) (const 1'd1)))
            )
        )
        """)

    def test_Switch_enum(self):
        class Color(Enum):
            RED  = 1
            BLUE = 2
        m = Module()
        se = Signal(Color)
        with m.Switch(se):
            with m.Case(Color.RED):
                m.d.comb += self.c1.eq(1)
        self.assertRepr(m._statements, """
        (
            (switch (sig se)
                (case 01 (eq (sig c1) (const 1'd1)))
            )
        )
        """)

    def test_Case_width_wrong(self):
        class Color(Enum):
            RED = 0b10101010
        m = Module()
        with m.Switch(self.w1):
            with self.assertRaisesRegex(SyntaxError,
                    r"^Case pattern '--' must have the same width as switch value \(which is 4\)$"):
                with m.Case("--"):
                    pass
            with self.assertWarnsRegex(SyntaxWarning,
                    (r"^Case pattern '10110' is wider than switch value \(which has width 4\); "
                        r"comparison will never be true$")):
                with m.Case(0b10110):
                    pass
            with self.assertWarnsRegex(SyntaxWarning,
                    (r"^Case pattern '10101010' \(Color\.RED\) is wider than switch value "
                        r"\(which has width 4\); comparison will never be true$")):
                with m.Case(Color.RED):
                    pass
        self.assertRepr(m._statements, """
        (
            (switch (sig w1) )
        )
        """)

    def test_Case_bits_wrong(self):
        m = Module()
        with m.Switch(self.w1):
            with self.assertRaisesRegex(SyntaxError,
                    (r"^Case pattern 'abc' must consist of 0, 1, and - \(don't care\) bits, "
                        r"and may include whitespace$")):
                with m.Case("abc"):
                    pass

    def test_Case_pattern_wrong(self):
        m = Module()
        with m.Switch(self.w1):
            with self.assertRaisesRegex(SyntaxError,
                    r"^Case pattern must be an integer, a string, or an enumeration, not 1\.0$"):
                with m.Case(1.0):
                    pass

    def test_Case_outside_Switch_wrong(self):
        m = Module()
        with self.assertRaisesRegex(SyntaxError,
                r"^Case is not permitted outside of Switch$"):
            with m.Case():
                pass

    def test_If_inside_Switch_wrong(self):
        m = Module()
        with m.Switch(self.s1):
            with self.assertRaisesRegex(SyntaxError,
                    (r"^If is not permitted directly inside of Switch; "
                        r"it is permitted inside of Switch Case$")):
                with m.If(self.s2):
                    pass

    def test_Case_wrong_nested(self):
        m = Module()
        with m.Switch(self.s1):
            with m.Case(0):
                with self.assertRaisesRegex(SyntaxError,
                    r"^Case is not permitted outside of Switch$"):
                    with m.Case(1):
                        pass

    def test_FSM_basic(self):
        a = Signal()
        b = Signal()
        c = Signal()
        m = Module()
        with m.FSM():
            with m.State("FIRST"):
                m.d.comb += a.eq(1)
                m.next = "SECOND"
            with m.State("SECOND"):
                m.d.sync += b.eq(~b)
                with m.If(c):
                    m.next = "FIRST"
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (sig fsm_state)
                (case 0
                    (eq (sig a) (const 1'd1))
                    (eq (sig fsm_state) (const 1'd1))
                )
                (case 1
                    (eq (sig b) (~ (sig b)))
                    (switch (cat (sig c))
                        (case 1
                            (eq (sig fsm_state) (const 1'd0)))
                    )
                )
            )
        )
        """)
        self.assertEqual({repr(k): v for k, v in m._driving.items()}, {
            "(sig a)": None,
            "(sig fsm_state)": "sync",
            "(sig b)": "sync",
        })

        frag = m.elaborate(platform=None)
        fsm  = frag.find_generated("fsm")
        self.assertIsInstance(fsm.state, Signal)
        self.assertEqual(fsm.encoding, OrderedDict({
            "FIRST": 0,
            "SECOND": 1,
        }))
        self.assertEqual(fsm.decoding, OrderedDict({
            0: "FIRST",
            1: "SECOND"
        }))

    def test_FSM_reset(self):
        a = Signal()
        m = Module()
        with m.FSM(reset="SECOND"):
            with m.State("FIRST"):
                m.d.comb += a.eq(0)
                m.next = "SECOND"
            with m.State("SECOND"):
                m.next = "FIRST"
        m._flush()
        self.assertRepr(m._statements, """
        (
            (switch (sig fsm_state)
                (case 0
                    (eq (sig a) (const 1'd0))
                    (eq (sig fsm_state) (const 1'd1))
                )
                (case 1
                    (eq (sig fsm_state) (const 1'd0))
                )
            )
        )
        """)

    def test_FSM_ongoing(self):
        a = Signal()
        b = Signal()
        m = Module()
        with m.FSM() as fsm:
            m.d.comb += b.eq(fsm.ongoing("SECOND"))
            with m.State("FIRST"):
                pass
            m.d.comb += a.eq(fsm.ongoing("FIRST"))
            with m.State("SECOND"):
                pass
        m._flush()
        self.assertEqual(m._generated["fsm"].state.reset, 1)
        self.maxDiff = 10000
        self.assertRepr(m._statements, """
        (
            (eq (sig b) (== (sig fsm_state) (const 1'd0)))
            (eq (sig a) (== (sig fsm_state) (const 1'd1)))
            (switch (sig fsm_state)
                (case 1
                )
                (case 0
                )
            )
        )
        """)

    def test_FSM_empty(self):
        m = Module()
        with m.FSM():
            pass
        self.assertRepr(m._statements, """
        ()
        """)

    def test_FSM_wrong_domain(self):
        m = Module()
        with self.assertRaisesRegex(ValueError,
                r"^FSM may not be driven by the 'comb' domain$"):
            with m.FSM(domain="comb"):
                pass

    def test_FSM_wrong_undefined(self):
        m = Module()
        with self.assertRaisesRegex(NameError,
                r"^FSM state 'FOO' is referenced but not defined$"):
            with m.FSM() as fsm:
                fsm.ongoing("FOO")

    def test_FSM_wrong_redefined(self):
        m = Module()
        with m.FSM():
            with m.State("FOO"):
                pass
            with self.assertRaisesRegex(NameError,
                    r"^FSM state 'FOO' is already defined$"):
                with m.State("FOO"):
                    pass

    def test_FSM_wrong_next(self):
        m = Module()
        with self.assertRaisesRegex(SyntaxError,
                r"^Only assignment to `m\.next` is permitted$"):
            m.next
        with self.assertRaisesRegex(SyntaxError,
                r"^`m\.next = <\.\.\.>` is only permitted inside an FSM state$"):
            m.next = "FOO"
        with self.assertRaisesRegex(SyntaxError,
                r"^`m\.next = <\.\.\.>` is only permitted inside an FSM state$"):
            with m.FSM():
                m.next = "FOO"

    def test_If_inside_FSM_wrong(self):
        m = Module()
        with m.FSM():
            with m.State("FOO"):
                pass
            with self.assertRaisesRegex(SyntaxError,
                    (r"^If is not permitted directly inside of FSM; "
                        r"it is permitted inside of FSM State$")):
                with m.If(self.s2):
                    pass

    def test_State_outside_FSM_wrong(self):
        m = Module()
        with self.assertRaisesRegex(SyntaxError,
            r"^FSM State is not permitted outside of FSM"):
            with m.State("FOO"):
                pass


    def test_FSM_State_wrong_nested(self):
        m = Module()
        with m.FSM():
            with m.State("FOO"):
                with self.assertRaisesRegex(SyntaxError,
                    r"^FSM State is not permitted outside of FSM"):
                    with m.State("BAR"):
                        pass

    def test_auto_pop_ctrl(self):
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

    def test_submodule_anon(self):
        m1 = Module()
        m2 = Module()
        m1.submodules += m2
        self.assertEqual(m1._anon_submodules, [m2])
        self.assertEqual(m1._named_submodules, {})

    def test_submodule_anon_multi(self):
        m1 = Module()
        m2 = Module()
        m3 = Module()
        m1.submodules += m2, m3
        self.assertEqual(m1._anon_submodules, [m2, m3])
        self.assertEqual(m1._named_submodules, {})

    def test_submodule_named(self):
        m1 = Module()
        m2 = Module()
        m1.submodules.foo = m2
        self.assertEqual(m1._anon_submodules, [])
        self.assertEqual(m1._named_submodules, {"foo": m2})

    def test_submodule_named_index(self):
        m1 = Module()
        m2 = Module()
        m1.submodules["foo"] = m2
        self.assertEqual(m1._anon_submodules, [])
        self.assertEqual(m1._named_submodules, {"foo": m2})

    def test_submodule_wrong(self):
        m = Module()
        with self.assertRaisesRegex(TypeError,
                r"^Trying to add 1, which does not implement \.elaborate\(\), as a submodule$"):
            m.submodules.foo = 1
        with self.assertRaisesRegex(TypeError,
                r"^Trying to add 1, which does not implement \.elaborate\(\), as a submodule$"):
            m.submodules += 1

    def test_submodule_named_conflict(self):
        m1 = Module()
        m2 = Module()
        m1.submodules.foo = m2
        with self.assertRaisesRegex(NameError, r"^Submodule named 'foo' already exists$"):
            m1.submodules.foo = m2

    def test_submodule_get(self):
        m1 = Module()
        m2 = Module()
        m1.submodules.foo = m2
        m3 = m1.submodules.foo
        self.assertEqual(m2, m3)

    def test_submodule_get_index(self):
        m1 = Module()
        m2 = Module()
        m1.submodules["foo"] = m2
        m3 = m1.submodules["foo"]
        self.assertEqual(m2, m3)

    def test_submodule_get_unset(self):
        m1 = Module()
        with self.assertRaisesRegex(AttributeError, r"^No submodule named 'foo' exists$"):
            m2 = m1.submodules.foo
        with self.assertRaisesRegex(AttributeError, r"^No submodule named 'foo' exists$"):
            m2 = m1.submodules["foo"]

    def test_domain_named_implicit(self):
        m = Module()
        m.domains += ClockDomain("sync")
        self.assertEqual(len(m._domains), 1)

    def test_domain_named_explicit(self):
        m = Module()
        m.domains.foo = ClockDomain()
        self.assertEqual(len(m._domains), 1)
        self.assertEqual(m._domains["foo"].name, "foo")

    def test_domain_add_wrong(self):
        m = Module()
        with self.assertRaisesRegex(TypeError,
                r"^Only clock domains may be added to `m\.domains`, not 1$"):
            m.domains.foo = 1
        with self.assertRaisesRegex(TypeError,
                r"^Only clock domains may be added to `m\.domains`, not 1$"):
            m.domains += 1

    def test_domain_add_wrong_name(self):
        m = Module()
        with self.assertRaisesRegex(NameError,
                r"^Clock domain name 'bar' must match name in `m\.domains\.foo \+= \.\.\.` syntax$"):
            m.domains.foo = ClockDomain("bar")

    def test_domain_add_wrong_duplicate(self):
        m = Module()
        m.domains += ClockDomain("foo")
        with self.assertRaisesRegex(NameError,
                r"^Clock domain named 'foo' already exists$"):
            m.domains += ClockDomain("foo")

    def test_lower(self):
        m1 = Module()
        m1.d.comb += self.c1.eq(self.s1)
        m2 = Module()
        m2.d.comb += self.c2.eq(self.s2)
        m2.d.sync += self.c3.eq(self.s3)
        m1.submodules.foo = m2

        f1 = m1.elaborate(platform=None)
        self.assertRepr(f1.statements, """
        (
            (eq (sig c1) (sig s1))
        )
        """)
        self.assertEqual(f1.drivers, {
            None: SignalSet((self.c1,))
        })
        self.assertEqual(len(f1.subfragments), 1)
        (f2, f2_name), = f1.subfragments
        self.assertEqual(f2_name, "foo")
        self.assertRepr(f2.statements, """
        (
            (eq (sig c2) (sig s2))
            (eq (sig c3) (sig s3))
        )
        """)
        self.assertEqual(f2.drivers, {
            None: SignalSet((self.c2,)),
            "sync": SignalSet((self.c3,))
        })
        self.assertEqual(len(f2.subfragments), 0)
