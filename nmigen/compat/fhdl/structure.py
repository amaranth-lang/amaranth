from collections import OrderedDict

from ...tools import deprecated
from ...fhdl import ast
from ...fhdl.ast import DUID, Value, Signal, Mux, Cat, Repl, Const, C, ClockSignal, ResetSignal
from ...fhdl.cd import ClockDomain


__all__ = ["DUID", "wrap", "Mux", "Cat", "Replicate", "Constant", "C", "Signal", "ClockSignal",
           "ResetSignal", "If", "Case", "Array", "ClockDomain",
           "SPECIAL_INPUT", "SPECIAL_OUTPUT", "SPECIAL_INOUT"]


@deprecated("instead of `wrap`, use `Value.wrap`")
def wrap(v):
    return Value.wrap(v)


@deprecated("instead of `Replicate`, use `Repl`")
def Replicate(v, n):
    return Repl(v, n)


@deprecated("instead of `Constant`, use `Const`")
def Constant(value, bits_sign=None):
    return Const(value, bits_sign)


class If(ast.Switch):
    @deprecated("instead of `If(cond, ...)`, use `with m.If(cond): ...`")
    def __init__(self, cond, *stmts):
        super().__init__(cond, {"1": ast.Statement.wrap(stmts)})

    @deprecated("instead of `.Elif(cond, ...)`, use `with m.Elif(cond): ...`")
    def Elif(self, cond, *stmts):
        self.cases = OrderedDict(("-" + k, v) for k, v in self.cases.items())
        self.cases["1" + "-" * len(self.test)] = ast.Statement.wrap(stmts)
        self.test = Cat(self.test, cond)
        return self

    @deprecated("instead of `.Else(...)`, use `with m.Else(): ...`")
    def Else(self, *stmts):
        self.cases["-" * len(self.test)] = ast.Statement.wrap(stmts)
        return self


class Case(ast.Switch):
    @deprecated("instead of `Case(test, ...)`, use `with m.Case(test, ...):`")
    def __init__(self, test, cases):
        new_cases = []
        for k, v in cases.items():
            if k == "default":
                k = "-" * len(ast.Value.wrap(test))
            new_cases.append((k, v))
        super().__init__(test, OrderedDict(new_cases))

    def makedefault(self, key=None):
        raise NotImplementedError


def Array(*args):
    raise NotImplementedError


(SPECIAL_INPUT, SPECIAL_OUTPUT, SPECIAL_INOUT) = range(3)
