from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable

from ..tools import flatten
from .ast import *
from .ast import _StatementList
from .cd import *
from .ir import *
from .rec import *


__all__ = ["ValueVisitor", "ValueTransformer",
           "StatementVisitor", "StatementTransformer",
           "FragmentTransformer",
           "DomainRenamer", "DomainLowerer",
           "SampleDomainInjector", "SampleLowerer",
           "SwitchCleaner", "LHSGroupAnalyzer", "LHSGroupFilter",
           "ResetInserter", "CEInserter"]


class ValueVisitor(metaclass=ABCMeta):
    @abstractmethod
    def on_Const(self, value):
        pass # :nocov:

    @abstractmethod
    def on_AnyConst(self, value):
        pass # :nocov:

    @abstractmethod
    def on_AnySeq(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Signal(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Record(self, value):
        pass # :nocov:

    @abstractmethod
    def on_ClockSignal(self, value):
        pass # :nocov:

    @abstractmethod
    def on_ResetSignal(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Operator(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Slice(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Part(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Cat(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Repl(self, value):
        pass # :nocov:

    @abstractmethod
    def on_ArrayProxy(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Sample(self, value):
        pass # :nocov:

    def on_unknown_value(self, value):
        raise TypeError("Cannot transform value '{!r}'".format(value)) # :nocov:

    def on_value(self, value):
        if type(value) is Const:
            new_value = self.on_Const(value)
        elif type(value) is AnyConst:
            new_value = self.on_AnyConst(value)
        elif type(value) is AnySeq:
            new_value = self.on_AnySeq(value)
        elif type(value) is Signal:
            new_value = self.on_Signal(value)
        elif type(value) is Record:
            new_value = self.on_Record(value)
        elif type(value) is ClockSignal:
            new_value = self.on_ClockSignal(value)
        elif type(value) is ResetSignal:
            new_value = self.on_ResetSignal(value)
        elif type(value) is Operator:
            new_value = self.on_Operator(value)
        elif type(value) is Slice:
            new_value = self.on_Slice(value)
        elif type(value) is Part:
            new_value = self.on_Part(value)
        elif isinstance(value, Cat):
            # Uses `isinstance()` and not `type() is` because nmigen.compat requires it.
            new_value = self.on_Cat(value)
        elif type(value) is Repl:
            new_value = self.on_Repl(value)
        elif type(value) is ArrayProxy:
            new_value = self.on_ArrayProxy(value)
        elif type(value) is Sample:
            new_value = self.on_Sample(value)
        else:
            new_value = self.on_unknown_value(value)
        if isinstance(new_value, Value):
            new_value.src_loc = value.src_loc
        return new_value

    def __call__(self, value):
        return self.on_value(value)


class ValueTransformer(ValueVisitor):
    def on_Const(self, value):
        return value

    def on_AnyConst(self, value):
        return value

    def on_AnySeq(self, value):
        return value

    def on_Signal(self, value):
        return value

    def on_Record(self, value):
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
        return Cat(self.on_value(o) for o in value.parts)

    def on_Repl(self, value):
        return Repl(self.on_value(value.value), value.count)

    def on_ArrayProxy(self, value):
        return ArrayProxy([self.on_value(elem) for elem in value._iter_as_values()],
                          self.on_value(value.index))

    def on_Sample(self, value):
        return Sample(self.on_value(value.value), value.clocks, value.domain)


class StatementVisitor(metaclass=ABCMeta):
    @abstractmethod
    def on_Assign(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_Assert(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_Assume(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_Switch(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_statements(self, stmts):
        pass # :nocov:

    def on_unknown_statement(self, stmt):
        raise TypeError("Cannot transform statement '{!r}'".format(stmt)) # :nocov:

    def on_statement(self, stmt):
        if type(stmt) is Assign:
            new_stmt = self.on_Assign(stmt)
        elif type(stmt) is Assert:
            new_stmt = self.on_Assert(stmt)
        elif type(stmt) is Assume:
            new_stmt = self.on_Assume(stmt)
        elif isinstance(stmt, Switch):
            # Uses `isinstance()` and not `type() is` because nmigen.compat requires it.
            new_stmt = self.on_Switch(stmt)
        elif isinstance(stmt, Iterable):
            new_stmt = self.on_statements(stmt)
        else:
            new_stmt = self.on_unknown_statement(stmt)
        if hasattr(stmt, "src_loc") and hasattr(new_stmt, "src_loc"):
            new_stmt.src_loc = stmt.src_loc
        return new_stmt

    def __call__(self, value):
        return self.on_statement(value)


class StatementTransformer(StatementVisitor):
    def on_value(self, value):
        return value

    def on_Assign(self, stmt):
        return Assign(self.on_value(stmt.lhs), self.on_value(stmt.rhs))

    def on_Assert(self, stmt):
        return Assert(self.on_value(stmt.test), _check=stmt._check, _en=stmt._en)

    def on_Assume(self, stmt):
        return Assume(self.on_value(stmt.test), _check=stmt._check, _en=stmt._en)

    def on_Switch(self, stmt):
        cases = OrderedDict((k, self.on_statement(s)) for k, s in stmt.cases.items())
        return Switch(self.on_value(stmt.test), cases)

    def on_statements(self, stmts):
        return _StatementList(flatten(self.on_statement(stmt) for stmt in stmts))


class FragmentTransformer:
    def map_subfragments(self, fragment, new_fragment):
        for subfragment, name in fragment.subfragments:
            new_fragment.add_subfragment(self(subfragment), name)

    def map_ports(self, fragment, new_fragment):
        for port, dir in fragment.ports.items():
            new_fragment.add_ports(port, dir=dir)

    def map_named_ports(self, fragment, new_fragment):
        if hasattr(self, "on_value"):
            for name, value in fragment.named_ports.items():
                new_fragment.named_ports[name] = self.on_value(value)
        else:
            new_fragment.named_ports = OrderedDict(fragment.named_ports.items())

    def map_domains(self, fragment, new_fragment):
        for domain in fragment.iter_domains():
            new_fragment.add_domains(fragment.domains[domain])

    def map_statements(self, fragment, new_fragment):
        if hasattr(self, "on_statement"):
            new_fragment.add_statements(map(self.on_statement, fragment.statements))
        else:
            new_fragment.add_statements(fragment.statements)

    def map_drivers(self, fragment, new_fragment):
        for domain, signal in fragment.iter_drivers():
            new_fragment.add_driver(signal, domain)

    def on_fragment(self, fragment):
        if isinstance(fragment, Instance):
            new_fragment = Instance(fragment.type)
            new_fragment.parameters = OrderedDict(fragment.parameters)
            self.map_named_ports(fragment, new_fragment)
        else:
            new_fragment = Fragment()
            new_fragment.flatten = fragment.flatten
        self.map_ports(fragment, new_fragment)
        self.map_subfragments(fragment, new_fragment)
        self.map_domains(fragment, new_fragment)
        self.map_statements(fragment, new_fragment)
        self.map_drivers(fragment, new_fragment)
        return new_fragment

    def __call__(self, value):
        return self.on_fragment(value)


class DomainRenamer(FragmentTransformer, ValueTransformer, StatementTransformer):
    def __init__(self, domain_map):
        if isinstance(domain_map, str):
            domain_map = {"sync": domain_map}
        self.domain_map = OrderedDict(domain_map)

    def on_ClockSignal(self, value):
        if value.domain in self.domain_map:
            return ClockSignal(self.domain_map[value.domain])
        return value

    def on_ResetSignal(self, value):
        if value.domain in self.domain_map:
            return ResetSignal(self.domain_map[value.domain])
        return value

    def map_domains(self, fragment, new_fragment):
        for domain in fragment.iter_domains():
            cd = fragment.domains[domain]
            if domain in self.domain_map:
                if cd.name == domain:
                    # Rename the actual ClockDomain object.
                    cd.rename(self.domain_map[domain])
                else:
                    assert cd.name == self.domain_map[domain]
            new_fragment.add_domains(cd)

    def map_drivers(self, fragment, new_fragment):
        for domain, signals in fragment.drivers.items():
            if domain in self.domain_map:
                domain = self.domain_map[domain]
            for signal in signals:
                new_fragment.add_driver(signal, domain)


class DomainLowerer(FragmentTransformer, ValueTransformer, StatementTransformer):
    def __init__(self, domains):
        self.domains = domains

    def _resolve(self, domain, context):
        if domain not in self.domains:
            raise DomainError("Signal {!r} refers to nonexistent domain '{}'"
                              .format(context, domain))
        return self.domains[domain]

    def map_drivers(self, fragment, new_fragment):
        for domain, signal in fragment.iter_drivers():
            new_fragment.add_driver(self.on_value(signal), domain)

    def on_ClockSignal(self, value):
        cd = self._resolve(value.domain, value)
        return cd.clk

    def on_ResetSignal(self, value):
        cd = self._resolve(value.domain, value)
        if cd.rst is None:
            if value.allow_reset_less:
                return Const(0)
            else:
                raise DomainError("Signal {!r} refers to reset of reset-less domain '{}'"
                                  .format(value, value.domain))
        return cd.rst


class SampleDomainInjector(ValueTransformer, StatementTransformer):
    def __init__(self, domain):
        self.domain = domain

    def on_Sample(self, value):
        if value.domain is not None:
            return value
        return Sample(value.value, value.clocks, self.domain)

    def __call__(self, stmts):
        return self.on_statement(stmts)


class SampleLowerer(FragmentTransformer, ValueTransformer, StatementTransformer):
    def __init__(self):
        self.sample_cache = ValueDict()
        self.sample_stmts = OrderedDict()

    def _name_reset(self, value):
        if isinstance(value, Const):
            return "c${}".format(value.value), value.value
        elif isinstance(value, Signal):
            return "s${}".format(value.name), value.reset
        elif isinstance(value, ClockSignal):
            return "clk", 0
        elif isinstance(value, ResetSignal):
            return "rst", 1
        else:
            raise NotImplementedError # :nocov:

    def on_Sample(self, value):
        if value in self.sample_cache:
            return self.sample_cache[value]

        if value.clocks == 0:
            sample = value.value
        else:
            assert value.domain is not None
            sampled_name, sampled_reset = self._name_reset(value.value)
            name = "$sample${}${}${}".format(sampled_name, value.domain, value.clocks)
            sample = Signal.like(value.value, name=name, reset_less=True, reset=sampled_reset)
            sample.attrs["nmigen.sample_reg"] = True

            prev_sample = self.on_Sample(Sample(value.value, value.clocks - 1, value.domain))
            if value.domain not in self.sample_stmts:
                self.sample_stmts[value.domain] = []
            self.sample_stmts[value.domain].append(sample.eq(prev_sample))

        self.sample_cache[value] = sample
        return sample

    def on_fragment(self, fragment):
        new_fragment = super().on_fragment(fragment)
        for domain, stmts in self.sample_stmts.items():
            new_fragment.add_statements(stmts)
            for stmt in stmts:
                new_fragment.add_driver(stmt.lhs, domain)
        return new_fragment


class SwitchCleaner(StatementVisitor):
    def on_Assign(self, stmt):
        return stmt

    on_Assert = on_Assign

    on_Assume = on_Assign

    def on_Switch(self, stmt):
        cases = OrderedDict((k, self.on_statement(s)) for k, s in stmt.cases.items())
        if any(len(s) for s in cases.values()):
            return Switch(stmt.test, cases)

    def on_statements(self, stmts):
        stmts = flatten(self.on_statement(stmt) for stmt in stmts)
        return _StatementList(stmt for stmt in stmts if stmt is not None)


class LHSGroupAnalyzer(StatementVisitor):
    def __init__(self):
        self.signals = SignalDict()
        self.unions  = OrderedDict()

    def find(self, signal):
        if signal not in self.signals:
            self.signals[signal] = len(self.signals)
        group = self.signals[signal]
        while group in self.unions:
            group = self.unions[group]
        self.signals[signal] = group
        return group

    def unify(self, root, *leaves):
        root_group = self.find(root)
        for leaf in leaves:
            leaf_group = self.find(leaf)
            if root_group == leaf_group:
                continue
            self.unions[leaf_group] = root_group

    def groups(self):
        groups = OrderedDict()
        for signal in self.signals:
            group = self.find(signal)
            if group not in groups:
                groups[group] = SignalSet()
            groups[group].add(signal)
        return groups

    def on_Assign(self, stmt):
        self.unify(*stmt._lhs_signals())

    on_Assert = on_Assign

    on_Assume = on_Assign

    def on_Switch(self, stmt):
        for case_stmts in stmt.cases.values():
            self.on_statements(case_stmts)

    def on_statements(self, stmts):
        for stmt in stmts:
            self.on_statement(stmt)

    def __call__(self, stmts):
        self.on_statements(stmts)
        return self.groups()


class LHSGroupFilter(SwitchCleaner):
    def __init__(self, signals):
        self.signals = signals

    def on_Assign(self, stmt):
        # The invariant provided by LHSGroupAnalyzer is that all signals that ever appear together
        # on LHS are a part of the same group, so it is sufficient to check any of them.
        any_lhs_signal = next(iter(stmt.lhs._lhs_signals()))
        if any_lhs_signal in self.signals:
            return stmt

    def on_Assert(self, stmt):
        any_lhs_signal = next(iter(stmt._lhs_signals()))
        if any_lhs_signal in self.signals:
            return stmt

    on_Assume = on_Assert


class _ControlInserter(FragmentTransformer):
    def __init__(self, controls):
        if isinstance(controls, Value):
            controls = {"sync": controls}
        self.controls = OrderedDict(controls)

    def on_fragment(self, fragment):
        new_fragment = super().on_fragment(fragment)
        for domain, signals in fragment.drivers.items():
            if domain is None or domain not in self.controls:
                continue
            self._insert_control(new_fragment, domain, signals)
        return new_fragment

    def _insert_control(self, fragment, domain, signals):
        raise NotImplementedError # :nocov:


class ResetInserter(_ControlInserter):
    def _insert_control(self, fragment, domain, signals):
        stmts = [s.eq(Const(s.reset, s.nbits)) for s in signals if not s.reset_less]
        fragment.add_statements(Switch(self.controls[domain], {1: stmts}))


class CEInserter(_ControlInserter):
    def _insert_control(self, fragment, domain, signals):
        stmts = [s.eq(s) for s in signals]
        fragment.add_statements(Switch(self.controls[domain], {0: stmts}))
