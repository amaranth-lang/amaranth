from collections import OrderedDict

from .ast import *
from .ir import *


__all__ = ["ValueTransformer", "StatementTransformer", "ResetInserter", "CEInserter"]


class ValueTransformer:
    def on_Const(self, value):
        return value

    def on_Signal(self, value):
        return value

    def on_ClockSignal(self, value):
        return value

    def on_ResetSignal(self, value):
        return value

    def on_Operator(self, value):
        return Operator(value.op, [self.on_value(o) for o in value.operands])

    def on_Slice(self, value):
        return Slice(self.on_value(value.value), value.start, value.end)

    def on_Part(self, value):
        return Part(self.on_value(value.value), self.on_value(value.offset), value.width)

    def on_Cat(self, value):
        return Cat(self.on_value(o) for o in value.operands)

    def on_Repl(self, value):
        return Repl(self.on_value(value.value), value.count)

    def on_value(self, value):
        if isinstance(value, Const):
            return self.on_Const(value)
        elif isinstance(value, Signal):
            return self.on_Signal(value)
        elif isinstance(value, ClockSignal):
            return self.on_ClockSignal(value)
        elif isinstance(value, ResetSignal):
            return self.on_ResetSignal(value)
        elif isinstance(value, Operator):
            return self.on_Operator(value)
        elif isinstance(value, Slice):
            return self.on_Slice(value)
        elif isinstance(value, Part):
            return self.on_Part(value)
        elif isinstance(value, Cat):
            return self.on_Cat(value)
        elif isinstance(value, Repl):
            return self.on_Repl(value)
        else:
            raise TypeError("Cannot transform value {!r}".format(value))

    def __call__(self, value):
        return self.on_value(value)


class StatementTransformer:
    def on_value(self, value):
        return value

    def on_Assign(self, stmt):
        return Assign(self.on_value(stmt.lhs), self.on_value(stmt.rhs))

    def on_Switch(self, stmt):
        cases = OrderedDict((k, self.on_value(v)) for k, v in stmt.cases.items())
        return Switch(self.on_value(stmt.test), cases)

    def on_statements(self, stmt):
        return list(flatten(self.on_statement(stmt) for stmt in self.on_statement(stmt)))

    def on_statement(self, stmt):
        if isinstance(stmt, Assign):
            return self.on_Assign(stmt)
        elif isinstance(stmt, Switch):
            return self.on_Switch(stmt)
        elif isinstance(stmt, (list, tuple)):
            return self.on_statements(stmt)
        else:
            raise TypeError("Cannot transform statement {!r}".format(stmt))

    def __call__(self, value):
        return self.on_statement(value)


class _ControlInserter:
    def __init__(self, controls):
        if isinstance(controls, Value):
            controls = {"sys": controls}
        self.controls = OrderedDict(controls)

    def __call__(self, fragment):
        new_fragment = Fragment()
        for subfragment, name in fragment.subfragments:
            new_fragment.add_subfragment(self(subfragment), name)
        new_fragment.add_statements(fragment.statements)
        for cd_name, signals in fragment.iter_domains():
            for signal in signals:
                new_fragment.drive(signal, cd_name)
            if cd_name is None or cd_name not in self.controls:
                continue
            self._wrap_control(new_fragment, cd_name, signals)
        return new_fragment

    def _wrap_control(self, fragment, cd_name, signals):
        raise NotImplementedError


class ResetInserter(_ControlInserter):
    def _wrap_control(self, fragment, cd_name, signals):
        stmts = [s.eq(Const(s.reset, s.nbits)) for s in signals]
        fragment.add_statements(Switch(self.controls[cd_name], {1: stmts}))


class CEInserter(_ControlInserter):
    def _wrap_control(self, fragment, cd_name, signals):
        stmts = [s.eq(s) for s in signals]
        fragment.add_statements(Switch(self.controls[cd_name], {0: stmts}))
