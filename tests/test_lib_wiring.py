import unittest
from types import SimpleNamespace as NS

from amaranth import *
from amaranth.hdl.ast import ValueCastable
from amaranth.lib import data, enum
from amaranth.lib.wiring import Flow, In, Out, Member
from amaranth.lib.wiring import SignatureError, SignatureMembers, FlippedSignatureMembers
from amaranth.lib.wiring import Signature, FlippedSignature, Interface, FlippedInterface
from amaranth.lib.wiring import Component
from amaranth.lib.wiring import ConnectionError, connect, flipped


class FlowTestCase(unittest.TestCase):
    def test_flow_call(self):
        self.assertEqual(In(unsigned(1)), Member(Flow.In, unsigned(1)))
        self.assertEqual(Out(5), Member(Flow.Out, 5))

    def test_flow_repr(self):
        self.assertEqual(repr(Flow.In), "In")
        self.assertEqual(repr(Flow.Out), "Out")

    def test_flow_str(self):
        self.assertEqual(str(Flow.In), "In")
        self.assertEqual(str(Flow.Out), "Out")


class MemberTestCase(unittest.TestCase):
    def test_port_member(self):
        member = Member(In, unsigned(1))
        self.assertEqual(member.flow, In)
        self.assertEqual(member.is_port, True)
        self.assertEqual(member.shape, unsigned(1))
        self.assertEqual(member.reset, None)
        self.assertEqual(member.is_signature, False)
        with self.assertRaisesRegex(AttributeError,
                r"^A port member does not have a signature$"):
            member.signature
        self.assertEqual(member.dimensions, ())
        self.assertEqual(repr(member), "In(unsigned(1))")

    def test_port_member_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Port member description must be a shape-castable object or a signature, "
                r"not 'whatever'$"):
            Member(In, "whatever")

    def test_port_member_reset(self):
        member = Member(Out, unsigned(1), reset=1)
        self.assertEqual(member.flow, Out)
        self.assertEqual(member.shape, unsigned(1))
        self.assertEqual(member.reset, 1)
        self.assertEqual(repr(member._reset_as_const), repr(Const(1, 1)))
        self.assertEqual(repr(member), "Out(unsigned(1), reset=1)")

    def test_port_member_reset_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Port member reset value 'no' is not a valid constant initializer "
                r"for unsigned\(1\)$"):
            Member(In, 1, reset="no")

    def test_port_member_reset_shape_castable(self):
        layout = data.StructLayout({"a": 32})
        member = Member(In, layout, reset={"a": 1})
        self.assertEqual(member.flow, In)
        self.assertEqual(member.shape, layout)
        self.assertEqual(member.reset, {"a": 1})
        self.assertEqual(repr(member), "In(StructLayout({'a': 32}), reset={'a': 1})")

    def test_port_member_reset_shape_castable_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Port member reset value 'no' is not a valid constant initializer "
                r"for StructLayout\({'a': 32}\)$"):
            Member(In, data.StructLayout({"a": 32}), reset="no")

    def test_signature_member_out(self):
        sig = Signature({"data": Out(unsigned(32))})
        member = Member(Out, sig)
        self.assertEqual(member.flow, Out)
        self.assertEqual(member.is_port, False)
        with self.assertRaisesRegex(AttributeError,
                r"^A signature member does not have a shape$"):
            member.shape
        with self.assertRaisesRegex(AttributeError,
                r"^A signature member does not have a reset value$"):
            member.reset
        self.assertEqual(member.is_signature, True)
        self.assertEqual(member.signature, sig)
        self.assertEqual(member.dimensions, ())
        self.assertEqual(repr(member), "Out(Signature({'data': Out(unsigned(32))}))")

    def test_signature_member_in(self):
        sig = Signature({"data": In(unsigned(32))})
        member = Member(In, sig)
        self.assertEqual(member.flow, In)
        self.assertEqual(member.is_port, False)
        with self.assertRaisesRegex(AttributeError,
                r"^A signature member does not have a shape$"):
            member.shape
        with self.assertRaisesRegex(AttributeError,
                r"^A signature member does not have a reset value$"):
            member.reset
        self.assertEqual(member.is_signature, True)
        self.assertEqual(member.signature, sig.flip())
        self.assertEqual(member.dimensions, ())
        self.assertEqual(repr(member), "In(Signature({'data': In(unsigned(32))}))")

    def test_signature_member_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^A signature member cannot have a reset value$"):
            Member(In, Signature({}), reset=1)

    def test_array(self):
        array_2 = Member(In, unsigned(1)).array(2)
        self.assertEqual(array_2.dimensions, (2,))
        self.assertEqual(repr(array_2), "In(unsigned(1)).array(2)")

        array_2_3 = Member(In, unsigned(1)).array(2, 3)
        self.assertEqual(array_2_3.dimensions, (2, 3))
        self.assertEqual(repr(array_2_3), "In(unsigned(1)).array(2, 3)")

        array_2_3_chained = Member(In, unsigned(1)).array(3).array(2)
        self.assertEqual(array_2_3_chained.dimensions, (2, 3))
        self.assertEqual(repr(array_2_3_chained), "In(unsigned(1)).array(2, 3)")

    def test_array_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Member array dimensions must be non-negative integers, not -1$"):
            Member(In, unsigned(1)).array(-1)
        with self.assertRaisesRegex(TypeError,
                r"^Member array dimensions must be non-negative integers, not 'what'$"):
            Member(In, unsigned(1)).array("what")

    def test_flip(self):
        self.assertEqual(In(1).flip(), Out(1))
        self.assertEqual(Out(1).flip(), In(1))

    def test_equality(self):
        self.assertEqual(In(1), In(1))
        self.assertNotEqual(In(1), Out(1))
        self.assertNotEqual(In(1), In(1, reset=1))
        self.assertNotEqual(In(1), In(1, reset=0))
        self.assertEqual(In(1), In(1).array())
        self.assertNotEqual(In(1), In(1).array(1))
        sig = Signature({})
        self.assertEqual(In(sig), In(sig))
        self.assertNotEqual(In(1), In(Signature({})))


class SignatureMembersTestCase(unittest.TestCase):
    def test_contains(self):
        self.assertNotIn("a", SignatureMembers())
        self.assertIn("a", SignatureMembers({"a": In(1)}))

    def test_getitem(self):
        members = SignatureMembers({"a": In(1)})
        self.assertEqual(members["a"], In(1))

    def test_getitem_missing(self):
        members = SignatureMembers({"a": In(1)})
        with self.assertRaisesRegex(SignatureError,
                r"^Member 'b' is not a part of the signature$"):
            members["b"]

    def test_getitem_wrong(self):
        members = SignatureMembers({"a": In(1)})
        with self.assertRaisesRegex(TypeError,
                r"^Member name must be a string, not 1$"):
            members[1]
        with self.assertRaisesRegex(NameError,
                r"^Member name '_a' must be a valid, public Python attribute name$"):
            members["_a"]
        with self.assertRaisesRegex(NameError,
                r"^Member name cannot be 'signature'$"):
            members["signature"]

    def test_setitem(self):
        members = SignatureMembers()
        members["a"] = In(1)
        self.assertEqual(members["a"], In(1))

    def test_setitem_existing(self):
        members = SignatureMembers({"a": In(1)})
        with self.assertRaisesRegex(SignatureError,
                r"^Member 'a' already exists in the signature and cannot be replaced$"):
            members["a"] = Out(2)

    def test_setitem_wrong(self):
        members = SignatureMembers()
        with self.assertRaisesRegex(TypeError,
                r"^Member name must be a string, not 1$"):
            members[1] = Out(1)
        with self.assertRaisesRegex(TypeError,
                r"^Assigned value 1 must be a member; did you mean In\(1\) or Out\(1\)\?$"):
            members["a"] = 1
        with self.assertRaisesRegex(NameError,
                r"^Member name '_a' must be a valid, public Python attribute name$"):
            members["_a"] = Out(1)
        with self.assertRaisesRegex(NameError,
                r"^Member name cannot be 'signature'$"):
            members["signature"] = Out(1)

    def test_delitem(self):
        members = SignatureMembers()
        with self.assertRaisesRegex(SignatureError,
                r"^Members cannot be removed from a signature$"):
            del members["a"]

    def test_iter_len(self):
        members = SignatureMembers()
        self.assertEqual(list(iter(members)), [])
        self.assertEqual(len(members), 0)
        members["a"] = In(1)
        self.assertEqual(list(iter(members)), ["a"])
        self.assertEqual(len(members), 1)

    def test_iter_sorted(self):
        self.assertEqual(list(iter(SignatureMembers({"a": In(1), "b": Out(1)}))),
                         ["a", "b"])
        self.assertEqual(list(iter(SignatureMembers({"b": In(1), "a": Out(1)}))),
                         ["a", "b"])

    def test_iadd(self):
        members = SignatureMembers()
        members += {"a": In(1)}
        members += [("b", Out(1))]
        self.assertEqual(members, SignatureMembers({"a": In(1), "b": Out(1)}))

    def test_freeze(self):
        members = SignatureMembers({"a": In(1)})
        self.assertEqual(members.frozen, False)
        members.freeze()
        self.assertEqual(members.frozen, True)
        with self.assertRaisesRegex(SignatureError,
                r"^Cannot add members to a frozen signature$"):
            members += {"b": Out(1)}

    def test_freeze_rec(self):
        sig = Signature({})
        members = SignatureMembers({
            "a": In(1),
            "s": Out(sig)
        })
        self.assertEqual(members.frozen, False)
        self.assertEqual(sig.frozen, False)
        self.assertEqual(sig.members.frozen, False)
        members.freeze()
        self.assertEqual(members.frozen, True)
        self.assertEqual(sig.frozen, True)
        self.assertEqual(sig.members.frozen, True)

    def test_flatten(self):
        sig = Signature({
            "b": Out(1),
            "c": In(2)
        })
        members = SignatureMembers({
            "a": In(1),
            "s": Out(sig)
        })
        self.assertEqual(list(members.flatten()), [
            (("a",), In(1)),
            (("s",), Out(sig)),
            (("s", "b"), Out(1)),
            (("s", "c"), In(2)),
        ])

    def test_create(self):
        sig = Signature({
            "b": Out(2)
        })
        members = SignatureMembers({
            "a": In(1),
            "s": Out(sig)
        })
        attrs = members.create()
        self.assertEqual(list(attrs.keys()), ["a", "s"])
        self.assertIsInstance(attrs["a"], Signal)
        self.assertEqual(attrs["a"].shape(), unsigned(1))
        self.assertEqual(attrs["a"].name, "a")
        self.assertEqual(attrs["s"].b.shape(), unsigned(2))
        self.assertEqual(attrs["s"].b.name, "s__b")

    def test_create_reset(self):
        members = SignatureMembers({
            "a": In(1, reset=1),
        })
        attrs = members.create()
        self.assertEqual(attrs["a"].reset, 1)

    def test_create_tuple(self):
        sig = SignatureMembers({
            "a": Out(1).array(2, 3)
        })
        members = sig.create()
        self.assertEqual(len(members["a"]), 2)
        self.assertEqual(len(members["a"][0]), 3)
        self.assertEqual(len(members["a"][1]), 3)
        for x in members["a"]:
            for y in x:
                self.assertIsInstance(y, Signal)
        self.assertEqual(members["a"][1][2].name, "a__1__2")

    def test_repr(self):
        self.assertEqual(repr(SignatureMembers({})),
                         "SignatureMembers({})")
        self.assertEqual(repr(SignatureMembers({"a": In(1)})),
                         "SignatureMembers({'a': In(1)})")
        members = SignatureMembers({"b": Out(2)})
        members.freeze()
        self.assertEqual(repr(members),
                         "SignatureMembers({'b': Out(2)}).freeze()")


class FlippedSignatureMembersTestCase(unittest.TestCase):
    def test_basic(self):
        members = SignatureMembers({"a": In(1)})
        fmembers = members.flip()
        self.assertIsInstance(fmembers, FlippedSignatureMembers)
        self.assertIn("a", fmembers)
        self.assertEqual(fmembers["a"], Out(1))
        fmembers["b"] = Out(2)
        self.assertEqual(len(fmembers), 2)
        self.assertEqual(members["b"], In(2))
        self.assertEqual(list(fmembers), ["a", "b"])
        fmembers += {"c": In(2)}
        self.assertEqual(members["c"], Out(2))
        self.assertIs(fmembers.flip(), members)

    def test_eq(self):
        self.assertEqual(SignatureMembers({"a": In(1)}).flip(),
                         SignatureMembers({"a": In(1)}).flip())
        self.assertEqual(SignatureMembers({"a": In(1)}).flip(),
                         SignatureMembers({"a": Out(1)}))

    def test_delitem(self):
        fmembers = SignatureMembers().flip()
        with self.assertRaisesRegex(SignatureError,
                r"^Members cannot be removed from a signature$"):
            del fmembers["a"]

    def test_freeze(self):
        members = SignatureMembers({"a": In(1)})
        fmembers = members.flip()
        self.assertEqual(fmembers.frozen, False)
        fmembers.freeze()
        self.assertEqual(members.frozen, True)
        self.assertEqual(fmembers.frozen, True)

    def test_repr(self):
        fmembers = SignatureMembers({"a": In(1)}).flip()
        self.assertEqual(repr(fmembers), "SignatureMembers({'a': In(1)}).flip()")


class SignatureTestCase(unittest.TestCase):
    def test_create(self):
        sig = Signature({"a": In(1)})
        self.assertEqual(sig.members, SignatureMembers({"a": In(1)}))

    def test_eq(self):
        self.assertEqual(Signature({"a": In(1)}),
                         Signature({"a": In(1)}))
        self.assertNotEqual(Signature({"a": In(1)}),
                            Signature({"a": Out(1)}))

    def test_freeze(self):
        sig = Signature({"a": In(1)})
        self.assertEqual(sig.frozen, False)
        sig.freeze()
        self.assertEqual(sig.frozen, True)
        with self.assertRaisesRegex(SignatureError,
                r"^Cannot add members to a frozen signature$"):
            sig.members += {"b": Out(1)}

    def assertFlattenedSignature(self, actual, expected):
        for (a_path, a_member, a_value), (b_path, b_member, b_value) in zip(actual, expected):
            self.assertEqual(a_path, b_path)
            self.assertEqual(a_member, b_member)
            self.assertIs(a_value, b_value)

    def test_flatten(self):
        sig = Signature({"a": In(1), "b": Out(2).array(2)})
        intf = sig.create()
        self.assertFlattenedSignature(sig.flatten(intf), [
            (("a",), In(1), intf.a),
            ((("b",), 0), Out(2), intf.b[0]),
            ((("b",), 1), Out(2), intf.b[1])
        ])

    def test_flatten_sig(self):
        sig = Signature({
            "a": Out(Signature({"p": Out(1)})),
            "b": Out(Signature({"q": In (1)})),
            "c": In( Signature({"r": Out(1)})),
            "d": In( Signature({"s": In (1)})),
        })
        intf = sig.create()
        self.assertFlattenedSignature(sig.flatten(intf), [
            (("a", "p"), Out(1), intf.a.p),
            (("b", "q"), In (1), intf.b.q),
            (("c", "r"), Out(1), intf.c.r),
            (("d", "s"), In (1), intf.d.s),
        ])

    def assertNotCompliant(self, reason_regex, sig, obj):
        self.assertFalse(sig.is_compliant(obj))
        reasons = []
        self.assertFalse(sig.is_compliant(obj, reasons=reasons))
        self.assertEqual(len(reasons), 1)
        self.assertRegex(reasons[0], reason_regex)

    def test_is_compliant(self):
        self.assertNotCompliant(
            r"^'obj' does not have an attribute 'a'$",
            sig=Signature({"a": In(1)}),
            obj=NS())
        self.assertNotCompliant(
            r"^'obj\.a' is expected to be a tuple or a list, but it is a \(sig \$signal\)$",
            sig=Signature({"a": In(1).array(2)}),
            obj=NS(a=Signal()))
        self.assertNotCompliant(
            r"^'obj\.a' is expected to have dimension 2, but its length is 1$",
            sig=Signature({"a": In(1).array(2)}),
            obj=NS(a=[Signal()]))
        self.assertNotCompliant(
            r"^'obj\.a\[0\]' is expected to have dimension 2, but its length is 1$",
            sig=Signature({"a": In(1).array(1, 2)}),
            obj=NS(a=[[Signal()]]))
        self.assertNotCompliant(
            r"^'obj\.a' is not a value-castable object, but 'foo'$",
            sig=Signature({"a": In(1)}),
            obj=NS(a="foo"))
        self.assertNotCompliant(
            r"^'obj\.a' is neither a signal nor a constant, but "
            r"\(\+ \(const 1'd1\) \(const 1'd1\)\)$",
            sig=Signature({"a": In(1)}),
            obj=NS(a=Const(1)+1))
        self.assertNotCompliant(
            r"^'obj\.a' is expected to have the shape unsigned\(1\), but "
            r"it has the shape unsigned\(2\)$",
            sig=Signature({"a": In(1)}),
            obj=NS(a=Signal(2)))
        self.assertNotCompliant(
            r"^'obj\.a' is expected to have the shape unsigned\(1\), but "
            r"it has the shape signed\(1\)$",
            sig=Signature({"a": In(unsigned(1))}),
            obj=NS(a=Signal(signed(1))))
        self.assertNotCompliant(
            r"^'obj\.a' is expected to have the reset value None, but it has the reset value 1$",
            sig=Signature({"a": In(1)}),
            obj=NS(a=Signal(reset=1)))
        self.assertNotCompliant(
            r"^'obj\.a' is expected to have the reset value 1, but it has the reset value 0$",
            sig=Signature({"a": In(1, reset=1)}),
            obj=NS(a=Signal(1)))
        self.assertNotCompliant(
            r"^'obj\.a' is expected to not be reset-less$",
            sig=Signature({"a": In(1)}),
            obj=NS(a=Signal(1, reset_less=True)))
        self.assertNotCompliant(
            r"^'obj\.a' does not have an attribute 'b'$",
            sig=Signature({"a": Out(Signature({"b": In(1)}))}),
            obj=NS(a=Signal()))
        self.assertTrue(
            Signature({"a": In(1)}).is_compliant(
                NS(a=Signal())))
        self.assertTrue(
            Signature({"a": In(1)}).is_compliant(
                NS(a=Const(1))))
        self.assertTrue( # list
            Signature({"a": In(1).array(2, 2)}).is_compliant(
                NS(a=[[Const(1), Const(1)], [Signal(), Signal()]])))
        self.assertTrue( # tuple
            Signature({"a": In(1).array(2, 2)}).is_compliant(
                NS(a=((Const(1), Const(1)), (Signal(), Signal())))))
        self.assertTrue( # mixed list and tuple
            Signature({"a": In(1).array(2, 2)}).is_compliant(
                NS(a=[[Const(1), Const(1)], (Signal(), Signal())])))
        self.assertTrue(
            Signature({"a": Out(Signature({"b": In(1)}))}).is_compliant(
                NS(a=NS(b=Signal()))))

    def test_repr(self):
        sig = Signature({"a": In(1)})
        self.assertEqual(repr(sig), "Signature({'a': In(1)})")

    def test_repr_subclass(self):
        class S(Signature):
            def __init__(self):
                super().__init__({"a": In(1)})
        sig = S()
        self.assertRegex(repr(sig), r"^<.+\.S object at .+?>$")

    def test_subclasscheck(self):
        class S(Signature):
            pass
        self.assertTrue(issubclass(FlippedSignature, Signature))
        self.assertTrue(issubclass(Signature, Signature))
        self.assertTrue(issubclass(FlippedSignature, S))
        self.assertTrue(not issubclass(Signature, S))

    def test_instancecheck(self):
        class S(Signature):
            pass
        sig = Signature({})
        sig2 = S({})
        self.assertTrue(isinstance(sig.flip(), Signature))
        self.assertTrue(isinstance(sig2.flip(), Signature))
        self.assertTrue(not isinstance(sig.flip(), S))
        self.assertTrue(isinstance(sig2.flip(), S))


class FlippedSignatureTestCase(unittest.TestCase):
    def test_create(self):
        sig = Signature({"a": In(1)})
        fsig = sig.flip()
        self.assertIsInstance(fsig, FlippedSignature)
        self.assertIsInstance(fsig.members, FlippedSignatureMembers)
        self.assertIs(fsig.flip(), sig)

    def test_eq(self):
        self.assertEqual(Signature({"a": In(1)}).flip(),
                         Signature({"a": In(1)}).flip())
        self.assertEqual(Signature({"a": In(1)}).flip(),
                         Signature({"a": Out(1)}))

    def test_repr(self):
        sig = Signature({"a": In(1)}).flip()
        self.assertEqual(repr(sig), "Signature({'a': In(1)}).flip()")

    def test_getattr_setattr(self):
        class S(Signature):
            def __init__(self):
                super().__init__({})
                self.x = 1

            def f(self2):
                self.assertIsInstance(self2, FlippedSignature)
                return "f()"
        sig = S()
        fsig = sig.flip()
        self.assertEqual(fsig.x, 1)
        self.assertEqual(fsig.f(), "f()")
        fsig.y = 2
        self.assertEqual(sig.y, 2)


class InterfaceTestCase(unittest.TestCase):
    pass


class FlippedInterfaceTestCase(unittest.TestCase):
    def test_basic(self):
        sig = Signature({"a": In(1)})
        intf = sig.create()
        self.assertTrue(sig.is_compliant(intf))
        self.assertIs(intf.signature, sig)
        tintf = flipped(intf)
        self.assertEqual(tintf.signature, intf.signature.flip())
        self.assertEqual(tintf, flipped(intf))
        self.assertRegex(repr(tintf),
            r"^flipped\(<.+?\.Interface object at .+>\)$")
        self.assertIs(flipped(tintf), intf)

    def test_getattr_setattr(self):
        class I(Interface):
            signature = Signature({})

            def __init__(self):
                self.x = 1

            def f(self2):
                self.assertIsInstance(self2, FlippedInterface)
                return "f()"
        intf = I()
        tintf = flipped(intf)
        self.assertEqual(tintf.x, 1)
        self.assertEqual(tintf.f(), "f()")
        tintf.y = 2
        self.assertEqual(intf.y, 2)

    def test_flipped_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^flipped\(\) can only flip an interface object, not Signature\({}\)$"):
            flipped(Signature({}))


class ConnectTestCase(unittest.TestCase):
    def test_arg_handles_and_signature_attr(self):
        m = Module()
        with self.assertRaisesRegex(AttributeError,
                r"^Argument 0 must have a 'signature' attribute$"):
            connect(m, object())
        with self.assertRaisesRegex(AttributeError,
                r"^Argument 'x' must have a 'signature' attribute$"):
            connect(m, x=object())

    def test_signature_type(self):
        m = Module()
        with self.assertRaisesRegex(TypeError,
                r"^Signature of argument 0 must be a signature, not 1$"):
            connect(m, NS(signature=1))

    def test_signature_compliant(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Argument 0 does not match its signature:\n"
                r"- 'arg0' does not have an attribute 'a'$"):
            connect(m, NS(signature=Signature({"a": In(1)})))

    def test_signature_freeze(self):
        m = Module()
        intf = NS(signature=Signature({}))
        connect(m, intf)
        self.assertTrue(intf.signature.frozen)

    def test_member_missing(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Member 'b' is present in 'q', but not in 'p'$"):
            connect(m,
                    p=NS(signature=Signature({"a": In(1)}),
                         a=Signal()),
                    q=NS(signature=Signature({"a": In(1), "b": Out(1)}),
                         a=Signal(), b=Signal()))
        with self.assertRaisesRegex(ConnectionError,
                r"^Member 'b' is present in 'p', but not in 'q'$"):
            connect(m,
                    p=NS(signature=Signature({"a": In(1), "b": Out(1)}),
                         a=Signal(), b=Signal()),
                    q=NS(signature=Signature({"a": In(1)}),
                         a=Signal()))

    def test_signature_to_port(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Cannot connect signature member\(s\) 'p\.a' with port member\(s\) 'q\.a'$"):
            connect(m,
                    p=NS(signature=Signature({"a": Out(Signature({}))}),
                         a=NS(signature=Signature({}))),
                    q=NS(signature=Signature({"a": In(1)}),
                         a=Signal()))

    def test_shape_mismatch(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Cannot connect the member 'q\.a' with shape unsigned\(2\) to the member 'p\.a' "
                r"with shape unsigned\(1\) because the shape widths \(2 and 1\) do not match$"):
            connect(m,
                    p=NS(signature=Signature({"a": Out(1)}),
                         a=Signal()),
                    q=NS(signature=Signature({"a": In(2)}),
                         a=Signal(2)))

    def test_shape_mismatch_enum(self):
        class Cycle(enum.Enum, shape=2):
            READ  = 0
            WRITE = 1

        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Cannot connect the member 'q\.a' with shape unsigned\(2\) \(<enum 'Cycle'>\) "
                r"to the member 'p\.a' with shape unsigned\(1\) because the shape widths "
                r"\(2 and 1\) do not match$"):
            connect(m,
                    p=NS(signature=Signature({"a": Out(1)}),
                         a=Signal()),
                    q=NS(signature=Signature({"a": In(Cycle)}),
                         a=Signal(Cycle)))

    def test_reset_mismatch(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Cannot connect together the member 'q\.a' with reset value 1 and the member "
                r"'p\.a' with reset value 0 because the reset values do not match$"):
            connect(m,
                    p=NS(signature=Signature({"a": Out(1, reset=0)}),
                         a=Signal()),
                    q=NS(signature=Signature({"a": In(1, reset=1)}),
                         a=Signal(reset=1)))

    def test_reset_none_match(self):
        m = Module()
        connect(m,
                p=NS(signature=Signature({"a": Out(1, reset=0)}),
                     a=Signal()),
                q=NS(signature=Signature({"a": In(1)}),
                     a=Signal()))

    def test_out_to_out(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Cannot connect several output members 'p\.a', 'q\.a' together$"):
            connect(m,
                    p=NS(signature=Signature({"a": Out(1)}),
                         a=Signal()),
                    q=NS(signature=Signature({"a": Out(1)}),
                         a=Signal()))

    def test_out_to_const_in(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Cannot connect to the input member 'q\.a' that has a constant value 0$"):
            connect(m,
                    p=NS(signature=Signature({"a": Out(1)}),
                         a=Signal()),
                    q=NS(signature=Signature({"a": In(1)}),
                         a=Const(0)))

    def test_const_out_to_const_in_value_mismatch(self):
        m = Module()
        with self.assertRaisesRegex(ConnectionError,
                r"^Cannot connect input member 'q\.a' that has a constant value 0 to an output "
                r"member 'p\.a' that has a differing constant value 1$"):
            connect(m,
                    p=NS(signature=Signature({"a": Out(1)}),
                         a=Const(1)),
                    q=NS(signature=Signature({"a": In(1)}),
                         a=Const(0)))

    def test_simple_bus(self):
        class Cycle(enum.Enum):
            IDLE  = 0
            READ  = 1
            WRITE = 2
        sig = Signature({
            "cycle":  Out(Cycle),
            "addr":   Out(16),
            "r_data": In(32),
            "w_data": Out(32),
        })

        src = sig.create(path=('src',))
        snk = sig.flip().create(path=('snk',))

        m = Module()
        connect(m, src=src, snk=snk)
        self.assertEqual([repr(stmt) for stmt in m._statements], [
            '(eq (sig snk__addr) (sig src__addr))',
            '(eq (sig snk__cycle) (sig src__cycle))',
            '(eq (sig src__r_data) (sig snk__r_data))',
            '(eq (sig snk__w_data) (sig src__w_data))'
        ])

    def test_const_in_out(self):
        m = Module()
        connect(m,
                p=NS(signature=Signature({"a": Out(1)}),
                     a=Const(1)),
                q=NS(signature=Signature({"a": In(1)}),
                     a=Const(1)))
        self.assertEqual(m._statements, [])

    def test_nested(self):
        m = Module()
        connect(m,
                p=NS(signature=Signature({"a": Out(Signature({"f": Out(1)}))}),
                     a=NS(f=Signal(name='p__a'))),
                q=NS(signature=Signature({"a": In(Signature({"f": Out(1)}))}),
                     a=NS(f=Signal(name='q__a'))))
        self.assertEqual([repr(stmt) for stmt in m._statements], [
            '(eq (sig q__a) (sig p__a))'
        ])

    def test_dimension(self):
        sig = Signature({"a": Out(1).array(2)})

        m = Module()
        connect(m, p=sig.create(path=('p',)), q=sig.flip().create(path=('q',)))
        self.assertEqual([repr(stmt) for stmt in m._statements], [
            '(eq (sig q__a__0) (sig p__a__0))',
            '(eq (sig q__a__1) (sig p__a__1))'
        ])

    def test_dimension_multi(self):
        sig = Signature({"a": Out(1).array(1).array(1)})

        m = Module()
        connect(m, p=sig.create(path=('p',)), q=sig.flip().create(path=('q',)))
        self.assertEqual([repr(stmt) for stmt in m._statements], [
            '(eq (sig q__a__0__0) (sig p__a__0__0))',
        ])


class ComponentTestCase(unittest.TestCase):
    def test_basic(self):
        class C(Component):
            sig : Out(2)

        c = C()
        self.assertEqual(c.signature, Signature({"sig": Out(2)}))
        self.assertIsInstance(c.sig, Signal)
        self.assertEqual(c.sig.shape(), unsigned(2))

    def test_non_member_annotations(self):
        class C(Component):
            sig : Out(2)
            foo : int

        c = C()
        self.assertEqual(c.signature, Signature({"sig": Out(2)}))

    def test_private_member_annotations(self):
        class C(Component):
            sig_pub : Out(2)
            _sig_priv : Out(2)

        c = C()
        self.assertEqual(c.signature, Signature({"sig_pub": Out(2)}))

    def test_no_annotations(self):
        class C(Component):
            pass

        with self.assertRaisesRegex(NotImplementedError,
                r"^Component '.+?\.C' does not have signature member annotations$"):
            C()

    def test_would_overwrite_field(self):
        class C(Component):
            sig : Out(2)

            def __init__(self):
                self.sig = 1
                super().__init__()

        with self.assertRaisesRegex(NameError,
                r"^Cannot initialize attribute for signature member 'sig' because an attribute "
                r"with the same name already exists$"):
            C()

    def test_missing_in_out_warning(self):
        class C1(Component):
            prt1 : In(1)
            sig2 : Signal

        with self.assertWarnsRegex(SyntaxWarning,
                r"^Component '.+\.C1' has an annotation 'sig2: Signal', which is not a signature "
                r"member; did you mean 'sig2: In\(Signal\)' or 'sig2: Out\(Signal\)'\?$"):
            C1().signature

        class C2(Component):
            prt1 : In(1)
            sig2 : Signature({})

        with self.assertWarnsRegex(SyntaxWarning,
                r"^Component '.+\.C2' has an annotation 'sig2: Signature\({}\)', which is not "
                r"a signature member; did you mean 'sig2: In\(Signature\({}\)\)' or "
                r"'sig2: Out\(Signature\({}\)\)'\?$"):
            C2().signature

        class MockValueCastable(ValueCastable):
            def shape(self): pass
            @ValueCastable.lowermethod
            def as_value(self): pass

        class C3(Component):
            prt1 : In(1)
            val2 : MockValueCastable

        with self.assertWarnsRegex(SyntaxWarning,
                r"^Component '.+\.C3' has an annotation 'val2: MockValueCastable', which is not "
                r"a signature member; did you mean 'val2: In\(MockValueCastable\)' or "
                r"'val2: Out\(MockValueCastable\)'\?$"):
            C3().signature

    def test_bug_882(self):
        class PageBuffer(Component):
            rand: Signature({}).flip()
            other: Out(1)

        with self.assertWarnsRegex(SyntaxWarning,
                r"^Component '.+\.PageBuffer' has an annotation 'rand: Signature\({}\)\.flip\(\)', "
                r"which is not a signature member; did you mean "
                r"'rand: In\(Signature\({}\)\.flip\(\)\)' or "
                r"'rand: Out\(Signature\({}\)\.flip\(\)\)'\?$"):
            PageBuffer()
