from typing import Tuple
from collections import defaultdict, OrderedDict
import enum
import warnings

from .._utils import flatten, to_binary, final
from .. import tracer, _unused
from . import _ast, _cd, _ir, _nir


__all__ = [
    "AlreadyElaborated", "UnusedElaboratable", "Elaboratable", "DuplicateElaboratable",
    "DomainRequirementFailed", "DriverConflict",
    "Fragment", "Instance", "IOBufferInstance", "RequirePosedge", "PortDirection",
    "Design", "build_netlist",
]


@final
class AlreadyElaborated(Exception):
    """Exception raised when an elaboratable is being modified after elaboration."""


class UnusedElaboratable(_unused.UnusedMustUse):
    # The warning is initially silenced. If everything that has been constructed remains unused,
    # it means the application likely crashed (with an exception, or in another way that does not
    # call `sys.excepthook`), and it's not necessary to show any warnings.
    # Once elaboration starts, the warning is enabled.
    _MustUse__silence = True


class Elaboratable(_unused.MustUse):
    _MustUse__warning = UnusedElaboratable


class DriverConflict(Exception):
    pass


class DuplicateElaboratable(Exception):
    pass


class DomainRequirementFailed(Exception):
    """Raised when a module has unsatisfied requirements about a clock domain, such as getting
    a negedge domain when only posedge domains are supported."""


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
            else:
                raise TypeError(f"Object {obj!r} is not an 'Elaboratable' nor 'Fragment'")
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
        self.statements = {}
        self.domains = OrderedDict()
        self.subfragments = []
        self.attrs = OrderedDict()
        self.generated = OrderedDict()
        self.src_loc = src_loc
        self.origins = None
        self.domain_renames = {}

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

    def _propagate_domains_down(self, hierarchy=("top",)):
        # For each domain defined in this fragment, ensure it also exists in all subfragments.
        for i, (subfrag, name, src_loc) in enumerate(self.subfragments):
            hier_name = name
            if hier_name is None:
                hier_name = f"<unnamed #{i}>"

            for domain in self.iter_domains():
                if domain not in subfrag.domains:
                    subfrag.add_domains(self.domains[domain])

            subfrag._propagate_domains_down(hierarchy + (hier_name,))

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
        self._propagate_domains_down()
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
            if not isinstance(signal, (_ast.Signal, _ast.ClockSignal, _ast.ResetSignal, _ast.IOPort)):
                raise TypeError(f"Only signals and IO ports may be added as ports, not {signal!r}")

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

        self.type       = type
        self.parameters = OrderedDict()
        self.ports      = OrderedDict()

        for (kind, name, value) in args:
            if kind == "a":
                self.attrs[name] = value
            elif kind == "p":
                self.parameters[name] = value
            elif kind in ("i", "o", "io"):
                if kind == "io":
                    value = _ast.IOValue.cast(value)
                else:
                    if not isinstance(value, _ast.IOValue):
                        value = _ast.Value.cast(value)
                self.ports[name] = (value, kind)
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
                if not isinstance(arg, _ast.IOValue):
                    arg = _ast.Value.cast(arg)
                self.ports[kw[2:]] = (arg, "i")
            elif kw.startswith("o_"):
                if not isinstance(arg, _ast.IOValue):
                    arg = _ast.Value.cast(arg)
                self.ports[kw[2:]] = (arg, "o")
            elif kw.startswith("io_"):
                self.ports[kw[3:]] = (_ast.IOValue.cast(arg), "io")
            else:
                raise NameError("Instance keyword argument {}={!r} does not start with one of "
                                "\"a_\", \"p_\", \"i_\", \"o_\", or \"io_\""
                                .format(kw, arg))


class IOBufferInstance(Fragment):
    def __init__(self, port, *, i=None, o=None, oe=None, src_loc_at=0, src_loc=None):
        super().__init__()

        self.port = _ast.IOValue.cast(port)
        if i is None:
            self.i = None
        else:
            self.i = _ast.Value.cast(i)
            if len(self.port) != len(self.i):
                raise ValueError(f"'port' length ({len(self.port)}) doesn't match 'i' length ({len(self.i)})")
        if o is None:
            if oe is not None:
                raise ValueError("'oe' must not be used if 'o' is not used")
            self.o = None
            self.oe = None
        else:
            self.o = _ast.Value.cast(o)
            if len(self.port) != len(self.o):
                raise ValueError(f"'port' length ({len(self.port)}) doesn't match 'o' length ({len(self.o)})")
            if oe is None:
                self.oe = _ast.Const(1)
            else:
                self.oe = _ast.Value.cast(oe)
                if len(self.oe) != 1:
                    raise ValueError(f"'oe' length ({len(self.oe)}) must be 1")

        self.src_loc = src_loc or tracer.get_src_loc(src_loc_at)


class RequirePosedge(Fragment):
    """A special fragment that requires a given domain to have :py:`clk_edge="pos"`, failing
    elaboration otherwise.

    This is a private interface, without a stability guarantee.
    """

    def __init__(self, domain, *, src_loc_at=0, src_loc=None):
        super().__init__()
        self._domain = domain
        self.src_loc = src_loc or tracer.get_src_loc(src_loc_at)


def _add_name(assigned_names, name):
    if name in assigned_names:
        name = f"{name}${len(assigned_names)}"
        assert name not in assigned_names
    assigned_names.add(name)
    return name


class DesignFragmentInfo:
    def __init__(self, parent, depth):
        self.parent = parent
        self.depth = depth
        self.signal_names = _ast.SignalDict()
        self.io_port_names = {}
        # Fixed up later.
        self.name: "tuple[str]" = ()
        self.assigned_names = set()
        # These two are used as sets, but are stored as dicts to ensure deterministic iteration order.
        self.used_signals = _ast.SignalDict()
        self.used_io_ports = {}


class Design:
    """Represents a design ready for simulation or netlist building.

    Returned by ``Fragment.prepare``."""

    def __init__(self, fragment: Fragment, ports, *, hierarchy):
        self.fragment = fragment
        self.ports = list(ports)
        self.hierarchy = hierarchy
        self.fragments: dict[Fragment, DesignFragmentInfo] = {}
        self.signal_lca = _ast.SignalDict()
        self.elaboratables: dict[Elaboratable, Fragment] = {}
        self._compute_fragment_depth_parent(fragment, None, 0)
        self._collect_used_signals(fragment)
        self._add_io_ports()
        self._assign_port_names()
        for name, conn, dir in self.ports:
            if isinstance(conn, _ast.IOPort):
                self._use_io_port(fragment, conn)
            else:
                self._use_signal(fragment, conn)
        self._assign_names(fragment, hierarchy)
        self._check_domain_requires()

    def _compute_fragment_depth_parent(self, fragment: Fragment, parent: "Fragment | None", depth: int):
        """Recursively computes every fragment's depth and parent."""
        self.fragments[fragment] = DesignFragmentInfo(parent, depth)
        for subfragment, _name, _src_loc in fragment.subfragments:
            self._compute_fragment_depth_parent(subfragment, fragment, depth + 1)

    def _use_signal(self, fragment: Fragment, signal: _ast.Signal):
        """Marks a signal as used in a given fragment.

        Also marks a signal as used if it has to be routed through a given fragment to get from
        one part of hierarchy to another.  For this purpose, the ``self.signal_lca`` dictionary
        is maintained: for every signal, it stores the topmost fragment in which it has been
        marked used so far.
        """
        if signal in self.fragments[fragment].used_signals:
            return
        self.fragments[fragment].used_signals[signal] = None
        if signal not in self.signal_lca:
            # First time we see a signal.
            self.signal_lca[signal] = fragment
            return
        # Signal already seen — go from current fragment to the LCA, marking everything along
        # the way as used.
        lca = self.signal_lca[signal]
        # First, go up from our fragment until it is no deeper than current LCA.
        while self.fragments[lca].depth < self.fragments[fragment].depth:
            fragment = self.fragments[fragment].parent
            # Early return if we reach a part of tree where the signal is already marked.
            if signal in self.fragments[fragment].used_signals:
                return
            self.fragments[fragment].used_signals[signal] = None
        # Second, go up from current LCA until it is no deeper than our fragment.
        while self.fragments[lca].depth > self.fragments[fragment].depth:
            lca = self.fragments[lca].parent
            self.fragments[lca].used_signals[signal] = None
        # Now, both fragments are at the same depth. Go up from both until the two paths meet.
        while fragment is not lca:
            lca = self.fragments[lca].parent
            self.fragments[lca].used_signals[signal] = None
            fragment = self.fragments[fragment].parent
            self.fragments[fragment].used_signals[signal] = None
        self.signal_lca[signal] = lca

    def _use_io_port(self, fragment: Fragment, port: _ast.IOPort):
        """Marks an IO port as used in a given fragment and all its ancestors."""
        frag_info = self.fragments[fragment]
        if port in frag_info.used_io_ports:
            return
        frag_info.used_io_ports[port] = None
        if frag_info.parent is not None:
            self._use_io_port(frag_info.parent, port)

    def _collect_used_signals_format(self, fragment: Fragment, fmt: _ast.Format):
        for chunk in fmt._chunks:
            if not isinstance(chunk, str):
                obj, _spec = chunk
                self._collect_used_signals_value(fragment, obj)

    def _collect_used_signals_value(self, fragment: Fragment, value: _ast.Value):
        if isinstance(value, (_ast.Const, _ast.Initial, _ast.AnyValue)):
            pass
        elif isinstance(value, _ast.Signal):
            self._use_signal(fragment, value)
        elif isinstance(value, _ast.Operator):
            for op in value.operands:
                self._collect_used_signals_value(fragment, op)
        elif isinstance(value, _ast.Slice):
            self._collect_used_signals_value(fragment, value.value)
        elif isinstance(value, _ast.Part):
            self._collect_used_signals_value(fragment, value.value)
            self._collect_used_signals_value(fragment, value.offset)
        elif isinstance(value, _ast.SwitchValue):
            self._collect_used_signals_value(fragment, value.test)
            for _patterns, elem in value.cases:
                self._collect_used_signals_value(fragment, elem)
        elif isinstance(value, _ast.Concat):
            for part in value.parts:
                self._collect_used_signals_value(fragment, part)
        else:
            raise NotImplementedError # :nocov:

    def _collect_used_signals_io_value(self, fragment: Fragment, value: _ast.IOValue):
        if isinstance(value, _ast.IOPort):
            self._use_io_port(fragment, value)
        elif isinstance(value, _ast.IOSlice):
            self._collect_used_signals_io_value(fragment, value.value)
        elif isinstance(value, _ast.IOConcat):
            for part in value.parts:
                self._collect_used_signals_io_value(fragment, part)
        else:
            raise NotImplementedError # :nocov:

    def _collect_used_signals_stmt(self, fragment: Fragment, stmt: _ast.Statement):
        if isinstance(stmt, _ast.Assign):
            self._collect_used_signals_value(fragment, stmt.lhs)
            self._collect_used_signals_value(fragment, stmt.rhs)
        elif isinstance(stmt, _ast.Print):
            self._collect_used_signals_format(fragment, stmt.message)
        elif isinstance(stmt, _ast.Property):
            self._collect_used_signals_value(fragment, stmt.test)
            if stmt.message is not None:
                self._collect_used_signals_format(fragment, stmt.message)
        elif isinstance(stmt, _ast.Switch):
            self._collect_used_signals_value(fragment, stmt.test)
            for _patterns, stmts, _src_loc in stmt.cases:
                for s in stmts:
                    self._collect_used_signals_stmt(fragment, s)
        else:
            raise NotImplementedError # :nocov:

    def _collect_used_signals(self, fragment: Fragment):
        """Collects used signals and IO ports for a fragment and all its subfragments."""
        from . import _mem
        if isinstance(fragment, _ir.Instance):
            for conn, kind in fragment.ports.values():
                if isinstance(conn, _ast.IOValue):
                    self._collect_used_signals_io_value(fragment, conn)
                elif isinstance(conn, _ast.Value):
                    self._collect_used_signals_value(fragment, conn)
                else:
                    assert False # :nocov:
        elif isinstance(fragment, _ir.IOBufferInstance):
            self._collect_used_signals_io_value(fragment, fragment.port)
            if fragment.i is not None:
                self._collect_used_signals_value(fragment, fragment.i)
            if fragment.o is not None:
                self._collect_used_signals_value(fragment, fragment.o)
                self._collect_used_signals_value(fragment, fragment.oe)
        elif isinstance(fragment, _mem.MemoryInstance):
            for port in fragment._read_ports:
                self._collect_used_signals_value(fragment, port._addr)
                self._collect_used_signals_value(fragment, port._data)
                self._collect_used_signals_value(fragment, port._en)
                if port._domain != "comb":
                    domain = fragment.domains[port._domain]
                    self._use_signal(fragment, domain.clk)
                    if domain.rst is not None:
                        self._use_signal(fragment, domain.rst)
            for port in fragment._write_ports:
                self._collect_used_signals_value(fragment, port._addr)
                self._collect_used_signals_value(fragment, port._data)
                self._collect_used_signals_value(fragment, port._en)
                domain = fragment.domains[port._domain]
                self._use_signal(fragment, domain.clk)
                if domain.rst is not None:
                    self._use_signal(fragment, domain.rst)
        elif isinstance(fragment, _ir.RequirePosedge):
            pass
        else:
            for domain_name, statements in fragment.statements.items():
                if domain_name != "comb":
                    domain = fragment.domains[domain_name]
                    self._use_signal(fragment, domain.clk)
                    if domain.rst is not None:
                        self._use_signal(fragment, domain.rst)
                for statement in statements:
                    self._collect_used_signals_stmt(fragment, statement)
            for subfragment, _name, _src_loc in fragment.subfragments:
                self._collect_used_signals(subfragment)

    def _add_io_ports(self):
        """Adds all used IO ports to our list of top-level ports, if they aren't there already."""
        io_ports = {conn for name, conn, dir in self.ports if isinstance(conn, _ast.IOPort)}
        for port in self.fragments[self.fragment].used_io_ports:
            if port not in io_ports:
                self.ports.append((None, port, None))

    def _assign_port_names(self):
        """Assigns names to all ports that haven't been explicitly named."""
        new_ports = []
        assigned_names = {name for name, conn, dir in self.ports if name is not None}
        for name, conn, dir in self.ports:
            if name is None:
                if conn.name == "": # Nothing to name this port!
                    raise TypeError("Signals with private names cannot be used in unnamed top-level ports")
                name = _add_name(assigned_names, conn.name)
                assigned_names.add(name)
            new_ports.append((name, conn, dir))
        self.ports = new_ports

    def _assign_names(self, fragment: Fragment, hierarchy: "tuple[str]"):
        """Assign names to signals and IO ports used in a given fragment, as well as its
        subfragments.

        The signal mapping is set in ``self.signal_names``, and the IO port mapping is set in
        ``self.io_port_names``.  Because names are deduplicated using local information only,
        the same signal used in a different fragment may get a different name.

        Subfragments may not necessarily have a name. This method assigns every such subfragment
        a name, ``U$<number>``, where ``<number>`` is based on its location in the hierarchy.

        Subfragment names may collide with signal names safely in Amaranth, but this may confuse
        backends. This method assigns every such subfragment a new name.

        Arguments
        ---------
        hierarchy : tuple of str
            Name of this fragment.
        """

        frag_info = self.fragments[fragment]
        frag_info.name = hierarchy

        if fragment.origins is not None:
            for origin in fragment.origins:
                if origin in self.elaboratables:
                    other_hierarchy = self.fragments[self.elaboratables[origin]].name
                    raise DuplicateElaboratable(f"Elaboratable {origin!r} is included twice "
                                                f"in the hierarchy, as {'.'.join(other_hierarchy)} "
                                                f"and {'.'.join(hierarchy)}")
                self.elaboratables[origin] = fragment

        if fragment is self.fragment:
            # Reserve names for top-level ports. If equal to the signal name, let the signal share it.
            for name, conn, _dir in self.ports:
                frag_info.assigned_names.add(name)
                if isinstance(conn, _ast.Signal) and conn.name == name:
                    frag_info.signal_names[conn] = name
                elif isinstance(conn, _ast.IOPort) and conn.name == name:
                    frag_info.io_port_names[conn] = name

        for signal in frag_info.used_signals:
            if signal not in frag_info.signal_names and signal.name != "": # Private name shouldn't be added.
                frag_info.signal_names[signal] = _add_name(frag_info.assigned_names, signal.name)
        for port in frag_info.used_io_ports:
            if port not in frag_info.io_port_names:
                frag_info.io_port_names[port] = _add_name(frag_info.assigned_names, port.name)

        for subfragment_index, (subfragment, subfragment_name, subfragment_src_loc) in enumerate(fragment.subfragments):
            if subfragment_name is None:
                subfragment_name = f"U${subfragment_index}"
            subfragment_name = _add_name(frag_info.assigned_names, subfragment_name)
            self._assign_names(subfragment, hierarchy=(*hierarchy, subfragment_name))

    def _check_domain_requires(self):
        for fragment, fragment_info in self.fragments.items():
            if isinstance(fragment, RequirePosedge):
                domain = fragment.domains[fragment._domain]
                if domain.clk_edge != "pos":
                    if fragment.src_loc is None:
                        src_loc = "<unknown>:0"
                    else:
                        src_loc = f"{fragment.src_loc[0]}:{fragment.src_loc[1]}"
                    fragment_name = ".".join(fragment_info.name)
                    raise DomainRequirementFailed(f"Domain {domain.name} has a negedge clock, but posedge clock is required by {fragment_name} at {src_loc}")

    def lookup_domain(self, domain, context):
        if domain == "comb":
            raise KeyError("comb")
        if context is not None:
            try:
                fragment = self.elaboratables[context]
            except KeyError:
                raise ValueError(f"Elaboratable {context!r} is not a part of the design")
        else:
            fragment = self.fragment
        domain = fragment.domain_renames.get(domain, domain)
        return fragment.domains[domain]


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

    def emit_value(self, builder, chunk_start, chunk_end):
        chunk_len = chunk_end - chunk_start
        if self.domain is None:
            init = _ast.Const(self.signal.init, len(self.signal))
            default, _signed = builder.emit_rhs(self.module_idx, init)
        else:
            default = builder.emit_signal(self.signal)
        default = default[chunk_start:chunk_end]
        assignments = []
        for assign in self.assignments:
            if assign.start >= chunk_end:
                continue
            if assign.start + len(assign.value) <= chunk_start:
                continue
            if assign.cond == 1 and assign.start == chunk_start and len(assign.value) == chunk_len and len(assignments) == 0:
                default = assign.value
            else:
                if assign.start < chunk_start:
                    start = 0
                    value = assign.value[chunk_start - assign.start:]
                else:
                    start = assign.start - chunk_start
                    value = assign.value
                if start + len(value) > chunk_len:
                    value = value[:chunk_len - start]
                assignments.append(_nir.Assignment(
                    cond=assign.cond,
                    start=start,
                    value=value,
                    src_loc=assign.src_loc
                ))
        if len(assignments) == 0:
            return default
        cell = _nir.AssignmentList(self.module_idx, default=default, assignments=assignments,
                                   src_loc=self.signal.src_loc)
        return builder.netlist.add_value_cell(len(default), cell)


class NetlistEmitter:
    def __init__(self, netlist: _nir.Netlist, design: Design, *, all_undef_to_ff=False):
        self.netlist = netlist
        self.design = design
        self.all_undef_to_ff = all_undef_to_ff
        # SignalDict from Signal to dict from (module index, ClockDomain | None) to NetlistDriver
        self.drivers = _ast.SignalDict()
        self.io_ports: dict[_ast.IOPort, int] = {}
        self.rhs_cache: dict[int, tuple[_nir.Value, bool, _ast.Value]] = {}
        self.match_cache = {}
        self.fragment_module_idx: dict[Fragment, int] = {}

        # Collected for driver conflict diagnostics only.
        self.late_net_to_signal = {}
        self.connect_src_loc = {}
        self.ionet_src_loc = {}

    def emit_signal(self, signal) -> _nir.Value:
        if signal in self.netlist.signals:
            return self.netlist.signals[signal]
        value = self.netlist.alloc_late_value(signal)
        self.netlist.signals[signal] = value
        for bit, net in enumerate(value):
            self.late_net_to_signal[net] = (signal, bit)
        return value

    def emit_io(self, value: _ast.IOValue) -> _nir.IOValue:
        if isinstance(value, _ast.IOPort):
            if value not in self.io_ports:
                port = len(self.netlist.io_ports)
                self.netlist.io_ports.append(value)
                self.io_ports[value] = _nir.IOValue(
                    _nir.IONet.from_port(port, bit)
                    for bit in range(0, len(value))
                )
            return self.io_ports[value]
        elif isinstance(value, _ast.IOConcat):
            result = []
            for part in value.parts:
                result += self.emit_io(part)
            return _nir.IOValue(result)
        elif isinstance(value, _ast.IOSlice):
            return self.emit_io(value.value)[value.start:value.stop]
        else:
            raise TypeError # :nocov:

    def emit_io_use(self, value: _ast.IOValue, *, src_loc) -> _nir.IOValue:
        res = self.emit_io(value)
        for net in res:
            if net not in self.ionet_src_loc:
                self.ionet_src_loc[net] = src_loc
            else:
                prev_src_loc = self.ionet_src_loc[net]
                port = self.netlist.io_ports[net.port]
                raise DriverConflict(f"Bit {net.bit} of I/O port {port!r} used twice, at "
                                     f"{prev_src_loc[0]}:{prev_src_loc[1]} and {src_loc[0]}:{src_loc[1]}")
        return res

    # Used for instance outputs and read port data, not used for actual assignments.
    def emit_lhs(self, value: _ast.Value):
        if isinstance(value, _ast.Signal):
            return self.emit_signal(value)
        elif isinstance(value, _ast.Concat):
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

    def emit_match(self, module_idx: int, en: _nir.Net, value: _nir.Value, patterns, *, src_loc):
        key = module_idx, en, value, patterns, src_loc
        try:
            return self.match_cache[key]
        except KeyError:
            cell = _nir.Match(module_idx, en=en, value=value, patterns=patterns, src_loc=src_loc)
            res = self.netlist.add_value_cell(len(patterns), cell)
            self.match_cache[key] = res
            return res

    def unify_shapes_bitwise(self,
            operand_a: _nir.Value, signed_a: bool, operand_b: _nir.Value, signed_b: bool):
        shape = _ast.Shape._unify((
            _ast.Shape(len(operand_a), signed_a),
            _ast.Shape(len(operand_b), signed_b),
        ))
        operand_a = self.extend(operand_a, signed_a, shape.width)
        operand_b = self.extend(operand_b, signed_b, shape.width)
        return (operand_a, operand_b, shape.signed)

    def emit_rhs(self, module_idx: int, value: _ast.Value) -> tuple[_nir.Value, bool]:
        """Emits a RHS value, returns a tuple of (value, is_signed)"""
        try:
            result, signed, value = self.rhs_cache[id(value)]
            return result, signed
        except KeyError:
            pass
        if isinstance(value, _ast.Const):
            shape  = value.shape()
            result = _nir.Value.from_const(value.value, shape.width)
            signed = shape.signed
        elif isinstance(value, _ast.Signal):
            shape  = value.shape()
            result = self.emit_signal(value)
            signed = shape.signed
        elif isinstance(value, _ast.Operator):
            if len(value.operands) == 1:
                operand_a, signed_a = self.emit_rhs(module_idx, value.operands[0])
                if value.operator == 's':
                    result = operand_a
                    signed = True
                elif value.operator == 'u':
                    result = operand_a
                    signed = False
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
        elif isinstance(value, _ast.SwitchValue):
            test, _signed = self.emit_rhs(module_idx, value.test)
            if (len(value.cases) == 2 and
                    value.cases[0][0] == ("0" * len(test),) and
                    value.cases[1][0] is None):
                operand_a, signed_a = self.emit_rhs(module_idx, value.cases[1][1])
                operand_b, signed_b = self.emit_rhs(module_idx, value.cases[0][1])
                if len(test) != 1:
                    test = self.emit_operator(module_idx, 'b', test, src_loc=value.src_loc)
                operand_a, operand_b, signed = \
                    self.unify_shapes_bitwise(operand_a, signed_a, operand_b, signed_b)
                result = self.emit_operator(module_idx, 'm', test, operand_a, operand_b,
                                            src_loc=value.src_loc)
            else:
                elems = []
                patterns = []
                for pattern_list, elem, in value.cases:
                    if pattern_list is not None:
                        patterns.append(pattern_list)
                    else:
                        patterns.append(("-" * len(test),))
                    elems.append(self.emit_rhs(module_idx, elem))
                conds = self.emit_match(module_idx, _nir.Net.from_const(1), test, tuple(patterns),
                                        src_loc=value.src_loc)
                shape = _ast.Shape._unify(
                    _ast.Shape(len(value), signed)
                    for value, signed in elems
                )
                elems = tuple(self.extend(elem, elem_signed, shape.width) for elem, elem_signed in elems)
                assignments = [
                    _nir.Assignment(cond=subcond, start=0, value=elem, src_loc=value.src_loc)
                    for subcond, elem in zip(conds, elems)
                ]
                cell = _nir.AssignmentList(module_idx, default=_nir.Value.from_const(0, shape.width),
                                           assignments=assignments, src_loc=value.src_loc)
                result = self.netlist.add_value_cell(shape.width, cell)
                signed = shape.signed
        elif isinstance(value, _ast.Concat):
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
                                         f"{other_src_loc[0]}:{other_src_loc[1]} and {src_loc[0]}:{src_loc[1]}")
            self.netlist.connections[left] = right
            self.connect_src_loc[left] = src_loc

    def emit_assign(self, module_idx: int, cd: "_cd.ClockDomain | None", lhs: _ast.Value, lhs_start: int, rhs: _nir.Value, cond: _nir.Net, *, src_loc):
        # Assign rhs to lhs[lhs_start:lhs_start+len(rhs)]
        if isinstance(lhs, _ast.Signal):
            sig_drivers = self.drivers.setdefault(lhs, {})
            key = (module_idx, cd)
            if key in sig_drivers:
                driver = sig_drivers[key]
            else:
                driver = NetlistDriver(module_idx, lhs, domain=cd, src_loc=src_loc)
                sig_drivers[key] = driver
            driver.assignments.append(_nir.Assignment(cond=cond, start=lhs_start, value=rhs,
                                                      src_loc=src_loc))
        elif isinstance(lhs, _ast.Slice):
            self.emit_assign(module_idx, cd, lhs.value, lhs_start + lhs.start, rhs, cond, src_loc=src_loc)
        elif isinstance(lhs, _ast.Concat):
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
            patterns = []
            for case_index in range(num_cases):
                patterns.append((to_binary(case_index, len(offset)),))
            conds = self.emit_match(module_idx, cond, offset, tuple(patterns), src_loc=lhs.src_loc)
            for idx, subcond in enumerate(conds):
                start = lhs_start + idx * lhs.stride
                if start >= width:
                    continue
                if start + len(rhs) >= width:
                    subrhs = rhs[:width - start]
                else:
                    subrhs = rhs
                self.emit_assign(module_idx, cd, lhs.value, start, subrhs, subcond, src_loc=src_loc)
        elif isinstance(lhs, _ast.SwitchValue):
            test, _signed = self.emit_rhs(module_idx, lhs.test)
            patterns = []
            elems = []
            for pattern_list, elem in lhs.cases:
                if pattern_list is not None:
                    patterns.append(pattern_list)
                else:
                    patterns.append(("-" * len(test),))
                elems.append(elem)
            conds = self.emit_match(module_idx, cond, test, tuple(patterns), src_loc=lhs.src_loc)
            for subcond, val in zip(conds, elems):
                self.emit_assign(module_idx, cd, val, lhs_start, rhs[:len(val)], subcond, src_loc=src_loc)
        elif isinstance(lhs, _ast.Operator):
            assert lhs.operator in ('u', 's')
            self.emit_assign(module_idx, cd, lhs.operands[0], lhs_start, rhs, cond, src_loc=src_loc)
        else:
            assert False # :nocov:

    def emit_format(self, module_idx, format):
        chunks = []
        for chunk in format._chunks:
            if isinstance(chunk, str):
                chunks.append(chunk)
            else:
                value, format_desc = chunk
                value, signed = self.emit_rhs(module_idx, value)
                chunks.append(_nir.FormatValue(value, format_desc, signed=signed))
        return _nir.Format(chunks)

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
        elif isinstance(stmt, _ast.Print):
            en_cell = _nir.AssignmentList(module_idx,
                default=_nir.Value.zeros(),
                assignments=[
                    _nir.Assignment(cond=cond, start=0, value=_nir.Value.ones(),
                                    src_loc=stmt.src_loc)
                ],
                src_loc=stmt.src_loc)
            cond, = self.netlist.add_value_cell(1, en_cell)
            format = self.emit_format(module_idx, stmt.message)
            if cd is None:
                cell = _nir.AsyncPrint(module_idx, en=cond,
                                       format=format, src_loc=stmt.src_loc)
            else:
                clk, = self.emit_signal(cd.clk)
                cell = _nir.SyncPrint(module_idx, en=cond,
                                      clk=clk, clk_edge=cd.clk_edge,
                                      format=format, src_loc=stmt.src_loc)
            self.netlist.add_cell(cell)
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
            if stmt.message is None:
                format = None
            else:
                format = self.emit_format(module_idx, stmt.message)
            if cd is None:
                cell = _nir.AsyncProperty(module_idx, kind=stmt.kind.value, test=test, en=cond,
                                          format=format, src_loc=stmt.src_loc)
            else:
                clk, = self.emit_signal(cd.clk)
                cell = _nir.SyncProperty(module_idx, kind=stmt.kind.value, test=test, en=cond,
                                         clk=clk, clk_edge=cd.clk_edge,
                                         format=format, src_loc=stmt.src_loc)
            self.netlist.add_cell(cell)
        elif isinstance(stmt, _ast.Switch):
            test, _signed = self.emit_rhs(module_idx, stmt.test)
            patterns = []
            case_stmts = []
            for pattern_list, stmts, case_src_loc in stmt.cases:
                if pattern_list is not None:
                    patterns.append(pattern_list)
                else:
                    patterns.append(("-" * len(test),))
                case_stmts.append(stmts)
            conds = self.emit_match(module_idx, cond, test, tuple(patterns), src_loc=stmt.src_loc)
            for subcond, substmts in zip(conds, case_stmts):
                for substmt in substmts:
                    self.emit_stmt(module_idx, fragment, domain, substmt, subcond)
        else:
            assert False # :nocov:

    def emit_iobuffer(self, module_idx: int, instance: _ir.IOBufferInstance):
        port = self.emit_io_use(instance.port, src_loc=instance.src_loc)
        if instance.o is None:
            o = None
            oe = None
            dir = _nir.IODirection.Input
        else:
            o, _signed = self.emit_rhs(module_idx, instance.o)
            (oe,), _signed = self.emit_rhs(module_idx, instance.oe)
            assert len(port) == len(o)
            if instance.i is None:
                dir = _nir.IODirection.Output
            else:
                dir = _nir.IODirection.Bidir
        cell = _nir.IOBuffer(module_idx, port=port, dir=dir, o=o, oe=oe, src_loc=instance.src_loc)
        value = self.netlist.add_value_cell(len(port), cell)
        if instance.i is not None:
            self.connect(self.emit_lhs(instance.i), value, src_loc=instance.src_loc)

    def emit_memory(self, module_idx: int, fragment: '_mem.MemoryInstance', name: str):
        cell = _nir.Memory(module_idx,
            width=_ast.Shape.cast(fragment._data._shape).width,
            depth=fragment._data._depth,
            init=fragment._data._init._raw,
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
        for port_name, (port_conn, dir) in instance.ports.items():
            if isinstance(port_conn, _ast.IOValue):
                if dir == 'i':
                    xlat_dir = _nir.IODirection.Input
                elif dir == 'o':
                    xlat_dir = _nir.IODirection.Output
                elif dir == 'io':
                    xlat_dir = _nir.IODirection.Bidir
                else:
                    assert False # :nocov:
                ports_io[port_name] = (self.emit_io_use(port_conn, src_loc=instance.src_loc), xlat_dir)
            elif dir == 'i':
                ports_i[port_name], _signed = self.emit_rhs(module_idx, port_conn)
            elif dir == 'o':
                port_conn = self.emit_lhs(port_conn)
                ports_o[port_name] = (next_output_bit, len(port_conn))
                outputs.append((next_output_bit, port_conn))
                next_output_bit += len(port_conn)
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
        next_input_bit = 2 # 0 and 1 are reserved for constants
        top = self.netlist.top

        for name, signal, dir in self.design.ports:
            if isinstance(signal, _ast.IOPort):
                continue
            signal_value = self.emit_signal(signal)
            if dir is None:
                is_driven = False
                for net in signal_value:
                    if net in self.netlist.connections:
                        is_driven = True
                if is_driven:
                    dir = PortDirection.Output
                else:
                    dir = PortDirection.Input
            if dir == PortDirection.Input:
                top.ports_i[name] = (next_input_bit, len(signal))
                value = _nir.Value(
                    _nir.Net.from_cell(0, bit)
                    for bit in range(next_input_bit, next_input_bit + len(signal))
                )
                next_input_bit += len(signal)
                self.connect(signal_value, value, src_loc=signal.src_loc)
            elif dir == PortDirection.Output:
                top.ports_o[name] = signal_value
            elif dir == PortDirection.Inout:
                raise ValueError(f"Port direction 'Inout' can only be used for 'IOPort', not 'Signal'")
            else:
                raise ValueError(f"Invalid port direction {dir!r}")

    def emit_signal_fields(self):
        for signal, fragment in self.design.signal_lca.items():
            module_idx = self.fragment_module_idx[fragment]
            fields = {}
            def emit_format(path, fmt):
                if isinstance(fmt, _ast.Format):
                    specs = [
                        chunk[0]
                        for chunk in fmt._chunks
                        if not isinstance(chunk, str)
                    ]
                    if len(specs) != 1:
                        return
                    val, signed = self.emit_rhs(module_idx, specs[0])
                    fields[path] = _nir.SignalField(val, signed=signed)
                elif isinstance(fmt, _ast.Format.Enum):
                    val, signed = self.emit_rhs(module_idx, fmt._value)
                    fields[path] = _nir.SignalField(val, signed=signed,
                                                    enum_name=fmt._name,
                                                    enum_variants=fmt._variants)
                elif isinstance(fmt, _ast.Format.Struct):
                    val, signed = self.emit_rhs(module_idx, fmt._value)
                    fields[path] = _nir.SignalField(val, signed=signed)
                    for name, subfmt in fmt._fields.items():
                        emit_format(path + (name,), subfmt)
                elif isinstance(fmt, _ast.Format.Array):
                    val, signed = self.emit_rhs(module_idx, fmt._value)
                    fields[path] = _nir.SignalField(val, signed=signed)
                    for idx, subfmt in enumerate(fmt._fields):
                        emit_format(path + (idx,), subfmt)
            emit_format((), signal._format)
            val, signed = self.emit_rhs(module_idx, signal)
            if () not in fields or fields[()].value != val:
                fields[()] = _nir.SignalField(val, signed=signed)
            self.netlist.signal_fields[signal] = fields

    def emit_drivers(self):
        for sig, sig_drivers in self.drivers.items():
            driven_bits = [None] * len(sig)
            for driver in sig_drivers.values():
                lhs = self.emit_signal(driver.signal)
                if len(sig_drivers) == 1 and all(net not in self.netlist.connections for net in lhs):
                    # If the signal is only assigned from one (module, clock domain) pair, and is
                    # also not driven by any instance, extend this driver to cover all bits of
                    # the signal for nicer netlist output.
                    driver_mask = (1 << len(sig)) - 1
                    driver_bit_start = 0
                    driver_bit_stop = len(sig)
                else:
                    # Otherwise, per-bit assignment it is.
                    driver_mask = 0
                    driver_bit_start = len(sig)
                    driver_bit_stop = 0
                    for assign in driver.assignments:
                        for bit in range(assign.start, assign.start + len(assign.value)):
                            driver_mask |= 1 << bit
                            # The conflict would be caught by connect anyway, but we can have
                            # a slightly better error message this way (showing the exact colliding
                            # domains)
                            if driven_bits[bit] is not None:
                                other_module_idx, other_domain, other_src_loc = driven_bits[bit]
                                if other_domain != driver.domain:
                                    domain_name = driver.domain.name if driver.domain is not None else "comb"
                                    other_domain_name = other_domain.name if other_domain is not None else "comb"
                                    raise _ir.DriverConflict(
                                        f"Signal {sig!r} bit {bit} driven from domain {domain_name} at "
                                        f"{assign.src_loc[0]}:{assign.src_loc[1]} and domain "
                                        f"{other_domain_name} at {other_src_loc[0]}:{other_src_loc[1]}")
                                if other_module_idx != driver.module_idx:
                                    mod_name = ".".join(self.netlist.modules[driver.module_idx].name or ("<toplevel>",))
                                    other_mod_name = \
                                        ".".join(self.netlist.modules[other_module_idx].name or ("<toplevel>",))
                                    raise _ir.DriverConflict(
                                        f"Signal {sig!r} bit {bit} driven from module {mod_name} at "
                                        f"{assign.src_loc[0]}:{assign.src_loc[1]} and "
                                        f"module {other_mod_name} at "
                                        f"{other_src_loc[0]}:{other_src_loc[1]}")
                            else:
                                driven_bits[bit] = (driver.module_idx, driver.domain, assign.src_loc)

                driver_chunks = []
                pos = 0
                while pos < len(sig):
                    if driver_mask & 1 << pos:
                        end_pos = pos
                        while driver_mask & 1 << end_pos:
                            end_pos += 1
                        driver_chunks.append((pos, end_pos))
                        pos = end_pos
                    else:
                        pos += 1


                if (driver.domain is not None and
                        driver.domain.rst is not None and
                        not driver.domain.async_reset and
                        not driver.signal.reset_less):
                    cond, = self.emit_match(driver.module_idx, _nir.Net.from_const(1),
                                            self.emit_signal(driver.domain.rst),
                                            (("1",),),
                                            src_loc=driver.domain.rst.src_loc)
                    init = _nir.Value.from_const(driver.signal.init, len(driver.signal))
                    driver.assignments.append(_nir.Assignment(cond=cond, start=0,
                                                            value=init, src_loc=driver.signal.src_loc))

                for chunk_start, chunk_end in driver_chunks:
                    chunk_len = chunk_end - chunk_start
                    chunk_mask = (1 << chunk_len) - 1

                    value = driver.emit_value(self, chunk_start, chunk_end)
                    if driver.domain is not None:
                        clk, = self.emit_signal(driver.domain.clk)
                        if driver.domain.rst is not None and driver.domain.async_reset and not driver.signal.reset_less:
                            arst, = self.emit_signal(driver.domain.rst)
                        else:
                            arst = _nir.Net.from_const(0)
                        cell = _nir.FlipFlop(driver.module_idx,
                            data=value,
                            init=(driver.signal.init >> chunk_start) & chunk_mask,
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

                    self.connect(lhs[chunk_start:chunk_end], value, src_loc=src_loc)

    def emit_undef_ff(self):
        # Connect all completely undriven signals to flip-flops with const-0 clock. This is used
        # for simulation targets, so that undriven signals have allocated storage that can be
        # used by the testbench to drive them, instead of being hardwired to the init value
        # constant.
        for signal, value in self.netlist.signals.items():
            fragment = self.design.signal_lca[signal]
            module_idx = self.fragment_module_idx[fragment]
            pos = 0
            while pos < len(signal):
                net = value[pos]
                if not net.is_late or net in self.netlist.connections:
                    pos += 1
                else:
                    end_pos = pos
                    while (end_pos < len(signal) and
                            value[end_pos].is_late and
                            value[end_pos] not in self.netlist.connections):
                        end_pos += 1
                    init = (signal.init >> pos) & ((1 << (end_pos - pos)) - 1)
                    cell = _nir.FlipFlop(module_idx,
                        data=value[pos:end_pos],
                        init=init,
                        clk=_nir.Net.from_const(0),
                        clk_edge="pos",
                        arst=_nir.Net.from_const(0),
                        attributes={},
                        src_loc=signal.src_loc,
                    )
                    ff_value = self.netlist.add_value_cell(end_pos - pos, cell)
                    self.connect(value[pos:end_pos], ff_value, src_loc=signal.src_loc)
                    pos = end_pos

    def emit_undriven(self):
        # Connect all undriven signal bits to their initial values. This can only happen for entirely
        # undriven signals, or signals that are partially driven by instances.
        for signal, value in self.netlist.signals.items():
            for bit, net in enumerate(value):
                if net.is_late and net not in self.netlist.connections:
                    self.netlist.connections[net] = _nir.Net.from_const((signal.init >> bit) & 1)

    def emit_fragment(self, fragment: _ir.Fragment, parent_module_idx: 'int | None', *, cell_src_loc=None):
        from . import _mem

        fragment_name = self.design.fragments[fragment].name
        if isinstance(fragment, _ir.Instance):
            assert parent_module_idx is not None
            self.emit_instance(parent_module_idx, fragment, name=fragment_name[-1])
            self.fragment_module_idx[fragment] = parent_module_idx
        elif isinstance(fragment, _mem.MemoryInstance):
            assert parent_module_idx is not None
            memory = self.emit_memory(parent_module_idx, fragment, name=fragment_name[-1])
            write_ports = []
            for port in fragment._write_ports:
                write_ports.append(self.emit_write_port(parent_module_idx, fragment, port, memory))
            for port in fragment._read_ports:
                self.emit_read_port(parent_module_idx, fragment, port, memory, write_ports)
            self.fragment_module_idx[fragment] = parent_module_idx
        elif isinstance(fragment, _ir.IOBufferInstance):
            assert parent_module_idx is not None
            self.emit_iobuffer(parent_module_idx, fragment)
            self.fragment_module_idx[fragment] = parent_module_idx
        elif isinstance(fragment, _ir.RequirePosedge):
            pass
        elif type(fragment) is _ir.Fragment:
            module_idx = self.netlist.add_module(parent_module_idx, fragment_name, src_loc=fragment.src_loc, cell_src_loc=cell_src_loc)
            self.fragment_module_idx[fragment] = module_idx
            signal_names = self.design.fragments[fragment].signal_names
            self.netlist.modules[module_idx].signal_names = signal_names
            io_port_names = self.design.fragments[fragment].io_port_names
            self.netlist.modules[module_idx].io_port_names = io_port_names
            for signal in signal_names:
                self.emit_signal(signal)
            for port in io_port_names:
                self.emit_io(port)
            for domain, stmts in fragment.statements.items():
                for stmt in stmts:
                    self.emit_stmt(module_idx, fragment, domain, stmt, _nir.Net.from_const(1))
            for subfragment, _name, sub_src_loc in fragment.subfragments:
                self.emit_fragment(subfragment, module_idx, cell_src_loc=sub_src_loc)
            if parent_module_idx is None:
                self.emit_signal_fields()
                self.emit_drivers()
                self.emit_top_ports(fragment)
                if self.all_undef_to_ff:
                    self.emit_undef_ff()
                self.emit_undriven()
        else:
            assert False # :nocov:


def _emit_netlist(netlist: _nir.Netlist, design, *, all_undef_to_ff=False):
    NetlistEmitter(netlist, design, all_undef_to_ff=all_undef_to_ff).emit_fragment(design.fragment, None)


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
    for cell_idx, cell in enumerate(netlist.cells):
        if isinstance(cell, _nir.Instance):
            for start, _ in cell.ports_o.values():
                port_starts.add(_nir.Net.from_cell(cell_idx, start))

    for module in netlist.modules:
        # Collect preferred names for ports. If a port exactly matches a signal, we reuse
        # the signal name for the port. Otherwise, we synthesize a private name.
        name_table = {}
        for signal, name in module.signal_names.items():
            value = netlist.signals[signal]
            if value not in name_table and not name.startswith('$'):
                name_table[value] = name

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
    for name, value in netlist.top.ports_o.items():
        top_module.ports[name] = (value, _nir.ModuleNetFlow.Output)


def _compute_ionet_dirs(netlist: _nir.Netlist):
    # Collects the direction of every IO net, for every module it needs to be routed through.
    for cell in netlist.cells:
        for (net, dir) in cell.io_nets():
            module_idx = cell.module_idx
            while module_idx is not None:
                netlist.modules[module_idx].ionet_dir[net] = dir
                module_idx = netlist.modules[module_idx].parent


def _compute_io_ports(netlist: _nir.Netlist, ports):
    io_ports = {
        port: _nir.IOValue(_nir.IONet.from_port(idx, bit) for bit in range(len(port)))
        for idx, port in enumerate(netlist.io_ports)
    }
    for module in netlist.modules:
        if module.parent is None:
            # Top module gets special treatment: each IOPort is added in its entirety.
            for (name, port, dir) in ports:
                dir = {
                    PortDirection.Input: _nir.IODirection.Input,
                    PortDirection.Output: _nir.IODirection.Output,
                    PortDirection.Inout: _nir.IODirection.Bidir,
                    None: None,
                }[dir]
                if not isinstance(port, _ast.IOPort):
                    continue
                auto_dir = None
                for net in io_ports[port]:
                    if net in module.ionet_dir:
                        if auto_dir is None:
                            auto_dir = module.ionet_dir[net]
                        else:
                            auto_dir |= module.ionet_dir[net]
                if dir is None:
                    dir = auto_dir
                    if auto_dir is None:
                        dir = _nir.IODirection.Bidir
                else:
                    if auto_dir is not None and (auto_dir | dir) != dir:
                        raise ValueError(f"Port {name} is {dir.value}, but is used as {auto_dir.value}")
                module.io_ports[name] = (io_ports[port], dir)
        else:
            # Collect preferred names for ports. If a port exactly matches a signal, we reuse
            # the signal name for the port. Otherwise, we synthesize a private name.
            name_table = {}
            for port, name in module.io_port_names.items():
                value = io_ports[port]
                if value not in name_table and not name.startswith('$'):
                    name_table[value] = name

            # Gather together "adjacent" nets with the same flow into ports.
            visited = set()
            for net in sorted(module.ionet_dir):
                dir = module.ionet_dir[net]
                if net in visited:
                    continue
                # We found a net that needs a port. Keep joining the next nets output by the same
                # cell into the same port, if applicable, but stop at instance/top port boundaries.
                nets = [net]
                while True:
                    succ = _nir.IONet.from_port(net.port, net.bit + 1)
                    if succ not in module.ionet_dir:
                        break
                    if module.ionet_dir[succ] != module.ionet_dir[net]:
                        break
                    net = succ
                    nets.append(net)
                value = _nir.IOValue(nets)
                # Joined as many nets as we could, now name and add the port.
                if value in name_table:
                    name = name_table[value]
                else:
                    name = f"ioport${value[0].port}${value[0].bit}"
                module.io_ports[name] = (value, dir)
                visited.update(value)


def build_netlist(fragment, ports=(), *, name="top", all_undef_to_ff=False, **kwargs):
    if isinstance(fragment, Design):
        design = fragment
    else:
        design = fragment.prepare(ports=ports, hierarchy=(name,), **kwargs)
    netlist = _nir.Netlist()
    _emit_netlist(netlist, design, all_undef_to_ff=all_undef_to_ff)
    netlist.check_comb_cycles()
    netlist.resolve_all_nets()
    _compute_net_flows(netlist)
    _compute_ports(netlist)
    _compute_ionet_dirs(netlist)
    _compute_io_ports(netlist, design.ports)
    return netlist
