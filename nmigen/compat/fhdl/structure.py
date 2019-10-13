from collections import OrderedDict

from ..._utils import deprecated, extend
from ...hdl import ast
from ...hdl.ast import (DUID, Value, Signal, Mux, Slice as _Slice, Cat, Repl, Const, C,
                        ClockSignal, ResetSignal,
                        Array, ArrayProxy as _ArrayProxy)
from ...hdl.cd import ClockDomain


__all__ = ["DUID", "wrap", "Mux", "Cat", "Replicate", "Constant", "C", "Signal", "ClockSignal",
           "ResetSignal", "If", "Case", "Array", "ClockDomain"]


@deprecated("instead of `wrap`, use `Value.cast`")
def wrap(v):
    return Value.cast(v)


@extend(Cat)
@property
@deprecated("instead of `Cat.l`, use `Cat.parts`")
def l(self):
    return self.parts


@deprecated("instead of `Replicate`, use `Repl`")
def Replicate(v, n):
    return Repl(v, n)


@deprecated("instead of `Constant`, use `Const`")
def Constant(value, bits_sign=None):
    return Const(value, bits_sign)


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
        super().__init__(cond, {("1",): ast.Statement.wrap(stmts)})

    @deprecated("instead of `.Elif(cond, ...)`, use `with m.Elif(cond): ...`")
    def Elif(self, cond, *stmts):
        cond = Value.cast(cond)
        if len(cond) != 1:
            cond = cond.bool()
        self.cases = OrderedDict((("-" + k,), v) for (k,), v in self.cases.items())
        self.cases[("1" + "-" * len(self.test),)] = ast.Statement.wrap(stmts)
        self.test = Cat(self.test, cond)
        return self

    @deprecated("instead of `.Else(...)`, use `with m.Else(): ...`")
    def Else(self, *stmts):
        self.cases[()] = ast.Statement.wrap(stmts)
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
            key = ("{:0{}b}".format(wrap(key).value, len(self.test)),)
        stmts = self.cases[key]
        del self.cases[key]
        self.cases[()] = stmts
        return self
