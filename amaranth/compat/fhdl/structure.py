import builtins
import warnings
from collections import OrderedDict

from ...utils import bits_for
from ..._utils import deprecated, extend
from ...hdl import ast
from ...hdl.ast import (DUID,
                        Shape, signed, unsigned,
                        Value, Const, C, Mux, Slice as _Slice, Part, Cat, Repl,
                        Signal as NativeSignal,
                        ClockSignal, ResetSignal,
                        Array, ArrayProxy as _ArrayProxy)
from ...hdl.cd import ClockDomain


__all__ = ["DUID", "wrap", "Mux", "Cat", "Replicate", "Constant", "C", "Signal", "ClockSignal",
           "ResetSignal", "If", "Case", "Array", "ClockDomain"]


@deprecated("instead of `wrap`, use `Value.cast`")
def wrap(v):
    return Value.cast(v)


class CompatSignal(NativeSignal):
    def __init__(self, bits_sign=None, name=None, variable=False, reset=0,
                 reset_less=False, name_override=None, min=None, max=None,
                 related=None, attr=None, src_loc_at=0, **kwargs):
        if min is not None or max is not None:
            warnings.warn("instead of `Signal(min={min}, max={max})`, "
                          "use `Signal(range({min}, {max}))`"
                          .format(min=min or 0, max=max or 2),
                          DeprecationWarning, stacklevel=2 + src_loc_at)

        if bits_sign is None:
            if min is None:
                min = 0
            if max is None:
                max = 2
            max -= 1  # make both bounds inclusive
            if min > max:
                raise ValueError("Lower bound {} should be less or equal to higher bound {}"
                                 .format(min, max + 1))
            sign = min < 0 or max < 0
            if min == max:
                bits = 0
            else:
                bits = builtins.max(bits_for(min, sign), bits_for(max, sign))
            shape = signed(bits) if sign else unsigned(bits)
        else:
            if not (min is None and max is None):
                raise ValueError("Only one of bits/signedness or bounds may be specified")
            if isinstance(bits_sign, tuple):
                shape = Shape(*bits_sign)
            else:
                shape = Shape.cast(bits_sign)

        super().__init__(shape=shape, name=name_override or name,
                         reset=reset, reset_less=reset_less,
                         attrs=attr, src_loc_at=1 + src_loc_at, **kwargs)


Signal = CompatSignal


@deprecated("instead of `Constant`, use `Const`")
def Constant(value, bits_sign=None):
    return Const(value, bits_sign)


@deprecated("instead of `Replicate(v, n)`, use `v.replicate(n)`")
def Replicate(v, n):
    return v.replicate(n)


@extend(Const)
@property
@deprecated("instead of `.nbits`, use `.width`")
def nbits(self):
    return self.width


@extend(NativeSignal)
@property
@deprecated("instead of `.nbits`, use `.width`")
def nbits(self):
    return self.width


@extend(NativeSignal)
@NativeSignal.nbits.setter
@deprecated("instead of `.nbits = x`, use `.width = x`")
def nbits(self, value):
    self.width = value


@extend(NativeSignal)
@deprecated("instead of `.part`, use `.bit_select`")
def part(self, offset, width):
    return Part(self, offset, width, src_loc_at=2)


@extend(Cat)
@property
@deprecated("instead of `.l`, use `.parts`")
def l(self):
    return self.parts


@extend(ast.Operator)
@property
@deprecated("instead of `.op`, use `.operator`")
def op(self):
    return self.operator


@extend(_ArrayProxy)
@property
@deprecated("instead `_ArrayProxy.choices`, use `ArrayProxy.elems`")
def choices(self):
    return self.elems


class If(ast.Switch):
    @deprecated("instead of `If(cond, ...)`, use `with m.If(cond): ...`")
    def __init__(self, cond, *stmts):
        cond = Value.cast(cond)
        if len(cond) != 1:
            cond = cond.bool()
        super().__init__(cond, {("1",): ast.Statement.cast(stmts)})

    @deprecated("instead of `.Elif(cond, ...)`, use `with m.Elif(cond): ...`")
    def Elif(self, cond, *stmts):
        cond = Value.cast(cond)
        if len(cond) != 1:
            cond = cond.bool()
        self.cases = OrderedDict((("-" + k,), v) for (k,), v in self.cases.items())
        self.cases[("1" + "-" * len(self.test),)] = ast.Statement.cast(stmts)
        self.test = Cat(self.test, cond)
        return self

    @deprecated("instead of `.Else(...)`, use `with m.Else(): ...`")
    def Else(self, *stmts):
        self.cases[()] = ast.Statement.cast(stmts)
        return self


class Case(ast.Switch):
    @deprecated("instead of `Case(test, { value: stmts })`, use `with m.Switch(test):` and "
                "`with m.Case(value): stmts`; instead of `\"default\": stmts`, use "
                "`with m.Case(): stmts`")
    def __init__(self, test, cases):
        new_cases = []
        default   = None
        for k, v in cases.items():
            if isinstance(k, (bool, int)):
                k = Const(k)
            if (not isinstance(k, Const)
                    and not (isinstance(k, str) and k == "default")):
                raise TypeError("Case object is not a Migen constant")
            if isinstance(k, str) and k == "default":
                default = v
                continue
            else:
                k = k.value
            new_cases.append((k, v))
        if default is not None:
            new_cases.append((None, default))
        super().__init__(test, OrderedDict(new_cases))

    @deprecated("instead of `Case(...).makedefault()`, use an explicit default case: "
                "`with m.Case(): ...`")
    def makedefault(self, key=None):
        if key is None:
            for choice in self.cases.keys():
                if (key is None
                        or (isinstance(choice, str) and choice == "default")
                        or choice > key):
                    key = choice
        elif isinstance(key, str) and key == "default":
            key = ()
        else:
            key = ("{:0{}b}".format(ast.Value.cast(key).value, len(self.test)),)
        stmts = self.cases[key]
        del self.cases[key]
        self.cases[()] = stmts
        return self
