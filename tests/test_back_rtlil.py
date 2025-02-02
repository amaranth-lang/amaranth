import operator
import re

from amaranth.back import rtlil
from amaranth.hdl import *
from amaranth.hdl._ast import *
from amaranth.lib import memory, wiring, data, enum

from .utils import *

class RTLILTestCase(FHDLTestCase):
    maxDiff = 10000

    def assertRTLIL(self, fragment, ports, rtlil_gold):
        rtlil_test = rtlil.convert(fragment, ports=ports, emit_src=False)
        def normalize(s):
            s = s.strip()
            s = re.sub(r" +", " ", s)
            s = re.sub(r"\n ", "\n", s)
            s = re.sub(r"\n+", "\n", s)
            return s + "\n"
        self.assertEqual(normalize(rtlil_test), normalize(rtlil_gold))

class TreeTestCase(RTLILTestCase):
    def test_tree(self):
        a = Signal()
        b = Signal()
        c = Signal()
        m = Module()
        m.submodules.m1 = m1 = Module()
        m.submodules.m2 = m2 = Module()
        m.submodules.m3 = m3 = Module()
        m3.submodules.m4 = m4 = Module()
        m1.d.comb += a.eq(~b)
        m2.d.comb += b.eq(~c)
        self.assertRTLIL(m, [a, c], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 1 \b
            wire width 1 input 0 \c
            wire width 1 output 1 \a
            cell \top.m1 \m1
                connect \a \a [0]
                connect \b \b [0]
            end
            cell \top.m2 \m2
                connect \c \c [0]
                connect \b \b [0]
            end
        end
        attribute \generator "Amaranth"
        module \top.m1
            wire width 1 output 0 \a
            wire width 1 input 1 \b
            cell $not $1
                parameter \A_SIGNED 0
                parameter \A_WIDTH 1
                parameter \Y_WIDTH 1
                connect \A \b [0]
                connect \Y \a
            end
        end
        attribute \generator "Amaranth"
        module \top.m2
            wire width 1 input 0 \c
            wire width 1 output 1 \b
            cell $not $1
                parameter \A_SIGNED 0
                parameter \A_WIDTH 1
                parameter \Y_WIDTH 1
                connect \A \c [0]
                connect \Y \b
            end
        end
        """)


class RHSTestCase(RTLILTestCase):
    def test_operator_unary(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        o1 = Signal(10)
        o2 = Signal(10)
        o3 = Signal(10)
        o4 = Signal(10)
        o5 = Signal(10)
        o6 = Signal(10)
        o7 = Signal(10)
        o8 = Signal(10)
        m = Module()
        m.d.comb += [
            o1.eq(-i8u),
            o2.eq(-i8s),
            o3.eq(~i8u),
            o4.eq(~i8s),
            o5.eq(i8u.bool()),
            o6.eq(i8u.all()),
            o7.eq(i8u.any()),
            o8.eq(i8u.xor()),
        ]
        self.assertRTLIL(m, [i8u, i8s, o1, o2, o3, o4, o5, o6, o7, o8], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8u
            wire width 8 input 1 signed \i8s
            wire width 10 output 2 \o1
            wire width 10 output 3 \o2
            wire width 10 output 4 \o3
            wire width 10 output 5 \o4
            wire width 10 output 6 \o5
            wire width 10 output 7 \o6
            wire width 10 output 8 \o7
            wire width 10 output 9 \o8
            wire width 9 $1
            wire width 9 $2
            wire width 8 $3
            wire width 8 $4
            wire width 1 $5
            wire width 1 $6
            wire width 1 $7
            wire width 1 $8
            cell $neg $9
                parameter \A_SIGNED 0
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A \i8u [7:0]
                connect \Y $1
            end
            cell $neg $10
                parameter \A_SIGNED 1
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A \i8s [7:0]
                connect \Y $2
            end
            cell $not $11
                parameter \A_SIGNED 0
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 8
                connect \A \i8u [7:0]
                connect \Y $3
            end
            cell $not $12
                parameter \A_SIGNED 0
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 8
                connect \A \i8s [7:0]
                connect \Y $4
            end
            cell $reduce_bool $13
                parameter \A_SIGNED 0
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 1
                connect \A \i8u [7:0]
                connect \Y $5
            end
            cell $reduce_and $14
                parameter \A_SIGNED 0
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 1
                connect \A \i8u [7:0]
                connect \Y $6
            end
            cell $reduce_or $15
                parameter \A_SIGNED 0
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 1
                connect \A \i8u [7:0]
                connect \Y $7
            end
            cell $reduce_xor $16
                parameter \A_SIGNED 0
                parameter \A_WIDTH 8
                parameter \Y_WIDTH 1
                connect \A \i8u [7:0]
                connect \Y $8
            end
            connect \o1 { $1 [8] $1 [8:0] }
            connect \o2 { $2 [8] $2 [8:0] }
            connect \o3 { 2'00 $3 [7:0] }
            connect \o4 { $4 [7] $4 [7] $4 [7:0] }
            connect \o5 { 9'000000000 $5 [0] }
            connect \o6 { 9'000000000 $6 [0] }
            connect \o7 { 9'000000000 $7 [0] }
            connect \o8 { 9'000000000 $8 [0] }
        end
        """)

    def test_operator_addsub(self):
        i8ua = Signal(8)
        i8ub = Signal(8)
        i8sa = Signal(signed(8))
        i8sb = Signal(signed(8))
        o1 = Signal(10)
        o2 = Signal(10)
        o3 = Signal(10)
        o4 = Signal(10)
        o5 = Signal(10)
        o6 = Signal(10)
        m = Module()
        m.d.comb += [
            o1.eq(i8ua + i8ub),
            o2.eq(i8ua + i8sb),
            o3.eq(i8sa + i8sb),
            o4.eq(i8ua - i8ub),
            o5.eq(i8ua - i8sb),
            o6.eq(i8sa - i8sb),
        ]
        self.assertRTLIL(m, [i8ua, i8ub, i8sa, i8sb, o1, o2, o3, o4, o5, o6], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8ua
            wire width 8 input 1 \i8ub
            wire width 8 input 2 signed \i8sa
            wire width 8 input 3 signed \i8sb
            wire width 10 output 4 \o1
            wire width 10 output 5 \o2
            wire width 10 output 6 \o3
            wire width 10 output 7 \o4
            wire width 10 output 8 \o5
            wire width 10 output 9 \o6
            wire width 9 $1
            wire width 9 $2
            wire width 9 $3
            wire width 9 $4
            cell $add $5
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A \i8ua [7:0]
                connect \B \i8ub [7:0]
                connect \Y $1
            end
            cell $add $6
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 9
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 10
                connect \A { 1'0 \i8ua [7:0] }
                connect \B \i8sb [7:0]
                connect \Y \o2
            end
            cell $add $7
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 8
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A \i8sa [7:0]
                connect \B \i8sb [7:0]
                connect \Y $2
            end
            cell $sub $8
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A \i8ua [7:0]
                connect \B \i8ub [7:0]
                connect \Y $3
            end
            cell $sub $9
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 9
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 10
                connect \A { 1'0 \i8ua [7:0] }
                connect \B \i8sb [7:0]
                connect \Y \o5
            end
            cell $sub $10
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 8
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A \i8sa [7:0]
                connect \B \i8sb [7:0]
                connect \Y $4
            end
            connect \o1 { 1'0 $1 [8:0] }
            connect \o3 { $2 [8] $2 [8:0] }
            connect \o4 { $3 [8] $3 [8:0] }
            connect \o6 { $4 [8] $4 [8:0] }
        end
        """)

    def test_operator_add_imm(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        o1 = Signal(10)
        o2 = Signal(10)
        o3 = Signal(10)
        o4 = Signal(10)
        m = Module()
        m.d.comb += [
            o1.eq(i8u + 3),
            o2.eq(i8s + 3),
            o3.eq(3 + i8u),
            o4.eq(3 + i8s),
        ]
        self.assertRTLIL(m, [i8u, i8s, o1, o2, o3, o4], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8u
            wire width 8 input 1 signed \i8s
            wire width 10 output 2 \o1
            wire width 10 output 3 \o2
            wire width 10 output 4 \o3
            wire width 10 output 5 \o4
            wire width 9 $1
            wire width 9 $2
            wire width 9 $3
            wire width 9 $4
            cell $add $5
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 2
                parameter \Y_WIDTH 9
                connect \A \i8u [7:0]
                connect \B 2'11
                connect \Y $1
            end
            cell $add $6
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 8
                parameter \B_WIDTH 3
                parameter \Y_WIDTH 9
                connect \A \i8s [7:0]
                connect \B 3'011
                connect \Y $2
            end
            cell $add $7
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 2
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A 2'11
                connect \B \i8u [7:0]
                connect \Y $3
            end
            cell $add $8
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 3
                parameter \B_WIDTH 8
                parameter \Y_WIDTH 9
                connect \A 3'011
                connect \B \i8s [7:0]
                connect \Y $4
            end
            connect \o1 { 1'0 $1 [8:0] }
            connect \o2 { $2 [8] $2 [8:0] }
            connect \o3 { 1'0 $3 [8:0] }
            connect \o4 { $4 [8] $4 [8:0] }
        end
        """)


    def test_operator_mul(self):
        i4ua = Signal(4)
        i4ub = Signal(4)
        i4sa = Signal(signed(4))
        i4sb = Signal(signed(4))
        o1 = Signal(9)
        o2 = Signal(9)
        o3 = Signal(9)
        m = Module()
        m.d.comb += [
            o1.eq(i4ua * i4ub),
            o2.eq(i4ua * i4sb),
            o3.eq(i4sa * i4sb),
        ]
        self.assertRTLIL(m, [i4ua, i4ub, i4sa, i4sb, o1, o2, o3], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 4 input 0 \i4ua
            wire width 4 input 1 \i4ub
            wire width 4 input 2 signed \i4sa
            wire width 4 input 3 signed \i4sb
            wire width 9 output 4 \o1
            wire width 9 output 5 \o2
            wire width 9 output 6 \o3
            wire width 8 $1
            wire width 8 $2
            wire width 8 $3
            cell $mul $4
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 4
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 8
                connect \A \i4ua [3:0]
                connect \B \i4ub [3:0]
                connect \Y $1
            end
            cell $mul $5
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 5
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 8
                connect \A { 1'0 \i4ua [3:0] }
                connect \B \i4sb [3:0]
                connect \Y $2
            end
            cell $mul $6
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 4
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 8
                connect \A \i4sa [3:0]
                connect \B \i4sb [3:0]
                connect \Y $3
            end
            connect \o1 { 1'0 $1 [7:0] }
            connect \o2 { $2 [7] $2 [7:0] }
            connect \o3 { $3 [7] $3 [7:0] }
        end
        """)

    def test_operator_divmod(self):
        i4ua = Signal(4)
        i4ub = Signal(4)
        i4sa = Signal(signed(4))
        i4sb = Signal(signed(4))
        o1 = Signal(6)
        o2 = Signal(6)
        o3 = Signal(6)
        o4 = Signal(6)
        o5 = Signal(6)
        o6 = Signal(6)
        o7 = Signal(6)
        o8 = Signal(6)
        m = Module()
        m.d.comb += [
            o1.eq(i4ua // i4ub),
            o2.eq(i4ua // i4sb),
            o3.eq(i4sa // i4ub),
            o4.eq(i4sa // i4sb),
            o5.eq(i4ua % i4ub),
            o6.eq(i4ua % i4sb),
            o7.eq(i4sa % i4ub),
            o8.eq(i4sa % i4sb),
        ]
        self.assertRTLIL(m, [i4ua, i4ub, i4sa, i4sb, o1, o2, o3, o4, o5, o6, o7, o8], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 4 input 0 \i4ua
            wire width 4 input 1 \i4ub
            wire width 4 input 2 signed \i4sa
            wire width 4 input 3 signed \i4sb
            wire width 6 output 4 \o1
            wire width 6 output 5 \o2
            wire width 6 output 6 \o3
            wire width 6 output 7 \o4
            wire width 6 output 8 \o5
            wire width 6 output 9 \o6
            wire width 6 output 10 \o7
            wire width 6 output 11 \o8
            wire width 4 $1
            wire width 5 $2
            wire width 5 $3
            wire width 5 $4
            wire width 4 $5
            wire width 5 $6
            wire width 5 $7
            wire width 4 $8

            wire width 4 $9
            cell $divfloor $10
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 4
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 4
                connect \A \i4ua [3:0]
                connect \B \i4ub [3:0]
                connect \Y $9
            end
            wire width 1 $11
            cell $reduce_bool $12
                parameter \A_SIGNED 0
                parameter \A_WIDTH 4
                parameter \Y_WIDTH 1
                connect \A \i4ub [3:0]
                connect \Y $11
            end
            cell $mux $13
                parameter \WIDTH 4
                connect \S $11
                connect \A 4'0000
                connect \B $9
                connect \Y $1
            end

            wire width 5 $14
            cell $divfloor $15
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 5
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 5
                connect \A { 1'0 \i4ua [3:0] }
                connect \B \i4sb [3:0]
                connect \Y $14
            end
            wire width 1 $16
            cell $reduce_bool $17
                parameter \A_SIGNED 0
                parameter \A_WIDTH 4
                parameter \Y_WIDTH 1
                connect \A \i4sb [3:0]
                connect \Y $16
            end
            cell $mux $18
                parameter \WIDTH 5
                connect \S $16
                connect \A 5'00000
                connect \B $14
                connect \Y $2
            end

            wire width 5 $19
            cell $divfloor $20
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 4
                parameter \B_WIDTH 5
                parameter \Y_WIDTH 5
                connect \A \i4sa [3:0]
                connect \B { 1'0 \i4ub [3:0] }
                connect \Y $19
            end
            wire width 1 $21
            cell $reduce_bool $22
                parameter \A_SIGNED 0
                parameter \A_WIDTH 5
                parameter \Y_WIDTH 1
                connect \A { 1'0 \i4ub [3:0] }
                connect \Y $21
            end
            cell $mux $23
                parameter \WIDTH 5
                connect \S $21
                connect \A 5'00000
                connect \B $19
                connect \Y $3
            end

            wire width 5 $24
            cell $divfloor $25
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 4
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 5
                connect \A \i4sa [3:0]
                connect \B \i4sb [3:0]
                connect \Y $24
            end
            wire width 1 $26
            cell $reduce_bool $27
                parameter \A_SIGNED 0
                parameter \A_WIDTH 4
                parameter \Y_WIDTH 1
                connect \A \i4sb [3:0]
                connect \Y $26
            end
            cell $mux $28
                parameter \WIDTH 5
                connect \S $26
                connect \A 5'00000
                connect \B $24
                connect \Y $4
            end

            wire width 4 $29
            cell $modfloor $30
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 4
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 4
                connect \A \i4ua [3:0]
                connect \B \i4ub [3:0]
                connect \Y $29
            end
            wire width 1 $31
            cell $reduce_bool $32
                parameter \A_SIGNED 0
                parameter \A_WIDTH 4
                parameter \Y_WIDTH 1
                connect \A \i4ub [3:0]
                connect \Y $31
            end
            cell $mux $33
                parameter \WIDTH 4
                connect \S $31
                connect \A 4'0000
                connect \B $29
                connect \Y $5
            end

            wire width 5 $34
            cell $modfloor $35
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 5
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 5
                connect \A { 1'0 \i4ua [3:0] }
                connect \B \i4sb [3:0]
                connect \Y $34
            end
            wire width 1 $36
            cell $reduce_bool $37
                parameter \A_SIGNED 0
                parameter \A_WIDTH 4
                parameter \Y_WIDTH 1
                connect \A \i4sb [3:0]
                connect \Y $36
            end
            cell $mux $38
                parameter \WIDTH 5
                connect \S $36
                connect \A 5'00000
                connect \B $34
                connect \Y $6
            end

            wire width 5 $39
            cell $modfloor $40
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 4
                parameter \B_WIDTH 5
                parameter \Y_WIDTH 5
                connect \A \i4sa [3:0]
                connect \B { 1'0 \i4ub [3:0] }
                connect \Y $39
            end
            wire width 1 $41
            cell $reduce_bool $42
                parameter \A_SIGNED 0
                parameter \A_WIDTH 5
                parameter \Y_WIDTH 1
                connect \A { 1'0 \i4ub [3:0] }
                connect \Y $41
            end
            cell $mux $43
                parameter \WIDTH 5
                connect \S $41
                connect \A 5'00000
                connect \B $39
                connect \Y $7
            end

            wire width 4 $44
            cell $modfloor $45
                parameter \A_SIGNED 1
                parameter \B_SIGNED 1
                parameter \A_WIDTH 4
                parameter \B_WIDTH 4
                parameter \Y_WIDTH 4
                connect \A \i4sa [3:0]
                connect \B \i4sb [3:0]
                connect \Y $44
            end
            wire width 1 $46
            cell $reduce_bool $47
                parameter \A_SIGNED 0
                parameter \A_WIDTH 4
                parameter \Y_WIDTH 1
                connect \A \i4sb [3:0]
                connect \Y $46
            end
            cell $mux $48
                parameter \WIDTH 4
                connect \S $46
                connect \A 4'0000
                connect \B $44
                connect \Y $8
            end

            connect \o1 { 2'00 $1 [3:0] }
            connect \o2 { $2 [4] $2 [4:0] }
            connect \o3 { $3 [3] $3 [3] $3 [3:0] }
            connect \o4 { $4 [4] $4 [4:0] }
            connect \o5 { 2'00 $5 [3:0] }
            connect \o6 { $6 [3] $6 [3] $6 [3:0] }
            connect \o7 { 2'00 $7 [3:0] }
            connect \o8 { $8 [3] $8 [3] $8 [3:0] }
        end
        """)

    def test_operator_shift(self):
        i8ua = Signal(8)
        i8sa = Signal(signed(8))
        i3 = Signal(3)
        o1 = Signal(16)
        o2 = Signal(16)
        o3 = Signal(16)
        o4 = Signal(16)
        m = Module()
        m.d.comb += [
            o1.eq(i8ua << i3),
            o2.eq(i8sa << i3),
            o3.eq(i8ua >> i3),
            o4.eq(i8sa >> i3),
        ]
        self.assertRTLIL(m, [i8ua, i8sa, i3, o1, o2, o3, o4], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8ua
            wire width 8 input 1 signed \i8sa
            wire width 3 input 2 \i3
            wire width 16 output 3 \o1
            wire width 16 output 4 \o2
            wire width 16 output 5 \o3
            wire width 16 output 6 \o4
            wire width 15 $1
            wire width 15 $2
            wire width 8 $3
            wire width 8 $4
            cell $shl $5
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 3
                parameter \Y_WIDTH 15
                connect \A \i8ua [7:0]
                connect \B \i3 [2:0]
                connect \Y $1
            end
            cell $shl $6
                parameter \A_SIGNED 1
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 3
                parameter \Y_WIDTH 15
                connect \A \i8sa [7:0]
                connect \B \i3 [2:0]
                connect \Y $2
            end
            cell $shr $7
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 3
                parameter \Y_WIDTH 8
                connect \A \i8ua [7:0]
                connect \B \i3 [2:0]
                connect \Y $3
            end
            cell $sshr $8
                parameter \A_SIGNED 1
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 3
                parameter \Y_WIDTH 8
                connect \A \i8sa [7:0]
                connect \B \i3 [2:0]
                connect \Y $4
            end
            connect \o1 { 1'0 $1 [14:0] }
            connect \o2 { $2 [14] $2 [14:0] }
            connect \o3 { 8'00000000 $3 [7:0] }
            connect \o4 { $4 [7] $4 [7] $4 [7] $4 [7] $4 [7] $4 [7] $4 [7] $4 [7] $4 [7:0] }
        end
        """)

    def test_operator_bitwise(self):
        for (name, op) in [
            ("and", operator.__and__),
            ("or", operator.__or__),
            ("xor", operator.__xor__),
        ]:
            i8ua = Signal(8)
            i8ub = Signal(8)
            i8sa = Signal(signed(8))
            i8sb = Signal(signed(8))
            o1 = Signal(10)
            o2 = Signal(10)
            o3 = Signal(10)
            m = Module()
            m.d.comb += [
                o1.eq(op(i8ua, i8ub)),
                o2.eq(op(i8ua, i8sb)),
                o3.eq(op(i8sa, i8sb)),
            ]
            self.assertRTLIL(m, [i8ua, i8ub, i8sa, i8sb, o1, o2, o3], R"""
            attribute \generator "Amaranth"
            attribute \top 1
            module \top
                wire width 8 input 0 \i8ua
                wire width 8 input 1 \i8ub
                wire width 8 input 2 signed \i8sa
                wire width 8 input 3 signed \i8sb
                wire width 10 output 4 \o1
                wire width 10 output 5 \o2
                wire width 10 output 6 \o3
                wire width 8 $1
                wire width 9 $2
                wire width 8 $3
                cell $bitop $4
                    parameter \A_SIGNED 0
                    parameter \B_SIGNED 0
                    parameter \A_WIDTH 8
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 8
                    connect \A \i8ua [7:0]
                    connect \B \i8ub [7:0]
                    connect \Y $1
                end
                cell $bitop $5
                    parameter \A_SIGNED 0
                    parameter \B_SIGNED 0
                    parameter \A_WIDTH 9
                    parameter \B_WIDTH 9
                    parameter \Y_WIDTH 9
                    connect \A { 1'0 \i8ua [7:0] }
                    connect \B { \i8sb [7] \i8sb [7:0] }
                    connect \Y $2
                end
                cell $bitop $6
                    parameter \A_SIGNED 0
                    parameter \B_SIGNED 0
                    parameter \A_WIDTH 8
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 8
                    connect \A \i8sa [7:0]
                    connect \B \i8sb [7:0]
                    connect \Y $3
                end
                connect \o1 { 2'00 $1 [7:0] }
                connect \o2 { $2 [8] $2 [8:0] }
                connect \o3 { $3 [7] $3 [7] $3 [7:0] }
            end
            """.replace("bitop", name))

    def test_operator_eq(self):
        for (name, op) in [
            ("eq", operator.__eq__),
            ("ne", operator.__ne__),
        ]:
            i8ua = Signal(8)
            i8ub = Signal(8)
            i8sa = Signal(signed(8))
            i8sb = Signal(signed(8))
            o1 = Signal(2)
            o2 = Signal(2)
            o3 = Signal(2)
            m = Module()
            m.d.comb += [
                o1.eq(op(i8ua, i8ub)),
                o2.eq(op(i8ua, i8sb)),
                o3.eq(op(i8sa, i8sb)),
            ]
            self.assertRTLIL(m, [i8ua, i8ub, i8sa, i8sb, o1, o2, o3], R"""
            attribute \generator "Amaranth"
            attribute \top 1
            module \top
                wire width 8 input 0 \i8ua
                wire width 8 input 1 \i8ub
                wire width 8 input 2 signed \i8sa
                wire width 8 input 3 signed \i8sb
                wire width 2 output 4 \o1
                wire width 2 output 5 \o2
                wire width 2 output 6 \o3
                wire width 1 $1
                wire width 1 $2
                wire width 1 $3
                cell $eqop $4
                    parameter \A_SIGNED 0
                    parameter \B_SIGNED 0
                    parameter \A_WIDTH 8
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 1
                    connect \A \i8ua [7:0]
                    connect \B \i8ub [7:0]
                    connect \Y $1
                end
                cell $eqop $5
                    parameter \A_SIGNED 1
                    parameter \B_SIGNED 1
                    parameter \A_WIDTH 9
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 1
                    connect \A { 1'0 \i8ua [7:0] }
                    connect \B \i8sb [7:0]
                    connect \Y $2
                end
                cell $eqop $6
                    parameter \A_SIGNED 0
                    parameter \B_SIGNED 0
                    parameter \A_WIDTH 8
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 1
                    connect \A \i8sa [7:0]
                    connect \B \i8sb [7:0]
                    connect \Y $3
                end
                connect \o1 { 1'0 $1 [0] }
                connect \o2 { 1'0 $2 [0] }
                connect \o3 { 1'0 $3 [0] }
            end
            """.replace("eqop", name))

    def test_operator_cmp(self):
        for (name, op) in [
            ("lt", operator.__lt__),
            ("le", operator.__le__),
            ("gt", operator.__gt__),
            ("ge", operator.__ge__),
        ]:
            i8ua = Signal(8)
            i8ub = Signal(8)
            i8sa = Signal(signed(8))
            i8sb = Signal(signed(8))
            o1 = Signal(2)
            o2 = Signal(2)
            o3 = Signal(2)
            m = Module()
            m.d.comb += [
                o1.eq(op(i8ua, i8ub)),
                o2.eq(op(i8ua, i8sb)),
                o3.eq(op(i8sa, i8sb)),
            ]
            self.assertRTLIL(m, [i8ua, i8ub, i8sa, i8sb, o1, o2, o3], R"""
            attribute \generator "Amaranth"
            attribute \top 1
            module \top
                wire width 8 input 0 \i8ua
                wire width 8 input 1 \i8ub
                wire width 8 input 2 signed \i8sa
                wire width 8 input 3 signed \i8sb
                wire width 2 output 4 \o1
                wire width 2 output 5 \o2
                wire width 2 output 6 \o3
                wire width 1 $1
                wire width 1 $2
                wire width 1 $3
                cell $cmpop $4
                    parameter \A_SIGNED 0
                    parameter \B_SIGNED 0
                    parameter \A_WIDTH 8
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 1
                    connect \A \i8ua [7:0]
                    connect \B \i8ub [7:0]
                    connect \Y $1
                end
                cell $cmpop $5
                    parameter \A_SIGNED 1
                    parameter \B_SIGNED 1
                    parameter \A_WIDTH 9
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 1
                    connect \A { 1'0 \i8ua [7:0] }
                    connect \B \i8sb [7:0]
                    connect \Y $2
                end
                cell $cmpop $6
                    parameter \A_SIGNED 1
                    parameter \B_SIGNED 1
                    parameter \A_WIDTH 8
                    parameter \B_WIDTH 8
                    parameter \Y_WIDTH 1
                    connect \A \i8sa [7:0]
                    connect \B \i8sb [7:0]
                    connect \Y $3
                end
                connect \o1 { 1'0 $1 [0] }
                connect \o2 { 1'0 $2 [0] }
                connect \o3 { 1'0 $3 [0] }
            end
            """.replace("cmpop", name))

    def test_operator_mux(self):
        i8ua = Signal(8)
        i8ub = Signal(8)
        i8sa = Signal(signed(8))
        i8sb = Signal(signed(8))
        i1 = Signal()
        o1 = Signal(10)
        o2 = Signal(10)
        o3 = Signal(10)
        m = Module()
        m.d.comb += [
            o1.eq(Mux(i1, i8ua, i8ub)),
            o2.eq(Mux(i1, i8ua, i8sb)),
            o3.eq(Mux(i1, i8sa, i8sb)),
        ]
        self.assertRTLIL(m, [i8ua, i8ub, i8sa, i8sb, i1, o1, o2, o3], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8ua
            wire width 8 input 1 \i8ub
            wire width 8 input 2 signed \i8sa
            wire width 8 input 3 signed \i8sb
            wire width 1 input 4 \i1
            wire width 10 output 5 \o1
            wire width 10 output 6 \o2
            wire width 10 output 7 \o3
            wire width 8 $1
            wire width 9 $2
            wire width 8 $3
            cell $mux $4
                parameter \WIDTH 8
                connect \S \i1 [0]
                connect \A \i8ub [7:0]
                connect \B \i8ua [7:0]
                connect \Y $1
            end
            cell $mux $5
                parameter \WIDTH 9
                connect \S \i1 [0]
                connect \A { \i8sb [7] \i8sb [7:0] }
                connect \B { 1'0 \i8ua [7:0] }
                connect \Y $2
            end
            cell $mux $6
                parameter \WIDTH 8
                connect \S \i1 [0]
                connect \A \i8sb [7:0]
                connect \B \i8sa [7:0]
                connect \Y $3
            end
            connect \o1 { 2'00 $1 [7:0] }
            connect \o2 { $2 [8] $2 [8:0] }
            connect \o3 { $3 [7] $3 [7] $3 [7:0] }
        end
        """)

    def test_part(self):
        i8ua = Signal(8)
        i8sa = Signal(signed(8))
        i3 = Signal(3)
        o1 = Signal(4)
        o2 = Signal(4)
        o3 = Signal(4)
        o4 = Signal(4)
        m = Module()
        m.d.comb += [
            o1.eq(i8ua.bit_select(i3, width=3)),
            o2.eq(i8sa.bit_select(i3, width=3)),
            o3.eq(i8ua.word_select(i3, width=3)),
            o4.eq(i8sa.word_select(i3, width=3)),
        ]
        self.assertRTLIL(m, [i8ua, i8sa, i3, o1, o2, o3, o4], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8ua
            wire width 8 input 1 signed \i8sa
            wire width 3 input 2 \i3
            wire width 4 output 3 \o1
            wire width 4 output 4 \o2
            wire width 4 output 5 \o3
            wire width 4 output 6 \o4
            wire width 3 $1
            wire width 3 $2
            wire width 3 $3
            wire width 3 $4
            cell $shift $5
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 3
                parameter \Y_WIDTH 3
                connect \A \i8ua [7:0]
                connect \B \i3 [2:0]
                connect \Y $1
            end
            cell $shift $6
                parameter \A_SIGNED 1
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 3
                parameter \Y_WIDTH 3
                connect \A \i8sa [7:0]
                connect \B \i3 [2:0]
                connect \Y $2
            end
            wire width 5 $7
            cell $mul $8
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 3
                parameter \B_WIDTH 2
                parameter \Y_WIDTH 5
                connect \A \i3 [2:0]
                connect \B 2'11
                connect \Y $7
            end
            cell $shift $9
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 5
                parameter \Y_WIDTH 3
                connect \A \i8ua [7:0]
                connect \B $7
                connect \Y $3
            end
            wire width 5 $10
            cell $mul $11
                parameter \A_SIGNED 0
                parameter \B_SIGNED 0
                parameter \A_WIDTH 3
                parameter \B_WIDTH 2
                parameter \Y_WIDTH 5
                connect \A \i3 [2:0]
                connect \B 2'11
                connect \Y $10
            end
            cell $shift $12
                parameter \A_SIGNED 1
                parameter \B_SIGNED 0
                parameter \A_WIDTH 8
                parameter \B_WIDTH 5
                parameter \Y_WIDTH 3
                connect \A \i8sa [7:0]
                connect \B $10
                connect \Y $4
            end
            connect \o1 { 1'0 $1 [2:0] }
            connect \o2 { 1'0 $2 [2:0] }
            connect \o3 { 1'0 $3 [2:0] }
            connect \o4 { 1'0 $4 [2:0] }
        end
        """)

    def test_initial(self):
        o = Signal()
        m = Module()
        m.d.comb += [
            o.eq(Initial())
        ]
        self.assertRTLIL(m, [o], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 1 output 0 \o
            cell $initstate $1
                connect \Y \o
            end
        end
        """)

    def test_anyvalue(self):
        o1 = Signal(8)
        o2 = Signal(8)
        m = Module()
        m.d.comb += [
            o1.eq(AnyConst(unsigned(4))),
            o2.eq(AnySeq(signed(4))),
        ]
        self.assertRTLIL(m, [o1, o2], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 output 0 \o1
            wire width 8 output 1 \o2
            wire width 4 $1
            wire width 4 $2
            cell $anyconst $3
                parameter \WIDTH 4
                connect \Y $1
            end
            cell $anyseq $4
                parameter \WIDTH 4
                connect \Y $2
            end
            connect \o1 { 4'0000 $1 [3:0] }
            connect \o2 { $2 [3] $2 [3] $2 [3] $2 [3] $2 [3:0] }
        end
        """)


class FlopTestCase(RTLILTestCase):
    def test_sync(self):
        o = Signal(8, init=0x55)
        i = Signal(8)
        m = Module()
        m.domains.sync = sync = ClockDomain()
        m.d.sync += o.eq(i)
        self.assertRTLIL(m, [i, ClockSignal(), ResetSignal(), o], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i
            wire width 1 input 1 \clk
            wire width 1 input 2 \rst
            attribute \init 8'01010101
            wire width 8 output 3 \o
            wire width 8 $1
            process $2
                assign $1 [7:0] \i [7:0]
                switch \rst [0]
                    case 1'1
                        assign $1 [7:0] 8'01010101
                end
            end
            cell $dff $3
                parameter \WIDTH 8
                parameter \CLK_POLARITY 1
                connect \D $1 [7:0]
                connect \CLK \clk [0]
                connect \Q \o
            end
        end
        """)

    def test_async(self):
        o = Signal(8, init=0x55)
        i = Signal(8)
        m = Module()
        m.domains.sync = sync = ClockDomain(clk_edge="neg", async_reset=True)
        m.d.sync += o.eq(i)
        self.assertRTLIL(m, [i, ClockSignal(), ResetSignal(), o], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i
            wire width 1 input 1 \clk
            wire width 1 input 2 \rst
            attribute \init 8'01010101
            wire width 8 output 3 \o
            cell $adff $1
                parameter \WIDTH 8
                parameter \CLK_POLARITY 0
                parameter \ARST_POLARITY 1
                parameter \ARST_VALUE 8'01010101
                connect \D \i [7:0]
                connect \CLK \clk [0]
                connect \Q \o
                connect \ARST \rst [0]
            end
        end
        """)


class SwitchTestCase(RTLILTestCase):
    def test_simple(self):
        sel = Signal(4)
        out = Signal(4, init=12)
        m = Module()
        with m.Switch(sel):
            with m.Case(0):
                m.d.comb += out.eq(1)
            with m.Case(1, 2):
                m.d.comb += out.eq(2)
            with m.Case("11--"):
                m.d.comb += out.eq(3)
            with m.Case():
                m.d.comb += out.eq(4)
            with m.Default():
                m.d.comb += out.eq(5)
        self.assertRTLIL(m, [sel, out], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 4 input 0 \sel
            wire width 4 output 1 \out
            process $1
                assign \out [3:0] 4'1100
                switch \sel [3:0]
                    case 4'0000
                        assign \out [3:0] 4'0001
                    case 4'0001, 4'0010
                        assign \out [3:0] 4'0010
                    case 4'11--
                        assign \out [3:0] 4'0011
                    case
                        assign \out [3:0] 4'0101
                end
            end
        end
        """)

    def test_aba(self):
        a = Signal(2)
        sel = Signal(4)
        out = Signal(4, init=12)
        m = Module()
        with m.Switch(sel):
            with m.Case(0):
                m.d.comb += out.eq(1)
            with m.Case(1, 2):
                m.d.comb += out.eq(2)
            with m.Case("11--"):
                m.d.comb += out.eq(3)
            with m.Case():
                m.d.comb += out.eq(4)
            with m.Default():
                m.d.comb += out.eq(5)
        m.d.comb += out[1:3].eq(a)
        self.assertRTLIL(m, [sel, a, out], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 4 input 0 \sel
            wire width 2 input 1 \a
            wire width 4 output 2 \out
            process $1
                assign \out [3:0] 4'1100
                switch \sel [3:0]
                    case 4'0000
                        assign \out [3:0] 4'0001
                    case 4'0001, 4'0010
                        assign \out [3:0] 4'0010
                    case 4'11--
                        assign \out [3:0] 4'0011
                    case
                        assign \out [3:0] 4'0101
                end
                switch {}
                    case
                        assign \out [2:1] \a [1:0]
                end
            end
        end
        """)

    def test_nested(self):
        sel1 = Signal(4)
        sel2 = Signal(4)
        sel3 = Signal(4)
        out = Signal(4, init=12)
        m = Module()
        with m.Switch(sel1):
            with m.Case(0):
                m.d.comb += out.eq(1)
            with m.Case(1):
                with m.Switch(sel2):
                    with m.Case(0):
                        m.d.comb += out.eq(2)
                    with m.Case(1):
                        with m.Switch(sel3):
                            with m.Case(0):
                                m.d.comb += out.eq(3)
                            with m.Default():
                                m.d.comb += out.eq(4)
            with m.Case(2):
                m.d.comb += out.eq(5)
            with m.Default():
                m.d.comb += out.eq(6)
        self.assertRTLIL(m, [sel1, sel2, sel3, out], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 4 input 0 \sel1
            wire width 4 input 1 \sel2
            wire width 4 input 2 \sel3
            wire width 4 output 3 \out
            process $1
                assign \out [3:0] 4'1100
                switch \sel1 [3:0]
                    case 4'0000
                        assign \out [3:0] 4'0001
                    case 4'0001
                         switch \sel2 [3:0]
                            case 4'0000
                                assign \out [3:0] 4'0010
                            case 4'0001
                                switch \sel3 [3:0]
                                    case 4'0000
                                        assign \out [3:0] 4'0011
                                    case
                                        assign \out [3:0] 4'0100
                                end
                        end
                    case 4'0010
                        assign \out [3:0] 4'0101
                    case
                        assign \out [3:0] 4'0110
                end
            end
        end
        """)

    def test_trivial(self):
        sel = Signal(4)
        out = Signal(4)
        m = Module()
        with m.Switch(sel):
            with m.Default():
                m.d.comb += out.eq(1)
        self.assertRTLIL(m, [sel, out], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 4 input 0 \sel
            wire width 4 output 1 \out
            process $1
                assign \out [3:0] 4'0000
                switch \sel [3:0]
                    case
                        assign \out [3:0] 4'0001
                end
            end
        end
        """)


class IOBTestCase(RTLILTestCase):
    def test_iob(self):
        io_i = IOPort(1)
        io_o = IOPort(1)
        io_oe = IOPort(1)
        io_io = IOPort(1)
        i = Signal()
        o = Signal()
        oe = Signal()
        m = Module()
        m.submodules += IOBufferInstance(io_i, o=i)
        m.submodules += IOBufferInstance(io_o, i=o)
        m.submodules += IOBufferInstance(io_oe, i=oe)
        m.submodules += IOBufferInstance(io_io, i=i, o=o, oe=oe)
        self.assertRTLIL(m, [], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 1 \i
            wire width 1 \o
            wire width 1 \oe
            wire width 1 output 0 \io_i
            wire width 1 input 1 \io_o
            wire width 1 input 2 \io_oe
            wire width 1 inout 3 \io_io
            cell $tribuf $1
                parameter \WIDTH 1
                connect \Y \io_io [0]
                connect \A \o [0]
                connect \EN \oe [0]
            end
            connect \io_i [0] \i [0]
            connect \o \io_o [0]
            connect \oe \io_oe [0]
            connect \i \io_io [0]
        end
        """)


class InstanceTestCase(RTLILTestCase):
    def test_instance(self):
        m = Module()
        i = Signal(2)
        o = Signal(3)
        m.submodules.inst = Instance("t", i_i=i, o_o=o)
        self.assertRTLIL(m, [i, o], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 2 input 0 \i
            wire width 3 output 1 \o
            cell \t \inst
                connect \i \i [1:0]
                connect \o \o
            end
        end
        """)

    def test_attr(self):
        m = Module()
        i = Signal(2)
        o = Signal(3)
        m.submodules.inst = Instance("t", i_i=i, o_o=o,
                                     a_str="abc", a_int=123,
                                     a_const=Const(0x55, 8),
                                     a_sint=-3, a_sconst=Const(-2, 3))
        self.assertRTLIL(m, [i, o], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 2 input 0 \i
            wire width 3 output 1 \o
            attribute \str "abc"
            attribute \int 123
            attribute \const 8'01010101
            attribute \sint 32'11111111111111111111111111111101
            attribute \sconst 3'110
            cell \t \inst
                connect \i \i [1:0]
                connect \o \o
            end
        end
        """)

    def test_param(self):
        m = Module()
        i = Signal(2)
        o = Signal(3)
        m.submodules.inst = Instance("t", i_i=i, o_o=o,
                                     p_str="abc", p_int=123, p_float=3.0,
                                     p_const=Const(0x55, 8),
                                     p_sint=-3, p_sconst=Const(2, signed(3)))
        self.assertRTLIL(m, [i, o], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 2 input 0 \i
            wire width 3 output 1 \o
            cell \t \inst
                parameter \str "abc"
                parameter \int 123
                parameter real \float "3.0"
                parameter \const 8'01010101
                parameter signed \sint 32'11111111111111111111111111111101
                parameter signed \sconst 3'010
                connect \i \i [1:0]
                connect \o \o
            end
        end
        """)

    def test_ioport(self):
        io_i = IOPort(2)
        io_o = IOPort(3)
        io_io = IOPort(4)
        m = Module()
        m.submodules.sm = sm = Module()
        sm.submodules.inst = Instance("t", i_i=io_i, o_o=io_o, io_io=io_io)
        self.assertRTLIL(m, [], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 2 input 0 \io_i
            wire width 3 output 1 \io_o
            wire width 4 inout 2 \io_io
            cell \top.sm \sm
                connect \io_i \io_i [1:0]
                connect \io_o \io_o [2:0]
                connect \io_io \io_io [3:0]
            end
        end
        attribute \generator "Amaranth"
        module \top.sm
            wire width 2 input 0 \io_i
            wire width 3 output 1 \io_o
            wire width 4 inout 2 \io_io
            cell \t \inst
                connect \i \io_i [1:0]
                connect \o \io_o [2:0]
                connect \io \io_io [3:0]
            end
        end
        """)

    def test_concat(self):
        io_a = IOPort(2)
        io_b = IOPort(2)
        m = Module()
        m.submodules.inst = Instance("t", io_io=Cat(io_a, io_b))
        self.assertRTLIL(m, [], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 2 inout 0 \io_a
            wire width 2 inout 1 \io_b
            cell \t \inst
                connect \io { \io_b [1:0] \io_a [1:0] }
            end
        end
        """)


class MemoryTestCase(RTLILTestCase):
    def test_async_read(self):
        m = Module()
        m.submodules.mem = mem = memory.Memory(shape=8, depth=4, init=[1, 2, 3, 4])
        wp = mem.write_port()
        rp = mem.read_port(domain="comb")
        self.assertRTLIL(m, [
            ("rd", rp.data, None),
            ("ra", rp.addr, None),
            ("wd", wp.data, None),
            ("wa", wp.addr, None),
            ("we", wp.en, None),
        ], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            memory width 8 size 4 \mem
            wire width 8 \rp__data
            wire width 2 \rp__addr
            wire width 8 \wp__data
            wire width 2 \wp__addr
            wire width 1 \wp__en
            wire width 2 input 0 \ra
            wire width 8 input 1 \wd
            wire width 2 input 2 \wa
            wire width 1 input 3 \we
            wire width 1 input 4 \clk
            wire width 1 input 5 \rst
            wire width 8 output 6 \rd
            cell $meminit_v2 $1
                parameter \MEMID "\\mem"
                parameter \ABITS 0
                parameter \WIDTH 8
                parameter \WORDS 4
                parameter \PRIORITY 0
                connect \ADDR { }
                connect \DATA 32'00000100000000110000001000000001
                connect \EN 8'11111111
            end
            cell $memwr_v2 $2
                parameter \MEMID "\\mem"
                parameter \ABITS 2
                parameter \WIDTH 8
                parameter \CLK_ENABLE 1
                parameter \CLK_POLARITY 1
                parameter \PORTID 0
                parameter \PRIORITY_MASK 0
                connect \ADDR \wa [1:0]
                connect \DATA \wd [7:0]
                connect \EN { \we [0] \we [0] \we [0] \we [0] \we [0] \we [0] \we [0] \we [0] }
                connect \CLK \clk [0]
            end
            cell $memrd_v2 $3
                parameter \MEMID "\\mem"
                parameter \ABITS 2
                parameter \WIDTH 8
                parameter \TRANSPARENCY_MASK 1'0
                parameter \COLLISION_X_MASK 1'0
                parameter \ARST_VALUE 8'xxxxxxxx
                parameter \SRST_VALUE 8'xxxxxxxx
                parameter \INIT_VALUE 8'xxxxxxxx
                parameter \CE_OVER_SRST 0
                parameter \CLK_ENABLE 0
                parameter \CLK_POLARITY 1
                connect \ADDR \ra [1:0]
                connect \DATA \rp__data
                connect \ARST 1'0
                connect \SRST 1'0
                connect \EN 1'1
                connect \CLK 1'0
            end
            connect \rp__addr \ra [1:0]
            connect \wp__data \wd [7:0]
            connect \wp__addr \wa [1:0]
            connect \wp__en \we [0]
            connect \rd \rp__data [7:0]
        end
        """)

    def test_sync_read(self):
        m = Module()
        m.submodules.mem = mem = memory.Memory(shape=8, depth=4, init=[1, 2, 3, 4], attrs={"ram_style": "block"})
        wp = mem.write_port()
        rp = mem.read_port(transparent_for=(wp,))
        self.assertRTLIL(m, [
            ("rd", rp.data, None),
            ("ra", rp.addr, None),
            ("re", rp.en, None),
            ("wd", wp.data, None),
            ("wa", wp.addr, None),
            ("we", wp.en, None),
        ], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            attribute \ram_style "block"
            memory width 8 size 4 \mem
            wire width 8 \rp__data
            wire width 2 \rp__addr
            wire width 1 \rp__en
            wire width 8 \wp__data
            wire width 2 \wp__addr
            wire width 1 \wp__en
            wire width 2 input 0 \ra
            wire width 1 input 1 \re
            wire width 8 input 2 \wd
            wire width 2 input 3 \wa
            wire width 1 input 4 \we
            wire width 1 input 5 \clk
            wire width 1 input 6 \rst
            wire width 8 output 7 \rd
            cell $meminit_v2 $1
                parameter \MEMID "\\mem"
                parameter \ABITS 0
                parameter \WIDTH 8
                parameter \WORDS 4
                parameter \PRIORITY 0
                connect \ADDR { }
                connect \DATA 32'00000100000000110000001000000001
                connect \EN 8'11111111
            end
            cell $memwr_v2 $2
                parameter \MEMID "\\mem"
                parameter \ABITS 2
                parameter \WIDTH 8
                parameter \CLK_ENABLE 1
                parameter \CLK_POLARITY 1
                parameter \PORTID 0
                parameter \PRIORITY_MASK 0
                connect \ADDR \wa [1:0]
                connect \DATA \wd [7:0]
                connect \EN { \we [0] \we [0] \we [0] \we [0] \we [0] \we [0] \we [0] \we [0] }
                connect \CLK \clk [0]
            end
            cell $memrd_v2 $3
                parameter \MEMID "\\mem"
                parameter \ABITS 2
                parameter \WIDTH 8
                parameter \TRANSPARENCY_MASK 1'1
                parameter \COLLISION_X_MASK 1'0
                parameter \ARST_VALUE 8'xxxxxxxx
                parameter \SRST_VALUE 8'xxxxxxxx
                parameter \INIT_VALUE 8'xxxxxxxx
                parameter \CE_OVER_SRST 0
                parameter \CLK_ENABLE 1
                parameter \CLK_POLARITY 1
                connect \ADDR \ra [1:0]
                connect \DATA \rp__data
                connect \ARST 1'0
                connect \SRST 1'0
                connect \EN \re [0]
                connect \CLK \clk [0]
            end
            connect \rp__addr \ra [1:0]
            connect \rp__en \re [0]
            connect \wp__data \wd [7:0]
            connect \wp__addr \wa [1:0]
            connect \wp__en \we [0]
            connect \rd \rp__data [7:0]
        end
        """)


class PrintTestCase(RTLILTestCase):
    def test_print_simple(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        m = Module()
        m.d.comb += [
            Print(i8u, i8s),
        ]
        self.assertRTLIL(m, [i8u, i8s], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8u
            wire width 8 input 1 signed \i8s
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $print $3
                parameter \FORMAT "{8:> du} {8:> ds}\n"
                parameter \ARGS_WIDTH 16
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                connect \EN $1 [0]
                connect \ARGS { \i8s [7:0] \i8u [7:0] }
                connect \TRG { }
            end
        end
        """)

    def test_print_sync(self):
        i8u = Signal(8)
        i8s = Signal(signed(8))
        m = Module()
        m.domains.sync = ClockDomain()
        m.d.sync += [
            Print(i8u, i8s),
        ]
        self.assertRTLIL(m, [i8u, i8s, ClockSignal(), ResetSignal()], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i8u
            wire width 8 input 1 signed \i8s
            wire width 1 input 2 \clk
            wire width 1 input 3 \rst
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $print $3
                parameter \FORMAT "{8:> du} {8:> ds}\n"
                parameter \ARGS_WIDTH 16
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 1
                parameter \TRG_WIDTH 1
                parameter \TRG_POLARITY 1
                connect \EN $1 [0]
                connect \ARGS { \i8s [7:0] \i8u [7:0] }
                connect \TRG \clk [0]
            end
        end
        """)

    def test_assert_simple(self):
        test = Signal()
        en = Signal()
        m = Module()
        with m.If(en):
            m.d.comb += Assert(test)
        self.assertRTLIL(m, [test, en], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 1 input 0 \test
            wire width 1 input 1 \en
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                switch \en [0]
                    case 1'1
                        assign $1 [0] 1'1
                end
            end
            cell $check $3
                parameter \FORMAT ""
                parameter \ARGS_WIDTH 0
                parameter signed \PRIORITY 32'11111111111111111111111111111101
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                parameter \FLAVOR "assert"
                connect \EN $1 [0]
                connect \ARGS { }
                connect \TRG { }
                connect \A \test [0]
            end
        end
        """)

    def test_assume_msg(self):
        msg = Signal(32)
        test = Signal()
        m = Module()
        m.domains.sync = ClockDomain()
        m.d.sync += [
            Assume(test, Format("{:s}", msg)),
        ]
        self.assertRTLIL(m, [msg, test, ClockSignal(), ResetSignal()], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 32 input 0 \msg
            wire width 1 input 1 \test
            wire width 1 input 2 \clk
            wire width 1 input 3 \rst
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $check $3
                parameter \FORMAT "{32:< c}"
                parameter \ARGS_WIDTH 32
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 1
                parameter \TRG_WIDTH 1
                parameter \TRG_POLARITY 1
                parameter \FLAVOR "assume"
                connect \EN $1 [0]
                connect \ARGS { \msg [7:0] \msg [15:8] \msg [23:16] \msg [31:24] }
                connect \TRG \clk [0]
                connect \A \test [0]
            end
        end
        """)

    def test_print_char(self):
        i = Signal(21)
        m = Module()
        m.d.comb += [
            Print(Format("{:c} {:-<5c} {:->5c}", i, i, i)),
        ]
        self.assertRTLIL(m, [i], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 21 input 0 \i
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $print $3
                parameter \FORMAT "{21:U} {21:U}---- ----{21:U}\n"
                parameter \ARGS_WIDTH 63
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                connect \EN $1 [0]
                connect \ARGS { \i [20:0] \i [20:0] \i [20:0] }
                connect \TRG { }
            end
        end
        """)

    def test_print_base(self):
        i = Signal(8)
        m = Module()
        m.d.comb += [
            Print(Format("{:b} {:o} {:d} {:x} {:X} {:#x} {:#d} {:#_x}", i, i, i, i, i, i, i, i)),
        ]
        self.assertRTLIL(m, [i], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $print $3
                parameter \FORMAT "{8:> bu} {8:> ou} {8:> du} {8:> hu} {8:> Hu} {8:> h#u} {8:> du} {8:> h#_u}\n"
                parameter \ARGS_WIDTH 64
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                connect \EN $1 [0]
                connect \ARGS { \i [7:0] \i [7:0] \i [7:0] \i [7:0] \i [7:0] \i [7:0] \i [7:0] \i [7:0] }
                connect \TRG { }
            end
        end
        """)

    def test_print_sign(self):
        i = Signal(8)
        m = Module()
        m.d.comb += [
            Print(Format("{:5x} {:-5x} {:+5x} {: 5x}", i, i, i, i)),
        ]
        self.assertRTLIL(m, [i], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $print $3
                parameter \FORMAT "{8:> 5hu} {8:> 5h-u} {8:> 5h+u} {8:> 5h u}\n"
                parameter \ARGS_WIDTH 32
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                connect \EN $1 [0]
                connect \ARGS { \i [7:0] \i [7:0] \i [7:0] \i [7:0] }
                connect \TRG { }
            end
        end
        """)

    def test_print_align(self):
        i = Signal(8)
        m = Module()
        m.d.comb += [
            Print(Format("{:<5x} {:>5x} {:=5x} {:05x} {:-<5x}", i, i, i, i, i)),
        ]
        self.assertRTLIL(m, [i], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 8 input 0 \i
            wire width 1 $1
            process $2
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $print $3
                parameter \FORMAT "{8:< 5hu} {8:> 5hu} {8:= 5hu} {8:=05hu} {8:<-5hu}\n"
                parameter \ARGS_WIDTH 40
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                connect \EN $1 [0]
                connect \ARGS { \i [7:0] \i [7:0] \i [7:0] \i [7:0] \i [7:0] }
                connect \TRG { }
            end
        end
        """)

    def test_escape_curly(self):
        m = Module()
        m.d.comb += [
            Print("{"),
            Print("}"),
        ]
        self.assertRTLIL(m, [], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 1 $1
            wire width 1 $2
            process $3
                assign $1 [0] 1'0
                assign $1 [0] 1'1
            end
            cell $print $4
                parameter \FORMAT "{{\n"
                parameter \ARGS_WIDTH 0
                parameter signed \PRIORITY 32'11111111111111111111111111111110
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                connect \EN $1 [0]
                connect \ARGS { }
                connect \TRG { }
            end
            process $5
                assign $2 [0] 1'0
                assign $2 [0] 1'1
            end
            cell $print $6
                parameter \FORMAT "}}\n"
                parameter \ARGS_WIDTH 0
                parameter signed \PRIORITY 32'11111111111111111111111111111100
                parameter \TRG_ENABLE 0
                parameter \TRG_WIDTH 0
                parameter \TRG_POLARITY 0
                connect \EN $2 [0]
                connect \ARGS { }
                connect \TRG { }
            end
        end
        """)


class DetailTestCase(RTLILTestCase):
    def test_enum(self):
        class MyEnum(enum.Enum, shape=unsigned(2)):
            A = 0
            B = 1
            C = 2

        sig = Signal(MyEnum)
        m = Module()
        m.d.comb += sig.eq(MyEnum.A)
        self.assertRTLIL(m, [sig.as_value()], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            attribute \enum_base_type "DetailTestCase.test_enum.<locals>.MyEnum"
            attribute \enum_value_00 "A"
            attribute \enum_value_01 "B"
            attribute \enum_value_10 "C"
            wire width 2 output 0 \sig
            connect \sig 2'00
        end
        """)

    def test_struct(self):
        class MyEnum(enum.Enum, shape=unsigned(2)):
            A = 0
            B = 1
            C = 2

        class Meow(data.Struct):
            a: MyEnum
            b: 3
            c: signed(4)
            d: data.ArrayLayout(2, 2)

        sig = Signal(Meow)
        m = Module()
        self.assertRTLIL(m, [sig.as_value()], R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
            wire width 13 input 0 \sig
            attribute \enum_base_type "DetailTestCase.test_struct.<locals>.MyEnum"
            attribute \enum_value_00 "A"
            attribute \enum_value_01 "B"
            attribute \enum_value_10 "C"
            wire width 2 \sig.a
            wire width 3 \sig.b
            wire width 4 signed \sig.c
            wire width 4 \sig.d
            wire width 2 \sig.d[0]
            wire width 2 \sig.d[1]
            connect \sig.a \sig [1:0]
            connect \sig.b \sig [4:2]
            connect \sig.c \sig [8:5]
            connect \sig.d \sig [12:9]
            connect \sig.d[0] \sig [10:9]
            connect \sig.d[1] \sig [12:11]
        end
        """)

class ComponentTestCase(RTLILTestCase):
    def test_component(self):
        class MyComponent(wiring.Component):
            i: wiring.In(unsigned(8))
            o: wiring.Out(unsigned(8))

            def elaborate(self, platform):
                return Module()

        self.assertRTLIL(MyComponent(), None, R"""
        attribute \generator "Amaranth"
        attribute \top 1
        module \top
        wire width 8 input 0 \i
        wire width 8 output 1 \o
        connect \o 8'00000000
        end
        """)
