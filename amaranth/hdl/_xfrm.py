import warnings
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable

from .._utils import flatten
from .. import tracer
from ._ast import *
from ._ast import _StatementList, AnyValue
from ._cd import *
from ._ir import *
from ._mem import MemoryInstance


__all__ = ["ValueVisitor", "ValueTransformer",
           "StatementVisitor", "StatementTransformer",
           "FragmentTransformer",
           "TransformedElaboratable",
           "DomainCollector", "DomainRenamer", "DomainLowerer",
           "LHSMaskCollector",
           "ResetInserter", "EnableInserter"]


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
    def on_Concat(self, value):
        pass # :nocov:

    @abstractmethod
    def on_SwitchValue(self, value):
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
        elif type(value) is Concat:
            new_value = self.on_Concat(value)
        elif type(value) is SwitchValue:
            new_value = self.on_SwitchValue(value)
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

    def on_Concat(self, value):
        return Concat(self.on_value(o) for o in value.parts)

    def on_SwitchValue(self, value):
        return SwitchValue(self.on_value(value.test), [(patterns, self.on_value(val)) for patterns, val in value.cases])

    def on_Initial(self, value):
        return value


class StatementVisitor(metaclass=ABCMeta):
    @abstractmethod
    def on_Assign(self, stmt):
        pass # :nocov:

    @abstractmethod
    def on_Print(self, stmt):
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
        elif type(stmt) is Print:
            new_stmt = self.on_Print(stmt)
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
        if isinstance(new_stmt, (Print, Property)):
            new_stmt._MustUse__used = True
        return new_stmt

    def __call__(self, stmt):
        return self.on_statement(stmt)


class StatementTransformer(StatementVisitor):
    def on_value(self, value):
        return value

    def on_Format(self, format):
        chunks = []
        for chunk in format._chunks:
            if isinstance(chunk, str):
                chunks.append(chunk)
            else:
                value, format_spec = chunk
                chunks.append((self.on_value(value), format_spec))
        return Format._from_chunks(chunks)

    def on_Assign(self, stmt):
        return Assign(self.on_value(stmt.lhs), self.on_value(stmt.rhs))

    def on_Print(self, stmt):
        return Print(self.on_Format(stmt.message), end="")

    def on_Property(self, stmt):
        if stmt.message is None:
            message = None
        else:
            message = self.on_Format(stmt.message)
        return Property(stmt.kind, self.on_value(stmt.test), message)

    def on_Switch(self, stmt):
        cases = [(k, self.on_statement(s), l) for k, s, l in stmt.cases]
        return Switch(self.on_value(stmt.test), cases)

    def on_statements(self, stmts):
        return _StatementList(flatten(self.on_statement(stmt) for stmt in stmts))


class FragmentTransformer:
    def map_subfragments(self, fragment, new_fragment):
        for subfragment, name, src_loc in fragment.subfragments:
            new_fragment.add_subfragment(self(subfragment), name, src_loc=src_loc)

    def map_ports(self, fragment, new_fragment):
        if hasattr(self, "on_value"):
            for name, (value, dir) in fragment.ports.items():
                if isinstance(value, Value):
                    new_fragment.ports[name] = self.on_value(value), dir
                else:
                    new_fragment.ports[name] = value, dir
        else:
            new_fragment.ports = OrderedDict(fragment.ports.items())

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

    def map_domain_renames(self, fragment, new_fragment):
        new_fragment.domain_renames = dict(fragment.domain_renames)

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
                data=fragment._data,
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
            self.map_ports(fragment, new_fragment)
        elif isinstance(fragment, IOBufferInstance):
            if hasattr(self, "on_value"):
                new_fragment = IOBufferInstance(
                    port=fragment.port,
                    i=self.on_value(fragment.i) if fragment.i is not None else None,
                    o=self.on_value(fragment.o) if fragment.o is not None else None,
                    oe=self.on_value(fragment.oe) if fragment.o is not None else None,
                    src_loc=fragment.src_loc,
                )
            else:
                new_fragment = IOBufferInstance(
                    port=fragment.port,
                    i=fragment.i,
                    o=fragment.o,
                    oe=fragment.oe,
                    src_loc=fragment.src_loc,
                )
        elif isinstance(fragment, RequirePosedge):
            new_fragment = RequirePosedge(fragment._domain, src_loc=fragment.src_loc)
        else:
            new_fragment = Fragment(src_loc=fragment.src_loc)
        new_fragment.attrs = OrderedDict(fragment.attrs)
        new_fragment.origins = fragment.origins
        self.map_subfragments(fragment, new_fragment)
        self.map_domains(fragment, new_fragment)
        self.map_statements(fragment, new_fragment)
        self.map_domain_renames(fragment, new_fragment)
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

    def on_Concat(self, value):
        for o in value.parts:
            self.on_value(o)

    def on_SwitchValue(self, value):
        self.on_value(value.test)
        for patterns, val in value.cases:
            self.on_value(val)

    def on_Initial(self, value):
        pass

    def on_Format(self, format):
        for chunk in format._chunks:
            if not isinstance(chunk, str):
                value, _format_spec = chunk
                self.on_value(value)

    def on_Assign(self, stmt):
        self.on_value(stmt.lhs)
        self.on_value(stmt.rhs)

    def on_Print(self, stmt):
        self.on_Format(stmt.message)

    def on_Property(self, stmt):
        self.on_value(stmt.test)
        if stmt.message is not None:
            self.on_Format(stmt.message)

    def on_Switch(self, stmt):
        self.on_value(stmt.test)
        for _patterns, stmts, _src_loc in stmt.cases:
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
        if isinstance(fragment, RequirePosedge):
            self._add_used_domain(fragment._domain)

        if isinstance(fragment, Instance):
            for name, (value, dir) in fragment.ports.items():
                if not isinstance(value, IOValue):
                    self.on_value(value)

        if isinstance(fragment, IOBufferInstance):
            if fragment.o is not None:
                self.on_value(fragment.o)
                self.on_value(fragment.oe)
            if fragment.i is not None:
                self.on_value(fragment.i)

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

    def map_domain_renames(self, fragment, new_fragment):
        new_fragment.domain_renames = {
            src: self.domain_map.get(dst, dst)
            for src, dst in fragment.domain_renames.items()
        }
        for src, dst in self.domain_map.items():
            if src not in new_fragment.domain_renames:
                new_fragment.domain_renames[src] = dst

    def map_memory_ports(self, fragment, new_fragment):
        super().map_memory_ports(fragment, new_fragment)
        for port in new_fragment._read_ports:
            if port._domain in self.domain_map:
                port._domain = self.domain_map[port._domain]
        for port in new_fragment._write_ports:
            if port._domain in self.domain_map:
                port._domain = self.domain_map[port._domain]

    def on_fragment(self, fragment):
        new_fragment = super().on_fragment(fragment)
        if isinstance(new_fragment, RequirePosedge) and new_fragment._domain in self.domain_map:
            new_fragment._domain = self.domain_map[new_fragment._domain]
        return new_fragment


class DomainLowerer(FragmentTransformer, ValueTransformer, StatementTransformer):
    def __init__(self, domains=None):
        self.domains = domains
        self.domains_propagated_up = {}

    def _warn_on_propagation_up(self, domain, src_loc):
        if domain in self.domains_propagated_up:
            used_in, defined_in = self.domains_propagated_up[domain]
            common_prefix = []
            for u, d in zip(used_in, defined_in):
                if u == d:
                    common_prefix.append(u)
            warnings.warn_explicit(f"Domain '{domain}' is used in '{'.'.join(used_in)}', but "
                                   f"defined in '{'.'.join(defined_in)}', which will not be "
                                   f"supported in Amaranth 0.6; define the domain in "
                                   f"'{'.'.join(common_prefix)}' or one of its parents",
                                   DeprecationWarning, filename=src_loc[0], lineno=src_loc[1])

    def _resolve(self, domain, context):
        if domain not in self.domains:
            raise DomainError("Signal {!r} refers to nonexistent domain '{}'"
                              .format(context, domain))
        self._warn_on_propagation_up(domain, context.src_loc)
        return self.domains[domain]

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

    def on_fragment(self, fragment):
        self.domains = fragment.domains
        self.domains_propagated_up = fragment.domains_propagated_up
        for domain, statements in fragment.statements.items():
            self._warn_on_propagation_up(domain, statements[0].src_loc)
        if isinstance(fragment, MemoryInstance):
            for port in fragment._read_ports:
                self._warn_on_propagation_up(port._domain, fragment.src_loc)
            for port in fragment._write_ports:
                self._warn_on_propagation_up(port._domain, fragment.src_loc)
        return super().on_fragment(fragment)


class LHSMaskCollector:
    def __init__(self):
        self.lhs = SignalDict()

    def visit_stmt(self, stmt):
        if type(stmt) is Assign:
            self.visit_value(stmt.lhs, ~0)
        elif type(stmt) is Switch:
            for (_, substmt, _) in stmt.cases:
                self.visit_stmt(substmt)
        elif type(stmt) in (Property, Print):
            pass
        elif isinstance(stmt, Iterable):
            for substmt in stmt:
                self.visit_stmt(substmt)
        else:
            assert False # :nocov:

    def visit_value(self, value, mask):
        if type(value) in (Signal, ClockSignal, ResetSignal):
            mask &= (1 << len(value)) - 1
            self.lhs.setdefault(value, 0)
            self.lhs[value] |= mask
        elif type(value) is Operator:
            assert value.operator in ("s", "u")
            self.visit_value(value.operands[0], mask)
        elif type(value) is Slice:
            slice_mask = (1 << value.stop) - (1 << value.start)
            mask <<= value.start
            mask &= slice_mask
            self.visit_value(value.value, mask)
        elif type(value) is Part:
            # Could be more accurate, but if you're relying on such details, you're not seeing
            # the Light of Heaven.
            self.visit_value(value.value, ~0)
        elif type(value) is Concat:
            for part in value.parts:
                self.visit_value(part, mask)
                mask >>= len(part)
        elif type(value) is SwitchValue:
            for (_, subvalue) in value.cases:
                self.visit_value(subvalue, mask)
        else:
            assert False # :nocov:

    def chunks(self):
        for signal, mask in self.lhs.items():
            if mask == (1 << len(signal)) - 1:
                yield signal, 0, None
            else:
                start = 0
                while start < len(signal):
                    if ((mask >> start) & 1) == 0:
                        start += 1
                    else:
                        stop = start
                        while stop < len(signal) and ((mask >> stop) & 1) == 1:
                            stop += 1
                        yield (signal, start, stop)
                        start = stop

    def masks(self):
        yield from self.lhs.items()


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
        for domain, statements in fragment.statements.items():
            if domain == "comb" or domain not in self.controls:
                continue
            lhs_masks = LHSMaskCollector()
            lhs_masks.visit_stmt(statements)
            self._insert_control(new_fragment, domain, lhs_masks)
        return new_fragment

    def _insert_control(self, fragment, domain, signals):
        raise NotImplementedError # :nocov:

    def __call__(self, value, *, src_loc_at=0):
        self.src_loc = tracer.get_src_loc(src_loc_at=src_loc_at)
        return super().__call__(value, src_loc_at=1 + src_loc_at)


class ResetInserter(_ControlInserter):
    def _insert_control(self, fragment, domain, lhs_masks):
        stmts = []
        for signal, start, stop in lhs_masks.chunks():
            if signal.reset_less:
                continue
            if start == 0 and stop is None:
                stmts.append(signal.eq(Const(signal.init, signal.shape())))
            else:
                stmts.append(signal[start:stop].eq(Const(signal.init, signal.shape())[start:stop]))
        fragment.add_statements(domain, Switch(self.controls[domain], [(1, stmts, None)], src_loc=self.src_loc))


class EnableInserter(_ControlInserter):
    def _insert_control(self, fragment, domain, _lhs_masks):
        if domain in fragment.statements:
            fragment.statements[domain] = _StatementList([Switch(
                self.controls[domain],
                [(1, fragment.statements[domain], None)],
                src_loc=self.src_loc,
            )])

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
