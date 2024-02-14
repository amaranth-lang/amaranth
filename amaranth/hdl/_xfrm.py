from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable

from .._utils import flatten
from .. import tracer
from ._ast import *
from ._ast import _StatementList, AnyValue, Property
from ._cd import *
from ._ir import *
from ._mem import MemoryInstance


__all__ = ["ValueVisitor", "ValueTransformer",
           "StatementVisitor", "StatementTransformer",
           "FragmentTransformer",
           "TransformedElaboratable",
           "DomainCollector", "DomainRenamer", "DomainLowerer",
           "ResetInserter", "EnableInserter", "AssignmentLegalizer"]


class ValueVisitor(metaclass=ABCMeta):
    @abstractmethod
    def on_Const(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Signal(self, value):
        pass # :nocov:

    @abstractmethod
    def on_ClockSignal(self, value):
        pass # :nocov:

    @abstractmethod
    def on_ResetSignal(self, value):
        pass # :nocov:

    @abstractmethod
    def on_AnyValue(self, value):
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
    def on_ArrayProxy(self, value):
        pass # :nocov:

    @abstractmethod
    def on_Initial(self, value):
        pass # :nocov:

    def on_unknown_value(self, value):
        raise TypeError(f"Cannot transform value {value!r}") # :nocov:

    def replace_value_src_loc(self, value, new_value):
        return True

    def on_value(self, value):
        if type(value) is Const:
            new_value = self.on_Const(value)
        elif type(value) is Signal:
            new_value = self.on_Signal(value)
        elif type(value) is ClockSignal:
            new_value = self.on_ClockSignal(value)
        elif type(value) is ResetSignal:
            new_value = self.on_ResetSignal(value)
        elif type(value) is AnyValue:
            new_value = self.on_AnyValue(value)
        elif type(value) is Operator:
            new_value = self.on_Operator(value)
        elif type(value) is Slice:
            new_value = self.on_Slice(value)
        elif type(value) is Part:
            new_value = self.on_Part(value)
        elif type(value) is Cat:
            new_value = self.on_Cat(value)
        elif type(value) is ArrayProxy:
            new_value = self.on_ArrayProxy(value)
        elif type(value) is Initial:
            new_value = self.on_Initial(value)
        else:
            new_value = self.on_unknown_value(value)
        if isinstance(new_value, Value) and self.replace_value_src_loc(value, new_value):
            new_value.src_loc = value.src_loc
        return new_value

    def __call__(self, value):
        return self.on_value(value)


class ValueTransformer(ValueVisitor):
    def on_Const(self, value):
        return value

    def on_Signal(self, value):
        return value

    def on_ClockSignal(self, value):
        return value

    def on_ResetSignal(self, value):
        return value

    def on_AnyValue(self, value):
        return value

    def on_Operator(self, value):
        return Operator(value.operator, [self.on_value(o) for o in value.operands])

    def on_Slice(self, value):
        return Slice(self.on_value(value.value), value.start, value.stop)

    def on_Part(self, value):
        return Part(self.on_value(value.value), self.on_value(value.offset),
                    value.width, value.stride)

    def on_Cat(self, value):
        return Cat(self.on_value(o) for o in value.parts)

    def on_ArrayProxy(self, value):
        return ArrayProxy([self.on_value(elem) for elem in value._iter_as_values()],
                          self.on_value(value.index))

    def on_Initial(self, value):
        return value


class StatementVisitor(metaclass=ABCMeta):
    @abstractmethod
    def on_Assign(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_Property(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_Switch(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_statements(self, stmts):
        pass # :nocov:

    def on_unknown_statement(self, stmt):
        raise TypeError(f"Cannot transform statement {stmt!r}") # :nocov:

    def replace_statement_src_loc(self, stmt, new_stmt):
        return True

    def on_statement(self, stmt):
        if type(stmt) is Assign:
            new_stmt = self.on_Assign(stmt)
        elif type(stmt) is Property:
            new_stmt = self.on_Property(stmt)
        elif type(stmt) is Switch:
            new_stmt = self.on_Switch(stmt)
        elif isinstance(stmt, Iterable):
            new_stmt = self.on_statements(stmt)
        else:
            new_stmt = self.on_unknown_statement(stmt)
        if isinstance(new_stmt, Statement) and self.replace_statement_src_loc(stmt, new_stmt):
            new_stmt.src_loc = stmt.src_loc
            if isinstance(new_stmt, Switch) and isinstance(stmt, Switch):
                new_stmt.case_src_locs = stmt.case_src_locs
        if isinstance(new_stmt, Property):
            new_stmt._MustUse__used = True
        return new_stmt

    def __call__(self, stmt):
        return self.on_statement(stmt)


class StatementTransformer(StatementVisitor):
    def on_value(self, value):
        return value

    def on_Assign(self, stmt):
        return Assign(self.on_value(stmt.lhs), self.on_value(stmt.rhs))

    def on_Property(self, stmt):
        return Property(stmt.kind, self.on_value(stmt.test), name=stmt.name)

    def on_Switch(self, stmt):
        cases = OrderedDict((k, self.on_statement(s)) for k, s in stmt.cases.items())
        return Switch(self.on_value(stmt.test), cases)

    def on_statements(self, stmts):
        return _StatementList(flatten(self.on_statement(stmt) for stmt in stmts))


class FragmentTransformer:
    def map_subfragments(self, fragment, new_fragment):
        for subfragment, name, src_loc in fragment.subfragments:
            new_fragment.add_subfragment(self(subfragment), name, src_loc=src_loc)

    def map_ports(self, fragment, new_fragment):
        for port, dir in fragment.ports.items():
            new_fragment.add_ports(port, dir=dir)

    def map_named_ports(self, fragment, new_fragment):
        if hasattr(self, "on_value"):
            for name, (value, dir) in fragment.named_ports.items():
                new_fragment.named_ports[name] = self.on_value(value), dir
        else:
            new_fragment.named_ports = OrderedDict(fragment.named_ports.items())

    def map_domains(self, fragment, new_fragment):
        for domain in fragment.iter_domains():
            new_fragment.add_domains(fragment.domains[domain])

    def map_statements(self, fragment, new_fragment):
        if hasattr(self, "on_statement"):
            for domain, statements in fragment.statements.items():
                new_fragment.add_statements(domain, map(self.on_statement, statements))
        else:
            for domain, statements in fragment.statements.items():
                new_fragment.add_statements(domain, statements)

    def map_drivers(self, fragment, new_fragment):
        for domain, signal in fragment.iter_drivers():
            new_fragment.add_driver(signal, domain)

    def map_memory_ports(self, fragment, new_fragment):
        if hasattr(self, "on_value"):
            for port in new_fragment._read_ports:
                port._en = self.on_value(port._en)
                port._addr = self.on_value(port._addr)
                port._data = self.on_value(port._data)
            for port in new_fragment._write_ports:
                port._en = self.on_value(port._en)
                port._addr = self.on_value(port._addr)
                port._data = self.on_value(port._data)

    def on_fragment(self, fragment):
        if isinstance(fragment, MemoryInstance):
            new_fragment = MemoryInstance(
                identity=fragment._identity,
                width=fragment._width,
                depth=fragment._depth,
                init=fragment._init,
                attrs=fragment._attrs,
                src_loc=fragment.src_loc
            )
            new_fragment._read_ports = [
                MemoryInstance._ReadPort(
                    domain=port._domain,
                    addr=port._addr,
                    data=port._data,
                    en=port._en,
                    transparent_for=port._transparent_for,
                )
                for port in fragment._read_ports
            ]
            new_fragment._write_ports = [
                MemoryInstance._WritePort(
                    domain=port._domain,
                    addr=port._addr,
                    data=port._data,
                    en=port._en,
                )
                for port in fragment._write_ports
            ]
            self.map_memory_ports(fragment, new_fragment)
        elif isinstance(fragment, Instance):
            new_fragment = Instance(fragment.type, src_loc=fragment.src_loc)
            new_fragment.parameters = OrderedDict(fragment.parameters)
            self.map_named_ports(fragment, new_fragment)
        else:
            new_fragment = Fragment(src_loc=fragment.src_loc)
            new_fragment.flatten = fragment.flatten
        new_fragment.attrs = OrderedDict(fragment.attrs)
        self.map_ports(fragment, new_fragment)
        self.map_subfragments(fragment, new_fragment)
        self.map_domains(fragment, new_fragment)
        self.map_statements(fragment, new_fragment)
        self.map_drivers(fragment, new_fragment)
        return new_fragment

    def __call__(self, value, *, src_loc_at=0):
        if isinstance(value, Fragment):
            return self.on_fragment(value)
        elif isinstance(value, TransformedElaboratable):
            value._transforms_.append(self)
            return value
        elif hasattr(value, "elaborate"):
            value = TransformedElaboratable(value, src_loc_at=1 + src_loc_at)
            value._transforms_.append(self)
            return value
        else:
            raise AttributeError(f"Object {value!r} cannot be elaborated")


class TransformedElaboratable(Elaboratable):
    def __init__(self, elaboratable, *, src_loc_at=0):
        assert hasattr(elaboratable, "elaborate")

        # Fields prefixed and suffixed with underscore to avoid as many conflicts with the inner
        # object as possible, since we're forwarding attribute requests to it.
        self._elaboratable_ = elaboratable
        self._transforms_   = []

    def __getattr__(self, attr):
        return getattr(self._elaboratable_, attr)

    def elaborate(self, platform):
        fragment = Fragment.get(self._elaboratable_, platform)
        for transform in self._transforms_:
            fragment = transform(fragment)
        return fragment


class DomainCollector(ValueVisitor, StatementVisitor):
    def __init__(self):
        self.used_domains = set()
        self.defined_domains = set()
        self._local_domains = set()

    def _add_used_domain(self, domain_name):
        if domain_name == "comb":
            return
        if domain_name in self._local_domains:
            return
        self.used_domains.add(domain_name)

    def on_ignore(self, value):
        pass

    on_Const = on_ignore
    on_Signal = on_ignore
    on_AnyValue = on_ignore

    def on_ClockSignal(self, value):
        self._add_used_domain(value.domain)

    def on_ResetSignal(self, value):
        self._add_used_domain(value.domain)

    def on_Operator(self, value):
        for o in value.operands:
            self.on_value(o)

    def on_Slice(self, value):
        self.on_value(value.value)

    def on_Part(self, value):
        self.on_value(value.value)
        self.on_value(value.offset)

    def on_Cat(self, value):
        for o in value.parts:
            self.on_value(o)

    def on_ArrayProxy(self, value):
        for elem in value._iter_as_values():
            self.on_value(elem)
        self.on_value(value.index)

    def on_Initial(self, value):
        pass

    def on_Assign(self, stmt):
        self.on_value(stmt.lhs)
        self.on_value(stmt.rhs)

    def on_Property(self, stmt):
        self.on_value(stmt.test)

    def on_Switch(self, stmt):
        self.on_value(stmt.test)
        for stmts in stmt.cases.values():
            self.on_statement(stmts)

    def on_statements(self, stmts):
        for stmt in stmts:
            self.on_statement(stmt)

    def on_fragment(self, fragment):
        if isinstance(fragment, MemoryInstance):
            for port in fragment._read_ports:
                self.on_value(port._addr)
                self.on_value(port._data)
                self.on_value(port._en)
                self._add_used_domain(port._domain)
            for port in fragment._write_ports:
                self.on_value(port._addr)
                self.on_value(port._data)
                self.on_value(port._en)
                self._add_used_domain(port._domain)

        if isinstance(fragment, Instance):
            for name, (value, dir) in fragment.named_ports.items():
                self.on_value(value)

        old_local_domains, self._local_domains = self._local_domains, set(self._local_domains)
        for domain_name, domain in fragment.domains.items():
            if domain.local:
                self._local_domains.add(domain_name)
            else:
                self.defined_domains.add(domain_name)

        for domain_name, statements in fragment.statements.items():
            self._add_used_domain(domain_name)
            self.on_statements(statements)
        for subfragment, name, src_loc in fragment.subfragments:
            self.on_fragment(subfragment)

        self._local_domains = old_local_domains

    def __call__(self, fragment):
        self.on_fragment(fragment)


class DomainRenamer(FragmentTransformer, ValueTransformer, StatementTransformer):
    def __init__(self, domain_map):
        if isinstance(domain_map, str):
            domain_map = {"sync": domain_map}
        for src, dst in domain_map.items():
            if src == "comb":
                raise ValueError(f"Domain '{src}' may not be renamed")
            if dst == "comb":
                raise ValueError(f"Domain '{src}' may not be renamed to '{dst}'")
        self.domain_map = OrderedDict(domain_map)

    def on_ClockSignal(self, value):
        if value.domain in self.domain_map:
            return ClockSignal(self.domain_map[value.domain])
        return value

    def on_ResetSignal(self, value):
        if value.domain in self.domain_map:
            return ResetSignal(self.domain_map[value.domain],
                               allow_reset_less=value.allow_reset_less)
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

    def map_statements(self, fragment, new_fragment):
        for domain, statements in fragment.statements.items():
            new_fragment.add_statements(
                self.domain_map.get(domain, domain),
                map(self.on_statement, statements)
            )

    def map_drivers(self, fragment, new_fragment):
        for domain, signals in fragment.drivers.items():
            if domain in self.domain_map:
                domain = self.domain_map[domain]
            for signal in signals:
                new_fragment.add_driver(self.on_value(signal), domain)

    def map_memory_ports(self, fragment, new_fragment):
        super().map_memory_ports(fragment, new_fragment)
        for port in new_fragment._read_ports:
            if port._domain in self.domain_map:
                port._domain = self.domain_map[port._domain]
        for port in new_fragment._write_ports:
            if port._domain in self.domain_map:
                port._domain = self.domain_map[port._domain]


class DomainLowerer(FragmentTransformer, ValueTransformer, StatementTransformer):
    def __init__(self, domains=None):
        self.domains = domains

    def _resolve(self, domain, context):
        if domain not in self.domains:
            raise DomainError("Signal {!r} refers to nonexistent domain '{}'"
                              .format(context, domain))
        return self.domains[domain]

    def map_drivers(self, fragment, new_fragment):
        for domain, signal in fragment.iter_drivers():
            new_fragment.add_driver(self.on_value(signal), domain)

    def replace_value_src_loc(self, value, new_value):
        return not isinstance(value, (ClockSignal, ResetSignal))

    def on_ClockSignal(self, value):
        domain = self._resolve(value.domain, value)
        return domain.clk

    def on_ResetSignal(self, value):
        domain = self._resolve(value.domain, value)
        if domain.rst is None:
            if value.allow_reset_less:
                return Const(0)
            else:
                raise DomainError("Signal {!r} refers to reset of reset-less domain '{}'"
                                  .format(value, value.domain))
        return domain.rst

    def _insert_resets(self, fragment):
        for domain_name, signals in fragment.drivers.items():
            if domain_name == "comb":
                continue
            domain = fragment.domains[domain_name]
            if domain.rst is None:
                continue
            stmts = [signal.eq(Const(signal.init, signal.width))
                     for signal in signals if not signal.reset_less]
            fragment.add_statements(domain_name, Switch(domain.rst, {1: stmts}))

    def on_fragment(self, fragment):
        self.domains = fragment.domains
        new_fragment = super().on_fragment(fragment)
        self._insert_resets(new_fragment)
        return new_fragment


class _ControlInserter(FragmentTransformer):
    def __init__(self, controls):
        self.src_loc = None
        if isinstance(controls, Value):
            controls = {"sync": controls}
        if "comb" in controls:
            raise ValueError("Cannot add controls on the 'comb' domain")
        self.controls = OrderedDict(controls)

    def on_fragment(self, fragment):
        new_fragment = super().on_fragment(fragment)
        for domain, signals in fragment.drivers.items():
            if domain == "comb" or domain not in self.controls:
                continue
            self._insert_control(new_fragment, domain, signals)
        return new_fragment

    def _insert_control(self, fragment, domain, signals):
        raise NotImplementedError # :nocov:

    def __call__(self, value, *, src_loc_at=0):
        self.src_loc = tracer.get_src_loc(src_loc_at=src_loc_at)
        return super().__call__(value, src_loc_at=1 + src_loc_at)


class ResetInserter(_ControlInserter):
    def _insert_control(self, fragment, domain, signals):
        stmts = [s.eq(Const(s.init, s.width)) for s in signals if not s.reset_less]
        fragment.add_statements(domain, Switch(self.controls[domain], {1: stmts}, src_loc=self.src_loc))


class _PropertyEnableInserter(StatementTransformer):
    def __init__(self, en):
        self.en = en

    def on_Property(self, stmt):
        return Switch(
            self.en,
            {1: [stmt]},
            src_loc=stmt.src_loc,
        )


class EnableInserter(_ControlInserter):
    def _insert_control(self, fragment, domain, signals):
        stmts = [s.eq(s) for s in signals]
        fragment.add_statements(domain, Switch(self.controls[domain], {0: stmts}, src_loc=self.src_loc))
        fragment.statements[domain] = _PropertyEnableInserter(self.controls[domain])(fragment.statements[domain])

    def on_fragment(self, fragment):
        new_fragment = super().on_fragment(fragment)
        if isinstance(new_fragment, MemoryInstance):
            for port in new_fragment._read_ports:
                if port._domain in self.controls:
                    port._en = port._en & self.controls[port._domain]
            for port in new_fragment._write_ports:
                if port._domain in self.controls:
                    port._en = Mux(self.controls[port._domain], port._en, Const(0, len(port._en)))
        return new_fragment


class AssignmentLegalizer(FragmentTransformer, StatementTransformer):
    """Ensures all assignments in switches have one of the following on the LHS:

    - a `Signal`
    - a `Slice` with `value` that is a `Signal`
    """
    def emit_assign(self, lhs, rhs, lhs_start=0, lhs_stop=None):
        if isinstance(lhs, ArrayProxy):
            # Lower into a switch.
            cases = {}
            for idx, val in enumerate(lhs.elems):
                cases[idx] = self.emit_assign(val, rhs, lhs_start, lhs_stop)
            return [Switch(lhs.index, cases)]
        elif isinstance(lhs, Part):
            offset = lhs.offset
            width = lhs.width
            if lhs_start != 0:
                width -= lhs_start
            if lhs_stop is not None:
                width = lhs_stop - lhs_start
            cases = {}
            lhs_width = len(lhs.value)
            for idx in range(lhs_width):
                start = lhs_start + idx * lhs.stride
                if start >= lhs_width:
                    break
                stop = min(start + width, lhs_width)
                cases[idx] = self.emit_assign(lhs.value, rhs, start, stop)
            return [Switch(offset, cases)]
        elif isinstance(lhs, Slice):
            part_start = lhs_start + lhs.start
            if lhs_stop is not None:
                part_stop = lhs_stop + lhs.start
            else:
                part_stop = lhs_start + lhs.stop
            return self.emit_assign(lhs.value, rhs, part_start, part_stop)
        elif isinstance(lhs, Cat):
            # Split into several assignments.
            part_stop = 0
            res = []
            if lhs_stop is None:
                lhs_len = len(lhs) - lhs_start
            else:
                lhs_len = lhs_stop - lhs_start
            if len(rhs) < lhs_len:
                rhs |= Const(0, Shape(lhs_len, signed=rhs.shape().signed))
            for val in lhs.parts:
                part_start = part_stop
                part_len = len(val)
                part_stop = part_start + part_len
                if lhs_start >= part_stop:
                    continue
                if lhs_start < part_start:
                    part_lhs_start = 0
                    part_rhs_start = part_start - lhs_start
                else:
                    part_lhs_start = lhs_start - part_start
                    part_rhs_start = 0
                if lhs_stop is not None and lhs_stop <= part_start:
                    continue
                elif lhs_stop is None or lhs_stop >= part_stop:
                    part_lhs_stop = None
                else:
                    part_lhs_stop = lhs_stop - part_start
                res += self.emit_assign(val, rhs[part_rhs_start:], part_lhs_start, part_lhs_stop)
            return res
        elif isinstance(lhs, Signal):
            # Already ok.
            if lhs_start != 0 or lhs_stop is not None:
                return [Assign(lhs[lhs_start:lhs_stop], rhs)]
            else:
                return [Assign(lhs, rhs)]
        elif isinstance(lhs, Operator):
            assert lhs.operator in ('u', 's')
            return self.emit_assign(lhs.operands[0], rhs, lhs_start, lhs_stop)
        else:
            raise TypeError

    def on_Assign(self, stmt):
        return self.emit_assign(stmt.lhs, stmt.rhs)
