from typing import Tuple
from collections import defaultdict, OrderedDict
from functools import reduce
import enum
import warnings

from .._utils import flatten, memoize
from .. import tracer, _unused
from . import _ast, _cd, _ir, _nir


__all__ = [
    "UnusedElaboratable", "Elaboratable", "DriverConflict", "Fragment", "Instance",
    "IOBufferInstance", "PortDirection", "Design", "build_netlist",
]


class UnusedElaboratable(_unused.UnusedMustUse):
    # The warning is initially silenced. If everything that has been constructed remains unused,
    # it means the application likely crashed (with an exception, or in another way that does not
    # call `sys.excepthook`), and it's not necessary to show any warnings.
    # Once elaboration starts, the warning is enabled.
    _MustUse__silence = True


class Elaboratable(_unused.MustUse):
    _MustUse__warning = UnusedElaboratable


class DriverConflict(UserWarning):
    pass


class Fragment:
    @staticmethod
    def get(obj, platform):
        code = None
        origins = []
        while True:
            if isinstance(obj, Fragment):
                if hasattr(obj, "origins"):
                    obj.origins = tuple(origins)
                return obj
            elif isinstance(obj, Elaboratable):
                code = obj.elaborate.__code__
                UnusedElaboratable._MustUse__silence = False
                obj._MustUse__used = True
                new_obj = obj.elaborate(platform)
            elif hasattr(obj, "elaborate"):
                warnings.warn(
                    message="Class {!r} is an elaboratable that does not explicitly inherit from "
                            "Elaboratable; doing so would improve diagnostics"
                            .format(type(obj)),
                    category=RuntimeWarning,
                    stacklevel=2)
                code = obj.elaborate.__code__
                new_obj = obj.elaborate(platform)
            else:
                raise AttributeError(f"Object {obj!r} cannot be elaborated")
            if new_obj is obj:
                raise RecursionError(f"Object {obj!r} elaborates to itself")
            if new_obj is None and code is not None:
                warnings.warn_explicit(
                    message=".elaborate() returned None; missing return statement?",
                    category=UserWarning,
                    filename=code.co_filename,
                    lineno=code.co_firstlineno)
            origins.append(obj)
            obj = new_obj

    def __init__(self, *, src_loc=None):
        self.drivers = OrderedDict()
        self.statements = {}
        self.domains = OrderedDict()
        self.subfragments = []
        self.attrs = OrderedDict()
        self.generated = OrderedDict()
        self.flatten = False
        self.src_loc = src_loc
        self.origins = None

    def add_driver(self, signal, domain="comb"):
        assert isinstance(domain, str)
        if domain not in self.drivers:
            self.drivers[domain] = _ast.SignalSet()
        self.drivers[domain].add(signal)

    def iter_drivers(self):
        for domain, signals in self.drivers.items():
            for signal in signals:
                yield domain, signal

    def iter_comb(self):
        if "comb" in self.drivers:
            yield from self.drivers["comb"]

    def iter_sync(self):
        for domain, signals in self.drivers.items():
            if domain == "comb":
                continue
            for signal in signals:
                yield domain, signal

    def add_domains(self, *domains):
        for domain in flatten(domains):
            assert isinstance(domain, _cd.ClockDomain)
            assert domain.name not in self.domains
            self.domains[domain.name] = domain

    def iter_domains(self):
        yield from self.domains

    def add_statements(self, domain, *stmts):
        assert isinstance(domain, str)
        for stmt in _ast.Statement.cast(stmts):
            stmt._MustUse__used = True
            self.statements.setdefault(domain, _ast._StatementList()).append(stmt)

    def add_subfragment(self, subfragment, name=None, *, src_loc=None):
        assert isinstance(subfragment, Fragment)
        self.subfragments.append((subfragment, name, src_loc))

    def find_subfragment(self, name_or_index):
        if isinstance(name_or_index, int):
            if name_or_index < len(self.subfragments):
                subfragment, name, src_loc = self.subfragments[name_or_index]
                return subfragment
            raise NameError(f"No subfragment at index #{name_or_index}")
        else:
            for subfragment, name, src_loc in self.subfragments:
                if name == name_or_index:
                    return subfragment
            raise NameError(f"No subfragment with name '{name_or_index}'")

    def find_generated(self, *path):
        if len(path) > 1:
            path_component, *path = path
            return self.find_subfragment(path_component).find_generated(*path)
        else:
            item, = path
            return self.generated[item]

    def elaborate(self, platform):
        return self

    def _merge_subfragment(self, subfragment):
        # Merge subfragment's everything except clock domains into this fragment.
        # Flattening is done after clock domain propagation, so we can assume the domains
        # are already the same in every involved fragment in the first place.
        for domain, signal in subfragment.iter_drivers():
            self.add_driver(signal, domain)
        for domain, statements in subfragment.statements.items():
            self.statements.setdefault(domain, []).extend(statements)
        self.subfragments += subfragment.subfragments

        # Remove the merged subfragment.
        found = False
        for i, (check_subfrag, check_name, check_src_loc) in enumerate(self.subfragments): # :nobr:
            if subfragment == check_subfrag:
                del self.subfragments[i]
                found = True
                break
        assert found

    def _resolve_hierarchy_conflicts(self, hierarchy=("top",), mode="warn"):
        assert mode in ("silent", "warn", "error")
        from ._mem import MemoryInstance

        driver_subfrags = _ast.SignalDict()
        def add_subfrag(registry, entity, entry):
            # Because of missing domain insertion, at the point when this code runs, we have
            # a mixture of bound and unbound {Clock,Reset}Signals. Map the bound ones to
            # the actual signals (because the signal itself can be driven as well); but leave
            # the unbound ones as it is, because there's no concrete signal for it yet anyway.
            if isinstance(entity, _ast.ClockSignal) and entity.domain in self.domains:
                entity = self.domains[entity.domain].clk
            elif isinstance(entity, _ast.ResetSignal) and entity.domain in self.domains:
                entity = self.domains[entity.domain].rst

            if entity not in registry:
                registry[entity] = set()
            registry[entity].add(entry)

        # For each signal driven by this fragment and/or its subfragments, determine which
        # subfragments also drive it.
        for domain, signal in self.iter_drivers():
            add_subfrag(driver_subfrags, signal, (None, hierarchy))

        flatten_subfrags = set()
        for i, (subfrag, name, src_loc) in enumerate(self.subfragments):
            if name is None:
                name = f"<unnamed #{i}>"
            subfrag_hierarchy = hierarchy + (name,)

            if subfrag.flatten:
                # Always flatten subfragments that explicitly request it.
                flatten_subfrags.add((subfrag, subfrag_hierarchy))

            if isinstance(subfrag, (Instance, MemoryInstance, IOBufferInstance)):
                # Never flatten instances.
                continue

            # First, recurse into subfragments and let them detect driver conflicts as well.
            subfrag_drivers = \
                subfrag._resolve_hierarchy_conflicts(subfrag_hierarchy, mode)

            # Second, classify subfragments by signals they drive.
            for signal in subfrag_drivers:
                add_subfrag(driver_subfrags, signal, (subfrag, subfrag_hierarchy))

        # Find out the set of subfragments that needs to be flattened into this fragment
        # to resolve driver-driver conflicts.
        def flatten_subfrags_if_needed(subfrags):
            if len(subfrags) == 1:
                return []
            flatten_subfrags.update((f, h) for f, h in subfrags if f is not None)
            return list(sorted(".".join(h) for f, h in subfrags))

        for signal, subfrags in driver_subfrags.items():
            subfrag_names = flatten_subfrags_if_needed(subfrags)
            if not subfrag_names:
                continue

            # While we're at it, show a message.
            message = ("Signal '{}' is driven from multiple fragments: {}"
                       .format(signal, ", ".join(subfrag_names)))
            if mode == "error":
                raise DriverConflict(message)
            elif mode == "warn":
                message += "; hierarchy will be flattened"
                warnings.warn_explicit(message, DriverConflict, *signal.src_loc)

        # Flatten hierarchy.
        for subfrag, subfrag_hierarchy in sorted(flatten_subfrags, key=lambda x: x[1]):
            self._merge_subfragment(subfrag)

        # If we flattened anything, we might be in a situation where we have a driver conflict
        # again, e.g. if we had a tree of fragments like A --- B --- C where only fragments
        # A and C were driving a signal S. In that case, since B is not driving S itself,
        # processing B will not result in any flattening, but since B is transitively driving S,
        # processing A will flatten B into it. Afterwards, we have a tree like AB --- C, which
        # has another conflict.
        if any(flatten_subfrags):
            # Try flattening again.
            return self._resolve_hierarchy_conflicts(hierarchy, mode)

        # Nothing was flattened, we're done!
        return _ast.SignalSet(driver_subfrags.keys())

    def _propagate_domains_up(self, hierarchy=("top",)):
        from ._xfrm import DomainRenamer

        domain_subfrags = defaultdict(set)

        # For each domain defined by a subfragment, determine which subfragments define it.
        for i, (subfrag, name, src_loc) in enumerate(self.subfragments):
            # First, recurse into subfragments and let them propagate domains up as well.
            hier_name = name
            if hier_name is None:
                hier_name = f"<unnamed #{i}>"
            subfrag._propagate_domains_up(hierarchy + (hier_name,))

            # Second, classify subfragments by domains they define.
            for domain_name, domain in subfrag.domains.items():
                if domain.local:
                    continue
                domain_subfrags[domain_name].add((subfrag, name, src_loc, i))

        # For each domain defined by more than one subfragment, rename the domain in each
        # of the subfragments such that they no longer conflict.
        for domain_name, subfrags in domain_subfrags.items():
            if len(subfrags) == 1:
                continue

            names = [n for f, n, s, i in subfrags]
            if not all(names):
                names = sorted(f"<unnamed #{i}>" if n is None else f"'{n}'"
                               for f, n, s, i in subfrags)
                raise _cd.DomainError(
                    "Domain '{}' is defined by subfragments {} of fragment '{}'; it is necessary "
                    "to either rename subfragment domains explicitly, or give names to subfragments"
                    .format(domain_name, ", ".join(names), ".".join(hierarchy)))

            if len(names) != len(set(names)):
                names = sorted(f"#{i}" for f, n, s, i in subfrags)
                raise _cd.DomainError(
                    "Domain '{}' is defined by subfragments {} of fragment '{}', some of which "
                    "have identical names; it is necessary to either rename subfragment domains "
                    "explicitly, or give distinct names to subfragments"
                    .format(domain_name, ", ".join(names), ".".join(hierarchy)))

            for subfrag, name, src_loc, i in subfrags:
                domain_name_map = {domain_name: f"{name}_{domain_name}"}
                self.subfragments[i] = (DomainRenamer(domain_name_map)(subfrag), name, src_loc)

        # Finally, collect the (now unique) subfragment domains, and merge them into our domains.
        for subfrag, name, src_loc in self.subfragments:
            for domain_name, domain in subfrag.domains.items():
                if domain.local:
                    continue
                self.add_domains(domain)

    def _propagate_domains_down(self):
        # For each domain defined in this fragment, ensure it also exists in all subfragments.
        for subfrag, name, src_loc in self.subfragments:
            for domain in self.iter_domains():
                if domain in subfrag.domains:
                    assert self.domains[domain] is subfrag.domains[domain]
                else:
                    subfrag.add_domains(self.domains[domain])

            subfrag._propagate_domains_down()

    def _create_missing_domains(self, missing_domain, *, platform=None):
        from ._xfrm import DomainCollector

        collector = DomainCollector()
        collector(self)

        new_domains = []
        for domain_name in collector.used_domains - collector.defined_domains:
            if domain_name == "comb":
                continue
            value = missing_domain(domain_name)
            if value is None:
                raise _cd.DomainError(f"Domain '{domain_name}' is used but not defined")
            if type(value) is _cd.ClockDomain:
                self.add_domains(value)
                # And expose ports on the newly added clock domain, since it is added directly
                # and there was no chance to add any logic driving it.
                new_domains.append(value)
            else:
                new_fragment = Fragment.get(value, platform=platform)
                if domain_name not in new_fragment.domains:
                    defined = new_fragment.domains.keys()
                    raise _cd.DomainError(
                        "Fragment returned by missing domain callback does not define "
                        "requested domain '{}' (defines {})."
                        .format(domain_name, ", ".join(f"'{n}'" for n in defined)))
                self.add_subfragment(new_fragment, f"cd_{domain_name}")
                self.add_domains(new_fragment.domains.values())
        return new_domains

    def _propagate_domains(self, missing_domain, *, platform=None):
        self._propagate_domains_up()
        self._propagate_domains_down()
        self._resolve_hierarchy_conflicts()
        new_domains = self._create_missing_domains(missing_domain, platform=platform)
        self._propagate_domains_down()
        return new_domains

    def _prepare_ports(self, ports):
        # Normalize ports to a list.
        new_ports = []
        if isinstance(ports, dict):
            for port_name, (signal, dir) in ports.items():
                new_ports.append((port_name, signal, dir))
        elif isinstance(ports, (list, tuple)):
            for port in ports:
                if isinstance(port, tuple):
                    port_name, signal, dir = port
                    new_ports.append((port_name, signal, dir))
                else:
                    new_ports.append((None, port, None))
        else:
            msg = f"`ports` must be a dict, a list or a tuple, not {ports!r}"
            if isinstance(ports, _ast.Value):
                msg += " (did you mean `ports=(<signal>,)`, rather than `ports=<signal>`?)"
            raise TypeError(msg)

        # Validate ports.
        prenamed_ports = set()
        for (port_name, signal, dir) in new_ports:
            if isinstance(port_name, str):
                if port_name in prenamed_ports:
                    raise TypeError(f"Duplicate port name {port_name!r}")
                else:
                    prenamed_ports.add(port_name)
            elif port_name is not None:
                raise TypeError(f"Port name must be a string, not {port_name!r}")
            if dir is not None and not isinstance(dir, PortDirection):
                raise TypeError(
                    f"Port direction must be a `PortDirection` instance or None, not {dir!r}")
            if not isinstance(signal, (_ast.Signal, _ast.ClockSignal, _ast.ResetSignal)):
                raise TypeError(f"Only signals may be added as ports, not {signal!r}")

        return new_ports

    def prepare(self, ports=(), *, hierarchy=("top",), missing_domain=lambda name: _cd.ClockDomain(name), propagate_domains=True):
        from ._xfrm import DomainLowerer

        ports = self._prepare_ports(ports)

        if propagate_domains:
            new_domains = self._propagate_domains(missing_domain)
            for domain in new_domains:
                ports.append((None, domain.clk, PortDirection.Input))
                if domain.rst is not None:
                    ports.append((None, domain.rst, PortDirection.Input))

        def resolve_signal(signal):
            if isinstance(signal, _ast.ClockSignal):
                domain = self.domains[signal.domain]
                return domain.clk
            elif isinstance(signal, _ast.ResetSignal):
                domain = self.domains[signal.domain]
                if domain.rst is None:
                    raise ValueError(f"Using ResetSignal for a reset-less domain {signal.domain}")
                return domain.rst
            else:
                return signal

        ports = [
            (name, resolve_signal(signal), dir)
            for name, signal, dir in ports
        ]

        fragment = DomainLowerer()(self)

        # Create design and let it do the rest.
        return Design(fragment, ports, hierarchy=hierarchy)


class Instance(Fragment):
    def __init__(self, type, *args, src_loc=None, src_loc_at=0, **kwargs):
        super().__init__(src_loc=src_loc or tracer.get_src_loc(src_loc_at))

        self.type        = type
        self.parameters  = OrderedDict()
        self.named_ports = OrderedDict()

        for (kind, name, value) in args:
            if kind == "a":
                self.attrs[name] = value
            elif kind == "p":
                self.parameters[name] = value
            elif kind in ("i", "o", "io"):
                self.named_ports[name] = (_ast.Value.cast(value), kind)
            else:
                raise NameError("Instance argument {!r} should be a tuple (kind, name, value) "
                                "where kind is one of \"a\", \"p\", \"i\", \"o\", or \"io\""
                                .format((kind, name, value)))

        for kw, arg in kwargs.items():
            if kw.startswith("a_"):
                self.attrs[kw[2:]] = arg
            elif kw.startswith("p_"):
                self.parameters[kw[2:]] = arg
            elif kw.startswith("i_"):
                self.named_ports[kw[2:]] = (_ast.Value.cast(arg), "i")
            elif kw.startswith("o_"):
                self.named_ports[kw[2:]] = (_ast.Value.cast(arg), "o")
            elif kw.startswith("io_"):
                self.named_ports[kw[3:]] = (_ast.Value.cast(arg), "io")
            else:
                raise NameError("Instance keyword argument {}={!r} does not start with one of "
                                "\"a_\", \"p_\", \"i_\", \"o_\", or \"io_\""
                                .format(kw, arg))


class IOBufferInstance(Fragment):
    def __init__(self, pad, *, i=None, o=None, oe=None, src_loc_at=0, src_loc=None):
        super().__init__()

        self.pad = _ast.Value.cast(pad)
        if i is None:
            self.i = None
        else:
            self.i = _ast.Value.cast(i)
            if len(self.pad) != len(self.i):
                raise ValueError(f"`pad` length ({len(self.pad)}) doesn't match `i` length ({len(self.i)})")
        if o is None:
            if oe is not None:
                raise ValueError("`oe` must not be used if `o` is not used")
            self.o = _ast.Const(0, len(self.pad))
            self.oe = _ast.Const(0)
        else:
            self.o = _ast.Value.cast(o)
            if len(self.pad) != len(self.o):
                raise ValueError(f"`pad` length ({len(self.pad)}) doesn't match `o` length ({len(self.o)})")
            if oe is None:
                self.oe = _ast.Const(1)
            else:
                self.oe = _ast.Value.cast(oe)
                if len(self.oe) != 1:
                    raise ValueError(f"`oe` length ({len(self.oe)}) must be 1")

        self.src_loc     = src_loc or tracer.get_src_loc(src_loc_at)


class Design:
    """Represents a design ready for simulation or netlist building.

    Returned by ``Fragment.prepare``."""

    def __init__(self, fragment, ports, *, hierarchy):
        self.fragment = fragment
        self.ports = ports
        self.hierarchy = hierarchy
        # dict of Fragment to SignalDict of Signal to name
        self.signal_names = {}
        self.fragment_names = {}
        self._assign_names_to_signals(fragment, ports)
        self._assign_names_to_fragments(fragment, hierarchy)
        # Use just-assigned signal names to name all unnamed ports.
        top_names = self.signal_names[fragment]
        self.ports = [
            (name or top_names[signal], signal, dir)
            for (name, signal, dir) in self.ports
        ]

    def _assign_names_to_signals(self, fragment, ports=None):
        """Assign names to signals used in a given fragment.

        The mapping is set in ``self.signal_names``.  Because names are deduplicated using local
        information only, the same signal used in a different fragment may get a different name.
        """

        signal_names   = _ast.SignalDict()
        assigned_names = set()

        def add_signal_name(signal):
            if signal not in signal_names:
                if signal.name not in assigned_names:
                    name = signal.name
                else:
                    name = f"{signal.name}${len(assigned_names)}"
                    assert name not in assigned_names
                signal_names[signal] = name
                assigned_names.add(name)

        if ports is not None:
            # First pass: reserve names for pre-named top-level ports. If equal to the signal name, let the signal share it.
            for name, signal, _dir in ports:
                if name is not None:
                    assigned_names.add(name)
                    if signal.name == name:
                        signal_names[signal] = name

            # Second pass: ensure non-pre-named top-level ports are named first.
            for name, signal, _dir in ports:
                if name is None:
                    add_signal_name(signal)

        for domain_name, domain_signals in fragment.drivers.items():
            if domain_name != "comb":
                domain = fragment.domains[domain_name]
                add_signal_name(domain.clk)
                if domain.rst is not None:
                    add_signal_name(domain.rst)

        for statements in fragment.statements.values():
            for statement in statements:
                for signal in statement._lhs_signals() | statement._rhs_signals():
                    if not isinstance(signal, (_ast.ClockSignal, _ast.ResetSignal)):
                        add_signal_name(signal)

        self.signal_names[fragment] = signal_names
        for subfragment, _name, _src_loc in fragment.subfragments:
            self._assign_names_to_signals(subfragment)

    def _assign_names_to_fragments(self, fragment, hierarchy):
        """Assign names to this fragment and its subfragments.

        Subfragments may not necessarily have a name. This method assigns every such subfragment
        a name, ``U$<number>``, where ``<number>`` is based on its location in the hierarchy.

        Subfragment names may collide with signal names safely in Amaranth, but this may confuse
        backends. This method assigns every such subfragment a name, ``<name>$U$<number>``, where
        ``name`` is its original name, and ``<number>`` is based on its location in the hierarchy.

        Arguments
        ---------
        hierarchy : tuple of str
            Name of this fragment.

        Returns
        -------
        dict of Fragment to tuple of str
            A mapping from this fragment and its subfragments to their full hierarchical names.
        """
        self.fragment_names[fragment] = hierarchy

        taken_names = set(self.signal_names[fragment].values())
        for subfragment_index, (subfragment, subfragment_name, subfragment_src_loc) in enumerate(fragment.subfragments):
            if subfragment_name is None:
                subfragment_name = f"U${subfragment_index}"
            elif subfragment_name in taken_names:
                subfragment_name = f"{subfragment_name}$U${subfragment_index}"
            assert subfragment_name not in taken_names
            taken_names.add(subfragment_name)
            self._assign_names_to_fragments(subfragment, hierarchy=(*hierarchy, subfragment_name))


############################################################################################### >:3


class PortDirection(enum.Enum):
    Input = "input"
    Output = "output"
    Inout = "inout"


class NetlistDriver:
    def __init__(self, module_idx: int, signal: _ast.Signal,
                 domain: '_cd.ClockDomain | None', *, src_loc):
        self.module_idx = module_idx
        self.signal = signal
        self.domain = domain
        self.src_loc = src_loc
        self.assignments = []

    def emit_value(self, builder):
        if self.domain is None:
            init = _ast.Const(self.signal.init, self.signal.width)
            default, _signed = builder.emit_rhs(self.module_idx, init)
        else:
            default = builder.emit_signal(self.signal)
        if len(self.assignments) == 1:
            assign, = self.assignments
            if assign.cond == 1 and assign.start == 0 and len(assign.value) == len(default):
                return assign.value
        cell = _nir.AssignmentList(self.module_idx, default=default, assignments=self.assignments,
                                   src_loc=self.signal.src_loc)
        return builder.netlist.add_value_cell(len(default), cell)


class NetlistEmitter:
    def __init__(self, netlist: _nir.Netlist, design):
        self.netlist = netlist
        self.design = design
        self.drivers = _ast.SignalDict()
        self.rhs_cache: dict[int, Tuple[_nir.Value, bool, _ast.Value]] = {}

        # Collected for driver conflict diagnostics only.
        self.late_net_to_signal = {}
        self.connect_src_loc = {}

    def emit_signal(self, signal) -> _nir.Value:
        if signal in self.netlist.signals:
            return self.netlist.signals[signal]
        value = self.netlist.alloc_late_value(len(signal))
        self.netlist.signals[signal] = value
        for bit, net in enumerate(value):
            self.late_net_to_signal[net] = (signal, bit)
        return value

    # Used for instance outputs and read port data, not used for actual assignments.
    def emit_lhs(self, value: _ast.Value):
        if isinstance(value, _ast.Signal):
            return self.emit_signal(value)
        elif isinstance(value, _ast.Cat):
            result = []
            for part in value.parts:
                result += self.emit_lhs(part)
            return _nir.Value(result)
        elif isinstance(value, _ast.Slice):
            return self.emit_lhs(value.value)[value.start:value.stop]
        elif isinstance(value, _ast.Operator):
            assert value.operator in ('u', 's')
            return self.emit_lhs(value.operands[0])
        else:
            raise TypeError # :nocov:

    def extend(self, value: _nir.Value, signed: bool, width: int):
        nets = list(value)
        while len(nets) < width:
            if signed:
                nets.append(nets[-1])
            else:
                nets.append(_nir.Net.from_const(0))
        return _nir.Value(nets)

    def emit_operator(self, module_idx: int, operator: str, *inputs: _nir.Value, src_loc):
        op = _nir.Operator(module_idx, operator=operator, inputs=inputs, src_loc=src_loc)
        return self.netlist.add_value_cell(op.width, op)

    def unify_shapes_bitwise(self,
            operand_a: _nir.Value, signed_a: bool, operand_b: _nir.Value, signed_b: bool):
        if signed_a == signed_b:
            width = max(len(operand_a), len(operand_b))
        elif signed_a:
            width = max(len(operand_a), len(operand_b) + 1)
        else: # signed_b
            width = max(len(operand_a) + 1, len(operand_b))
        operand_a = self.extend(operand_a, signed_a, width)
        operand_b = self.extend(operand_b, signed_b, width)
        signed = signed_a or signed_b
        return (operand_a, operand_b, signed)

    def emit_rhs(self, module_idx: int, value: _ast.Value) -> Tuple[_nir.Value, bool]:
        """Emits a RHS value, returns a tuple of (value, is_signed)"""
        try:
            result, signed, value = self.rhs_cache[id(value)]
            return result, signed
        except KeyError:
            pass
        if isinstance(value, _ast.Const):
            result = _nir.Value.from_const(value.value, value.width)
            signed = value.signed
        elif isinstance(value, _ast.Signal):
            result = self.emit_signal(value)
            signed = value.signed
        elif isinstance(value, _ast.Operator):
            if len(value.operands) == 1:
                operand_a, signed_a = self.emit_rhs(module_idx, value.operands[0])
                if value.operator == 's':
                    result = operand_a
                    signed = True
                elif value.operator == 'u':
                    result = operand_a
                    signed = False
                elif value.operator == '+':
                    result = operand_a
                    signed = signed_a
                elif value.operator == '-':
                    operand_a = self.extend(operand_a, signed_a, len(operand_a) + 1)
                    result = self.emit_operator(module_idx, '-', operand_a,
                                                src_loc=value.src_loc)
                    signed = True
                elif value.operator == '~':
                    result = self.emit_operator(module_idx, '~', operand_a,
                                                src_loc=value.src_loc)
                    signed = signed_a
                elif value.operator in ('b', 'r|', 'r&', 'r^'):
                    result = self.emit_operator(module_idx, value.operator, operand_a,
                                                src_loc=value.src_loc)
                    signed = False
                else:
                    assert False # :nocov:
            elif len(value.operands) == 2:
                operand_a, signed_a = self.emit_rhs(module_idx, value.operands[0])
                operand_b, signed_b = self.emit_rhs(module_idx, value.operands[1])
                if value.operator in ('|', '&', '^'):
                    operand_a, operand_b, signed = \
                        self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                    result = self.emit_operator(module_idx, value.operator, operand_a, operand_b,
                                                src_loc=value.src_loc)
                elif value.operator in ('+', '-'):
                    operand_a, operand_b, signed = \
                        self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                    width = len(operand_a) + 1
                    operand_a = self.extend(operand_a, signed, width)
                    operand_b = self.extend(operand_b, signed, width)
                    result = self.emit_operator(module_idx, value.operator, operand_a, operand_b,
                                                src_loc=value.src_loc)
                    if value.operator == '-':
                        signed = True
                elif value.operator == '*':
                    width = len(operand_a) + len(operand_b)
                    operand_a = self.extend(operand_a, signed_a, width)
                    operand_b = self.extend(operand_b, signed_b, width)
                    result = self.emit_operator(module_idx, '*', operand_a, operand_b,
                                                src_loc=value.src_loc)
                    signed = signed_a or signed_b
                elif value.operator == '//':
                    width = len(operand_a) + signed_b
                    operand_a, operand_b, signed = \
                        self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                    if len(operand_a) < width:
                        operand_a = self.extend(operand_a, signed, width)
                        operand_b = self.extend(operand_b, signed, width)
                    operator = 's//' if signed else 'u//'
                    result = _nir.Value(
                        self.emit_operator(module_idx, operator, operand_a, operand_b,
                                           src_loc=value.src_loc)[:width]
                    )
                elif value.operator == '%':
                    width = len(operand_b)
                    operand_a, operand_b, signed = \
                        self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                    operator = 's%' if signed else 'u%'
                    result = _nir.Value(
                        self.emit_operator(module_idx, operator, operand_a, operand_b,
                                           src_loc=value.src_loc)[:width]
                    )
                    signed = signed_b
                elif value.operator == '<<':
                    operand_a = self.extend(operand_a, signed_a,
                                            len(operand_a) + 2 ** len(operand_b) - 1)
                    result = self.emit_operator(module_idx, '<<', operand_a, operand_b,
                                                src_loc=value.src_loc)
                    signed = signed_a
                elif value.operator == '>>':
                    operator = 's>>' if signed_a else 'u>>'
                    result = self.emit_operator(module_idx, operator, operand_a, operand_b,
                                                src_loc=value.src_loc)
                    signed = signed_a
                elif value.operator in ('==', '!='):
                    operand_a, operand_b, signed = \
                        self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                    result = self.emit_operator(module_idx, value.operator, operand_a, operand_b,
                                                src_loc=value.src_loc)
                    signed = False
                elif value.operator in ('<', '>', '<=', '>='):
                    operand_a, operand_b, signed = \
                        self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                    operator = ('s' if signed else 'u') + value.operator
                    result = self.emit_operator(module_idx, operator, operand_a, operand_b,
                                                src_loc=value.src_loc)
                    signed = False
                else:
                    assert False # :nocov:
            elif len(value.operands) == 3:
                assert value.operator == 'm'
                operand_s, signed_s = self.emit_rhs(module_idx, value.operands[0])
                operand_a, signed_a = self.emit_rhs(module_idx, value.operands[1])
                operand_b, signed_b = self.emit_rhs(module_idx, value.operands[2])
                if len(operand_s) != 1:
                    operand_s = self.emit_operator(module_idx, 'b', operand_s,
                                                   src_loc=value.src_loc)
                operand_a, operand_b, signed = \
                    self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                result = self.emit_operator(module_idx, 'm', operand_s, operand_a, operand_b,
                                            src_loc=value.src_loc)
            else:
                assert False # :nocov:
        elif isinstance(value, _ast.Slice):
            inner, _signed = self.emit_rhs(module_idx, value.value)
            result = _nir.Value(inner[value.start:value.stop])
            signed = False
        elif isinstance(value, _ast.Part):
            inner, signed = self.emit_rhs(module_idx, value.value)
            offset, _signed = self.emit_rhs(module_idx, value.offset)
            cell = _nir.Part(module_idx, value=inner, value_signed=signed, width=value.width,
                             stride=value.stride, offset=offset, src_loc=value.src_loc)
            result = self.netlist.add_value_cell(value.width, cell)
            signed = False
        elif isinstance(value, _ast.ArrayProxy):
            elems = [self.emit_rhs(module_idx, elem) for elem in value.elems]
            width = 0
            signed = False
            for elem, elem_signed in elems:
                if elem_signed:
                    if not signed:
                        width += 1
                        signed = True
                    width = max(width, len(elem))
                elif signed:
                    width = max(width, len(elem) + 1)
                else:
                    width = max(width, len(elem))
            elems = tuple(self.extend(elem, elem_signed, width) for elem, elem_signed in elems)
            index, _signed = self.emit_rhs(module_idx, value.index)
            cell = _nir.ArrayMux(module_idx, width=width, elems=elems, index=index,
                                 src_loc=value.src_loc)
            result = self.netlist.add_value_cell(width, cell)
        elif isinstance(value, _ast.Cat):
            nets = []
            for val in value.parts:
                inner, _signed = self.emit_rhs(module_idx, val)
                for net in inner:
                    nets.append(net)
            result = _nir.Value(nets)
            signed = False
        elif isinstance(value, _ast.AnyValue):
            result = self.netlist.add_value_cell(value.width,
                _nir.AnyValue(module_idx, kind=value.kind.value, width=value.width,
                              src_loc=value.src_loc))
            signed = value.signed
        elif isinstance(value, _ast.Initial):
            result = self.netlist.add_value_cell(1, _nir.Initial(module_idx, src_loc=value.src_loc))
            signed = False
        else:
            assert False # :nocov:
        assert value.shape().width == len(result), \
            f"Value {value!r} with shape {value.shape()!r} does not match " \
            f"result with width {len(result)}"
        # Add the value itself to the cache to make sure `id(value)` remains allocated and pointing
        # at `value`. This would be a weakref.WeakKeyDictionary if `value` was hashable.
        self.rhs_cache[id(value)] = result, signed, value
        return (result, signed)

    def connect(self, lhs: _nir.Value, rhs: _nir.Value, *, src_loc):
        assert len(lhs) == len(rhs)
        for left, right in zip(lhs, rhs):
            if left in self.netlist.connections:
                signal, bit = self.late_net_to_signal[left]
                other_src_loc = self.connect_src_loc[left]
                raise _ir.DriverConflict(f"Bit {bit} of signal {signal!r} has multiple drivers: "
                                         f"{other_src_loc} and {src_loc}")
            self.netlist.connections[left] = right
            self.connect_src_loc[left] = src_loc

    def emit_assign(self, module_idx: int, cd: "_cd.ClockDomain | None", lhs: _ast.Value, lhs_start: int, rhs: _nir.Value, cond: _nir.Net, *, src_loc):
        # Assign rhs to lhs[lhs_start:lhs_start+len(rhs)]
        if isinstance(lhs, _ast.Signal):
            if lhs in self.drivers:
                driver = self.drivers[lhs]
                if driver.domain is not cd:
                    domain_name = cd.name if cd is not None else "comb"
                    other_domain_name = driver.domain.name if driver.domain is not None else "comb"
                    raise _ir.DriverConflict(
                        f"Signal {lhs} driven from domain {domain_name} at {src_loc} and domain "
                        f"{other_domain_name} at {driver.src_loc}")
                if driver.module_idx != module_idx:
                    mod_name = ".".join(self.netlist.modules[module_idx].name or ("<toplevel>",))
                    other_mod_name = \
                        ".".join(self.netlist.modules[driver.module_idx].name or ("<toplevel>",))
                    raise _ir.DriverConflict(
                        f"Signal {lhs} driven from module {mod_name} at {src_loc} and "
                        f"module {other_mod_name} at {driver.src_loc}")
            else:
                driver = NetlistDriver(module_idx, lhs, domain=cd, src_loc=src_loc)
                self.drivers[lhs] = driver
            driver.assignments.append(_nir.Assignment(cond=cond, start=lhs_start, value=rhs,
                                                      src_loc=src_loc))
        elif isinstance(lhs, _ast.Slice):
            self.emit_assign(module_idx, cd, lhs.value, lhs_start + lhs.start, rhs, cond, src_loc=src_loc)
        elif isinstance(lhs, _ast.Cat):
            part_stop = 0
            for part in lhs.parts:
                part_start = part_stop
                part_len = len(part)
                part_stop = part_start + part_len
                if lhs_start >= part_stop:
                    continue
                if lhs_start + len(rhs) <= part_start:
                    continue
                if lhs_start < part_start:
                    part_lhs_start = 0
                    part_rhs_start = part_start - lhs_start
                else:
                    part_lhs_start = lhs_start - part_start
                    part_rhs_start = 0
                if lhs_start + len(rhs) >= part_stop:
                    part_rhs_stop = part_stop - lhs_start
                else:
                    part_rhs_stop = len(rhs)
                self.emit_assign(module_idx, cd, part, part_lhs_start, rhs[part_rhs_start:part_rhs_stop], cond, src_loc=src_loc)
        elif isinstance(lhs, _ast.Part):
            offset, _signed = self.emit_rhs(module_idx, lhs.offset)
            width = len(lhs.value)
            num_cases = min((width + lhs.stride - 1) // lhs.stride, 1 << len(offset))
            conds = []
            for case_index in range(num_cases):
                cell = _nir.Matches(module_idx, value=offset,
                                    patterns=(f"{case_index:0{len(offset)}b}",),
                                    src_loc=lhs.src_loc)
                subcond, = self.netlist.add_value_cell(1, cell)
                conds.append(subcond)
            conds = _nir.Value(conds)
            cell = _nir.PriorityMatch(module_idx, en=cond, inputs=conds, src_loc=lhs.src_loc)
            conds = self.netlist.add_value_cell(len(conds), cell)
            for idx, subcond in enumerate(conds):
                start = lhs_start + idx * lhs.stride
                if start >= width:
                    continue
                if start + len(rhs) >= width:
                    subrhs = rhs[:width - start]
                else:
                    subrhs = rhs
                self.emit_assign(module_idx, cd, lhs.value, start, subrhs, subcond, src_loc=src_loc)
        elif isinstance(lhs, _ast.ArrayProxy):
            index, _signed = self.emit_rhs(module_idx, lhs.index)
            conds = []
            for case_index in range(len(lhs.elems)):
                cell = _nir.Matches(module_idx, value=index,
                                       patterns=(f"{case_index:0{len(index)}b}",),
                                       src_loc=lhs.src_loc)
                subcond, = self.netlist.add_value_cell(1, cell)
                conds.append(subcond)
            conds = _nir.Value(conds)
            cell = _nir.PriorityMatch(module_idx, en=cond, inputs=conds, src_loc=lhs.src_loc)
            conds = self.netlist.add_value_cell(len(conds), cell)
            for subcond, val in zip(conds, lhs.elems):
                self.emit_assign(module_idx, cd, val, lhs_start, rhs[:len(val)], subcond, src_loc=src_loc)
        elif isinstance(lhs, _ast.Operator):
            assert lhs.operator in ('u', 's')
            self.emit_assign(module_idx, cd, lhs.operands[0], lhs_start, rhs, cond, src_loc=src_loc)
        else:
            assert False # :nocov:

    def emit_stmt(self, module_idx: int, fragment: _ir.Fragment, domain: str,
                  stmt: _ast.Statement, cond: _nir.Net):
        if domain == "comb":
            cd: _cd.ClockDomain | None = None
        else:
            cd = fragment.domains[domain]
        if isinstance(stmt, _ast.Assign):
            rhs, signed = self.emit_rhs(module_idx, stmt.rhs)
            width = len(stmt.lhs)
            if len(rhs) > width:
                rhs = _nir.Value(rhs[:width])
            if len(rhs) < width:
                rhs = self.extend(rhs, signed, width)
            self.emit_assign(module_idx, cd, stmt.lhs, 0, rhs, cond, src_loc=stmt.src_loc)
        elif isinstance(stmt, _ast.Property):
            test, _signed = self.emit_rhs(module_idx, stmt.test)
            if len(test) != 1:
                test = self.emit_operator(module_idx, 'b', test, src_loc=stmt.src_loc)
            test, = test
            en_cell = _nir.AssignmentList(module_idx,
                default=_nir.Value.zeros(),
                assignments=[
                    _nir.Assignment(cond=cond, start=0, value=_nir.Value.ones(),
                                    src_loc=stmt.src_loc)
                ],
                src_loc=stmt.src_loc)
            cond, = self.netlist.add_value_cell(1, en_cell)
            if cd is None:
                cell = _nir.AsyncProperty(module_idx, kind=stmt.kind.value, test=test, en=cond,
                                          name=stmt.name, src_loc=stmt.src_loc)
            else:
                clk, = self.emit_signal(cd.clk)
                cell = _nir.SyncProperty(module_idx, kind=stmt.kind.value, test=test, en=cond,
                                         clk=clk, clk_edge=cd.clk_edge, name=stmt.name,
                                         src_loc=stmt.src_loc)
            self.netlist.add_cell(cell)
        elif isinstance(stmt, _ast.Switch):
            test, _signed = self.emit_rhs(module_idx, stmt.test)
            conds = []
            for patterns in stmt.cases:
                if patterns:
                    for pattern in patterns:
                        assert len(pattern) == len(test)
                    cell = _nir.Matches(module_idx, value=test, patterns=patterns,
                                        src_loc=stmt.case_src_locs.get(patterns))
                    net, = self.netlist.add_value_cell(1, cell)
                    conds.append(net)
                else:
                    conds.append(_nir.Net.from_const(1))
            cell = _nir.PriorityMatch(module_idx, en=cond, inputs=_nir.Value(conds),
                                      src_loc=stmt.src_loc)
            conds = self.netlist.add_value_cell(len(conds), cell)
            for subcond, substmts in zip(conds, stmt.cases.values()):
                for substmt in substmts:
                    self.emit_stmt(module_idx, fragment, domain, substmt, subcond)
        else:
            assert False # :nocov:

    def emit_iobuffer(self, module_idx: int, instance: _ir.IOBufferInstance):
        pad = self.emit_lhs(instance.pad)
        o, _signed = self.emit_rhs(module_idx, instance.o)
        (oe,), _signed = self.emit_rhs(module_idx, instance.oe)
        assert len(pad) == len(o)
        cell = _nir.IOBuffer(module_idx, pad=pad, o=o, oe=oe, src_loc=instance.src_loc)
        value = self.netlist.add_value_cell(len(pad), cell)
        if instance.i is not None:
            self.connect(self.emit_lhs(instance.i), value, src_loc=instance.src_loc)

    def emit_memory(self, module_idx: int, fragment: '_mem.MemoryInstance', name: str):
        cell = _nir.Memory(module_idx,
            width=fragment._width,
            depth=fragment._depth,
            init=fragment._init,
            name=name,
            attributes=fragment._attrs,
            src_loc=fragment.src_loc,
        )
        return self.netlist.add_cell(cell)

    def emit_write_port(self, module_idx: int, fragment: '_mem.MemoryInstance',
                        port: '_mem.MemoryInstance._WritePort', memory: int):
        data, _signed = self.emit_rhs(module_idx, port._data)
        addr, _signed = self.emit_rhs(module_idx, port._addr)
        en, _signed = self.emit_rhs(module_idx, port._en)
        en = _nir.Value([en[bit // port._granularity] for bit in range(len(port._data))])
        cd = fragment.domains[port._domain]
        clk, = self.emit_signal(cd.clk)
        cell = _nir.SyncWritePort(module_idx,
            memory=memory,
            data=data,
            addr=addr,
            en=en,
            clk=clk,
            clk_edge=cd.clk_edge,
            src_loc=port._data.src_loc,
        )
        return self.netlist.add_cell(cell)

    def emit_read_port(self, module_idx: int, fragment: '_mem.MemoryInstance',
                       port: '_mem.MemoryInstance._ReadPort', memory: int,
                       write_ports: 'list[int]'):
        addr, _signed = self.emit_rhs(module_idx, port._addr)
        if port._domain == "comb":
            cell = _nir.AsyncReadPort(module_idx,
                memory=memory,
                width=len(port._data),
                addr=addr,
                src_loc=port._data.src_loc,
            )
        else:
            (en,), _signed = self.emit_rhs(module_idx, port._en)
            cd = fragment.domains[port._domain]
            clk, = self.emit_signal(cd.clk)
            cell = _nir.SyncReadPort(module_idx,
                memory=memory,
                width=len(port._data),
                addr=addr,
                en=en,
                clk=clk,
                clk_edge=cd.clk_edge,
                transparent_for=tuple(write_ports[idx] for idx in port._transparent_for),
                src_loc=port._data.src_loc,
            )
        data = self.netlist.add_value_cell(len(port._data), cell)
        self.connect(self.emit_lhs(port._data), data, src_loc=port._data.src_loc)

    def emit_instance(self, module_idx: int, instance: _ir.Instance, name: str):
        ports_i = {}
        ports_o = {}
        ports_io = {}
        outputs = []
        next_output_bit = 0
        for port_name, (port_conn, dir) in instance.named_ports.items():
            if dir == 'i':
                ports_i[port_name], _signed = self.emit_rhs(module_idx, port_conn)
            elif dir == 'o':
                port_conn = self.emit_lhs(port_conn)
                ports_o[port_name] = (next_output_bit, len(port_conn))
                outputs.append((next_output_bit, port_conn))
                next_output_bit += len(port_conn)
            elif dir == 'io':
                ports_io[port_name] = self.emit_lhs(port_conn)
            else:
                assert False # :nocov:
        cell = _nir.Instance(module_idx,
            type=instance.type,
            name=name,
            parameters=instance.parameters,
            attributes=instance.attrs,
            ports_i=ports_i,
            ports_o=ports_o,
            ports_io=ports_io,
            src_loc=instance.src_loc,
        )
        output_nets = self.netlist.add_value_cell(width=next_output_bit, cell=cell)
        for start_bit, port_conn in outputs:
            self.connect(port_conn, _nir.Value(output_nets[start_bit:start_bit + len(port_conn)]),
                         src_loc=instance.src_loc)

    def emit_top_ports(self, fragment: _ir.Fragment):
        inouts = set()
        for cell in self.netlist.cells:
            if isinstance(cell, _nir.IOBuffer):
                inouts.update(cell.pad)
            if isinstance(cell, _nir.Instance):
                for value in cell.ports_io.values():
                    inouts.update(value)

        next_input_bit = 2 # 0 and 1 are reserved for constants
        top = self.netlist.top

        for name, signal, dir in self.design.ports:
            signal_value = self.emit_signal(signal)
            if dir is None:
                is_driven = False
                is_inout = False
                for net in signal_value:
                    if net in self.netlist.connections:
                        is_driven = True
                    if net in inouts:
                        is_inout = True
                if is_driven:
                    dir = PortDirection.Output
                elif is_inout:
                    dir = PortDirection.Inout
                else:
                    dir = PortDirection.Input
            if dir == PortDirection.Input:
                top.ports_i[name] = (next_input_bit, signal.width)
                value = _nir.Value(
                    _nir.Net.from_cell(0, bit)
                    for bit in range(next_input_bit, next_input_bit + signal.width)
                )
                next_input_bit += signal.width
                self.connect(signal_value, value, src_loc=signal.src_loc)
            elif dir == PortDirection.Output:
                top.ports_o[name] = signal_value
            elif dir == PortDirection.Inout:
                top.ports_io[name] = (next_input_bit, signal.width)
                value = _nir.Value(
                    _nir.Net.from_cell(0, bit)
                    for bit in range(next_input_bit, next_input_bit + signal.width)
                )
                next_input_bit += signal.width
                self.connect(signal_value, value, src_loc=signal.src_loc)
            else:
                raise ValueError(f"Invalid port direction {dir!r}")

    def emit_drivers(self):
        for driver in self.drivers.values():
            if (driver.domain is not None and
                    driver.domain.rst is not None and
                    not driver.domain.async_reset and
                    not driver.signal.reset_less):
                cell = _nir.Matches(driver.module_idx,
                                    value=self.emit_signal(driver.domain.rst),
                                    patterns=("1",),
                                    src_loc=driver.domain.rst.src_loc)
                cond, = self.netlist.add_value_cell(1, cell)
                cell = _nir.PriorityMatch(driver.module_idx, en=_nir.Net.from_const(1),
                                          inputs=_nir.Value(cond),
                                          src_loc=driver.domain.rst.src_loc)
                cond, = self.netlist.add_value_cell(1, cell)
                init = _nir.Value.from_const(driver.signal.init, driver.signal.width)
                driver.assignments.append(_nir.Assignment(cond=cond, start=0,
                                                         value=init, src_loc=driver.signal.src_loc))
            value = driver.emit_value(self)
            if driver.domain is not None:
                clk, = self.emit_signal(driver.domain.clk)
                if driver.domain.rst is not None and driver.domain.async_reset and not driver.signal.reset_less:
                    arst, = self.emit_signal(driver.domain.rst)
                else:
                    arst = _nir.Net.from_const(0)
                cell = _nir.FlipFlop(driver.module_idx,
                    data=value,
                    init=driver.signal.init,
                    clk=clk,
                    clk_edge=driver.domain.clk_edge,
                    arst=arst,
                    attributes=driver.signal.attrs,
                    src_loc=driver.signal.src_loc,
                )
                value = self.netlist.add_value_cell(len(value), cell)
            if driver.assignments:
                src_loc = driver.assignments[0].src_loc
            else:
                src_loc = driver.signal.src_loc
            self.connect(self.emit_signal(driver.signal), value, src_loc=src_loc)

    def emit_undriven(self):
        # Connect all undriven signal bits to their initial values. This can only happen for entirely
        # undriven signals, or signals that are partially driven by instances.
        for signal, value in self.netlist.signals.items():
            for bit, net in enumerate(value):
                if net.is_late and net not in self.netlist.connections:
                    self.netlist.connections[net] = _nir.Net.from_const((signal.init >> bit) & 1)

    def emit_fragment(self, fragment: _ir.Fragment, parent_module_idx: 'int | None', *, cell_src_loc=None):
        from . import _mem

        fragment_name = self.design.fragment_names[fragment]
        if isinstance(fragment, _ir.Instance):
            assert parent_module_idx is not None
            self.emit_instance(parent_module_idx, fragment, name=fragment_name[-1])
        elif isinstance(fragment, _mem.MemoryInstance):
            assert parent_module_idx is not None
            memory = self.emit_memory(parent_module_idx, fragment, name=fragment_name[-1])
            write_ports = []
            for port in fragment._write_ports:
                write_ports.append(self.emit_write_port(parent_module_idx, fragment, port, memory))
            for port in fragment._read_ports:
                self.emit_read_port(parent_module_idx, fragment, port, memory, write_ports)
        elif isinstance(fragment, _ir.IOBufferInstance):
            assert parent_module_idx is not None
            self.emit_iobuffer(parent_module_idx, fragment)
        elif type(fragment) is _ir.Fragment:
            module_idx = self.netlist.add_module(parent_module_idx, fragment_name, src_loc=fragment.src_loc, cell_src_loc=cell_src_loc)
            signal_names = self.design.signal_names[fragment]
            self.netlist.modules[module_idx].signal_names = signal_names
            for signal in signal_names:
                self.emit_signal(signal)
            for domain, stmts in fragment.statements.items():
                for stmt in stmts:
                    self.emit_stmt(module_idx, fragment, domain, stmt, _nir.Net.from_const(1))
            for subfragment, _name, sub_src_loc in fragment.subfragments:
                self.emit_fragment(subfragment, module_idx, cell_src_loc=sub_src_loc)
            if parent_module_idx is None:
                self.emit_drivers()
                self.emit_top_ports(fragment)
                self.emit_undriven()
        else:
            assert False # :nocov:


def _emit_netlist(netlist: _nir.Netlist, design):
    NetlistEmitter(netlist, design).emit_fragment(design.fragment, None)


def _compute_net_flows(netlist: _nir.Netlist):
    # Computes the net flows for all modules of the netlist.
    #
    # The rules for net flows are as follows:
    #
    # - the modules that have a given net in their net_flow form a subtree of the hierarchy
    # - Internal is used in the root of the subtree and nowhere else
    # - Output is used for modules that contain the definition of the net, or are on the
    #   path from the definition to the root
    # - remaining modules have a flow of Input (unless the net is a top-level inout port,
    #   in which case it is Inout)
    #
    # In other words, the tree looks something like this:
    #
    # - [no flow] <<< top
    #   - [no flow]
    #   - Internal
    #     - Input << use
    #       - [no flow]
    #     - Input
    #       - Input << use
    #     - Output
    #       - Input << use
    #       - [no flow]
    #       - Output << def
    #         - Input
    #           - Input
    #         - [no flow]
    #   - [no flow]
    #   - [no flow]
    #
    # This function doesn't assign the Inout flow — that is corrected later, in compute_ports.
    lca = {}

    # Initialize by marking the definition point of every net.
    for cell_idx, cell in enumerate(netlist.cells):
        for net in cell.output_nets(cell_idx):
            lca[net] = cell.module_idx
            netlist.modules[cell.module_idx].net_flow[net] = _nir.ModuleNetFlow.Internal

    # Marks a use of a net within a given module, and adjusts its netflows in all modules
    # as required.
    def use_net(net, use_module):
        if net.is_const:
            return
        # If the net is already present in the current module, we're done.
        if net in netlist.modules[use_module].net_flow:
            return
        modules = netlist.modules
        # Otherwise, we need to route the net through the hierarchy from def_module
        # to use_module. We do that by treating use_module and def_module as pointers
        # and moving them up the hierarchy until they meet at the new LCA.
        def_module = lca[net]
        # While def_module deeper than use_module, go up with def_module.
        while len(modules[def_module].name) > len(modules[use_module].name):
            modules[def_module].net_flow[net] = _nir.ModuleNetFlow.Output
            def_module = modules[def_module].parent
        # While use_module deeper than def_module, go up with use_module.
        # If use_module is below def_module in the hierarchy, we may hit
        # another module which already uses this net before hitting def_module,
        # so check for this case.
        while len(modules[def_module].name) < len(modules[use_module].name):
            if net in modules[use_module].net_flow:
                return
            modules[use_module].net_flow[net] = _nir.ModuleNetFlow.Input
            use_module = modules[use_module].parent
        # Now both pointers should be at the same depth within the hierarchy.
        assert len(modules[def_module].name) == len(modules[use_module].name)
        # Move both pointers up until they meet.
        while def_module != use_module:
            modules[def_module].net_flow[net] = _nir.ModuleNetFlow.Output
            def_module = modules[def_module].parent
            modules[use_module].net_flow[net] = _nir.ModuleNetFlow.Input
            use_module = modules[use_module].parent
            assert len(modules[def_module].name) == len(modules[use_module].name)
        # And mark the new LCA.
        modules[def_module].net_flow[net] = _nir.ModuleNetFlow.Internal
        lca[net] = def_module

    # Now mark all uses and flesh out the structure.
    for cell in netlist.cells:
        for net in cell.input_nets():
            use_net(net, cell.module_idx)
    # TODO: ?
    for module_idx, module in enumerate(netlist.modules):
        for signal in module.signal_names:
            for net in netlist.signals[signal]:
                use_net(net, module_idx)


def _compute_ports(netlist: _nir.Netlist):
    # Compute the indexes at which the outputs of a cell should be split to create a distinct port.
    # These indexes are stored here as nets.
    port_starts = set()
    for start, _ in netlist.top.ports_i.values():
        port_starts.add(_nir.Net.from_cell(0, start))
    for start, width in netlist.top.ports_io.values():
        port_starts.add(_nir.Net.from_cell(0, start))
    for cell_idx, cell in enumerate(netlist.cells):
        if isinstance(cell, _nir.Instance):
            for start, _ in cell.ports_o.values():
                port_starts.add(_nir.Net.from_cell(cell_idx, start))

    # Compute the set of all inout nets. Currently, a net has inout flow iff it is connected to
    # a toplevel inout port.
    inouts = set()
    for start, width in netlist.top.ports_io.values():
        for idx in range(start, start + width):
            inouts.add(_nir.Net.from_cell(0, idx))

    for module in netlist.modules:
        # Collect preferred names for ports. If a port exactly matches a signal, we reuse
        # the signal name for the port. Otherwise, we synthesize a private name.
        name_table = {}
        for signal, name in module.signal_names.items():
            value = netlist.signals[signal]
            if value not in name_table and not name.startswith('$'):
                name_table[value] = name

        # Adjust any input flows to inout as necessary.
        for (net, flow) in module.net_flow.items():
            if flow == _nir.ModuleNetFlow.Input and net in inouts:
                module.net_flow[net] = _nir.ModuleNetFlow.Inout

        # Gather together "adjacent" nets with the same flow into ports.
        visited = set()
        for net in sorted(module.net_flow):
            flow = module.net_flow[net]
            if flow == _nir.ModuleNetFlow.Internal:
                continue
            if net in visited:
                continue
            # We found a net that needs a port. Keep joining the next nets output by the same
            # cell into the same port, if applicable, but stop at instance/top port boundaries.
            nets = [net]
            while True:
                succ = _nir.Net.from_cell(net.cell, net.bit + 1)
                if succ in port_starts:
                    break
                if succ not in module.net_flow:
                    break
                if module.net_flow[succ] != module.net_flow[net]:
                    break
                net = succ
                nets.append(net)
            value = _nir.Value(nets)
            # Joined as many nets as we could, now name and add the port.
            if value in name_table:
                name = name_table[value]
            else:
                name = f"port${value[0].cell}${value[0].bit}"
            module.ports[name] = (value, flow)
            visited.update(value)

    # The 0th cell and the 0th module correspond to the toplevel. Transfer the net flows from
    # the toplevel cell (used for data flow) to the toplevel module (used to split netlist into
    # modules in the backends).
    top_module = netlist.modules[0]
    for name, (start, width) in netlist.top.ports_i.items():
        top_module.ports[name] = (
            _nir.Value(_nir.Net.from_cell(0, start + bit) for bit in range(width)),
            _nir.ModuleNetFlow.Input
        )
    for name, (start, width) in netlist.top.ports_io.items():
        top_module.ports[name] = (
            _nir.Value(_nir.Net.from_cell(0, start + bit) for bit in range(width)),
            _nir.ModuleNetFlow.Inout
        )
    for name, value in netlist.top.ports_o.items():
        top_module.ports[name] = (value, _nir.ModuleNetFlow.Output)


def build_netlist(fragment, ports=(), *, name="top", **kwargs):
    if isinstance(fragment, Design):
        design = fragment
    else:
        design = fragment.prepare(ports=ports, hierarchy=(name,), **kwargs)
    netlist = _nir.Netlist()
    _emit_netlist(netlist, design)
    netlist.resolve_all_nets()
    _compute_net_flows(netlist)
    _compute_ports(netlist)
    return netlist
