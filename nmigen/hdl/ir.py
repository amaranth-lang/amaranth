import warnings
from collections import defaultdict, OrderedDict

from ..tools import *
from .ast import *
from .cd import *


__all__ = ["Fragment", "Instance", "DriverConflict"]


class DriverConflict(UserWarning):
    pass


class Fragment:
    @staticmethod
    def get(obj, platform):
        if isinstance(obj, Fragment):
            return obj
        if not hasattr(obj, "elaborate"): # :deprecated:
            return Fragment.get(obj.get_fragment(platform), platform)
        return Fragment.get(obj.elaborate(platform), platform)

    def __init__(self):
        self.ports = SignalDict()
        self.drivers = OrderedDict()
        self.statements = []
        self.domains = OrderedDict()
        self.subfragments = []
        self.generated = OrderedDict()
        self.flatten = False

    def add_ports(self, *ports, dir):
        assert dir in ("i", "o", "io")
        for port in flatten(ports):
            self.ports[port] = dir

    def iter_ports(self, dir=None):
        if dir is None:
            yield from self.ports
        else:
            for port, port_dir in self.ports.items():
                if port_dir == dir:
                    yield port

    def add_driver(self, signal, domain=None):
        if domain not in self.drivers:
            self.drivers[domain] = SignalSet()
        self.drivers[domain].add(signal)

    def iter_drivers(self):
        for domain, signals in self.drivers.items():
            for signal in signals:
                yield domain, signal

    def iter_comb(self):
        if None in self.drivers:
            yield from self.drivers[None]

    def iter_sync(self):
        for domain, signals in self.drivers.items():
            if domain is None:
                continue
            for signal in signals:
                yield domain, signal

    def iter_signals(self):
        signals = SignalSet()
        signals |= self.ports.keys()
        for domain, domain_signals in self.drivers.items():
            if domain is not None:
                cd = self.domains[domain]
                signals.add(cd.clk)
                if cd.rst is not None:
                    signals.add(cd.rst)
            signals |= domain_signals
        return signals

    def add_domains(self, *domains):
        for domain in flatten(domains):
            assert isinstance(domain, ClockDomain)
            assert domain.name not in self.domains
            self.domains[domain.name] = domain

    def iter_domains(self):
        yield from self.domains

    def add_statements(self, *stmts):
        self.statements += Statement.wrap(stmts)

    def add_subfragment(self, subfragment, name=None):
        assert isinstance(subfragment, Fragment)
        self.subfragments.append((subfragment, name))

    def find_subfragment(self, name_or_index):
        if isinstance(name_or_index, int):
            if name_or_index < len(self.subfragments):
                subfragment, name = self.subfragments[name_or_index]
                return subfragment
            raise NameError("No subfragment at index #{}".format(name_or_index))
        else:
            for subfragment, name in self.subfragments:
                if name == name_or_index:
                    return subfragment
            raise NameError("No subfragment with name '{}'".format(name_or_index))

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
        self.ports.update(subfragment.ports)
        for domain, signal in subfragment.iter_drivers():
            self.add_driver(signal, domain)
        self.statements += subfragment.statements
        self.subfragments += subfragment.subfragments

        # Remove the merged subfragment.
        found = False
        for i, (check_subfrag, check_name) in enumerate(self.subfragments): # :nobr:
            if subfragment == check_subfrag:
                del self.subfragments[i]
                found = True
                break
        assert found

    def _resolve_hierarchy_conflicts(self, hierarchy=("top",), mode="warn"):
        assert mode in ("silent", "warn", "error")

        driver_subfrags = SignalDict()
        memory_subfrags = OrderedDict()
        def add_subfrag(registry, entity, entry):
            if entity not in registry:
                registry[entity] = set()
            registry[entity].add(entry)

        # For each signal driven by this fragment and/or its subfragments, determine which
        # subfragments also drive it.
        for domain, signal in self.iter_drivers():
            add_subfrag(driver_subfrags, signal, (None, hierarchy))

        flatten_subfrags = set()
        for i, (subfrag, name) in enumerate(self.subfragments):
            if name is None:
                name = "<unnamed #{}>".format(i)
            subfrag_hierarchy = hierarchy + (name,)

            if subfrag.flatten:
                # Always flatten subfragments that explicitly request it.
                flatten_subfrags.add((subfrag, subfrag_hierarchy))

            if isinstance(subfrag, Instance):
                # For memories (which are subfragments, but semantically a part of superfragment),
                # record that this fragment is driving it.
                if subfrag.type in ("$memrd", "$memwr"):
                    memory = subfrag.parameters["MEMID"]
                    add_subfrag(memory_subfrags, memory, (None, hierarchy))

                # Never flatten instances.
                continue

            # First, recurse into subfragments and let them detect driver conflicts as well.
            subfrag_drivers, subfrag_memories = \
                subfrag._resolve_hierarchy_conflicts(subfrag_hierarchy, mode)

            # Second, classify subfragments by signals they drive and memories they use.
            for signal in subfrag_drivers:
                add_subfrag(driver_subfrags, signal, (subfrag, subfrag_hierarchy))
            for memory in subfrag_memories:
                add_subfrag(memory_subfrags, memory, (subfrag, subfrag_hierarchy))

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

        for memory, subfrags in memory_subfrags.items():
            subfrag_names = flatten_subfrags_if_needed(subfrags)
            if not subfrag_names:
                continue

            # While we're at it, show a message.
            message = ("Memory '{}' is accessed from multiple fragments: {}"
                       .format(memory.name, ", ".join(subfrag_names)))
            if mode == "error":
                raise DriverConflict(message)
            elif mode == "warn":
                message += "; hierarchy will be flattened"
                warnings.warn_explicit(message, DriverConflict, *memory.src_loc)

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
        return (SignalSet(driver_subfrags.keys()),
                set(memory_subfrags.keys()))

    def _propagate_domains_up(self, hierarchy=("top",)):
        from .xfrm import DomainRenamer

        domain_subfrags = defaultdict(lambda: set())

        # For each domain defined by a subfragment, determine which subfragments define it.
        for i, (subfrag, name) in enumerate(self.subfragments):
            # First, recurse into subfragments and let them propagate domains up as well.
            hier_name = name
            if hier_name is None:
                hier_name = "<unnamed #{}>".format(i)
            subfrag._propagate_domains_up(hierarchy + (hier_name,))

            # Second, classify subfragments by domains they define.
            for domain in subfrag.iter_domains():
                domain_subfrags[domain].add((subfrag, name, i))

        # For each domain defined by more than one subfragment, rename the domain in each
        # of the subfragments such that they no longer conflict.
        for domain, subfrags in domain_subfrags.items():
            if len(subfrags) == 1:
                continue

            names = [n for f, n, i in subfrags]
            if not all(names):
                names = sorted("<unnamed #{}>".format(i) if n is None else "'{}'".format(n)
                               for f, n, i in subfrags)
                raise DomainError("Domain '{}' is defined by subfragments {} of fragment '{}'; "
                                  "it is necessary to either rename subfragment domains "
                                  "explicitly, or give names to subfragments"
                                  .format(domain, ", ".join(names), ".".join(hierarchy)))

            if len(names) != len(set(names)):
                names = sorted("#{}".format(i) for f, n, i in subfrags)
                raise DomainError("Domain '{}' is defined by subfragments {} of fragment '{}', "
                                  "some of which have identical names; it is necessary to either "
                                  "rename subfragment domains explicitly, or give distinct names "
                                  "to subfragments"
                                  .format(domain, ", ".join(names), ".".join(hierarchy)))

            for subfrag, name, i in subfrags:
                self.subfragments[i] = \
                    (DomainRenamer({domain: "{}_{}".format(name, domain)})(subfrag), name)

        # Finally, collect the (now unique) subfragment domains, and merge them into our domains.
        for subfrag, name in self.subfragments:
            for domain in subfrag.iter_domains():
                self.add_domains(subfrag.domains[domain])

    def _propagate_domains_down(self):
        # For each domain defined in this fragment, ensure it also exists in all subfragments.
        for subfrag, name in self.subfragments:
            for domain in self.iter_domains():
                if domain in subfrag.domains:
                    assert self.domains[domain] is subfrag.domains[domain]
                else:
                    subfrag.add_domains(self.domains[domain])

            subfrag._propagate_domains_down()

    def _propagate_domains(self, ensure_sync_exists):
        self._propagate_domains_up()
        if ensure_sync_exists and not self.domains:
            self.add_domains(ClockDomain("sync"))
        self._propagate_domains_down()

    def _insert_domain_resets(self):
        from .xfrm import ResetInserter

        resets = {cd.name: cd.rst for cd in self.domains.values() if cd.rst is not None}
        return ResetInserter(resets)(self)

    def _lower_domain_signals(self):
        from .xfrm import DomainLowerer

        return DomainLowerer(self.domains)(self)

    def _propagate_ports(self, ports):
        # Collect all signals we're driving (on LHS of statements), and signals we're using
        # (on RHS of statements, or in clock domains).
        if isinstance(self, Instance):
            # Named ports contain signals for input, output and bidirectional ports. Output
            # and bidirectional ports are already added to the main port dict, however, for
            # input ports this has to be done lazily as any expression is valid there, including
            # ones with deferred resolution to signals, such as ClockSignal().
            self_driven = SignalSet()
            self_used   = SignalSet()
            for named_port_used in union((p._rhs_signals() for p in self.named_ports.values()),
                                         start=SignalSet()):
                if named_port_used not in self.ports:
                    self_used.add(named_port_used)
        else:
            self_driven = union((s._lhs_signals() for s in self.statements), start=SignalSet())
            self_used   = union((s._rhs_signals() for s in self.statements), start=SignalSet())
            for domain, _ in self.iter_sync():
                cd = self.domains[domain]
                self_used.add(cd.clk)
                if cd.rst is not None:
                    self_used.add(cd.rst)

        # Our input ports are all the signals we're using but not driving. This is an over-
        # approximation: some of these signals may be driven by our subfragments.
        ins  = self_used - self_driven
        # Our output ports are all the signals we're asked to provide that we're driving. This is
        # an underapproximation: some of these signals may be driven by subfragments.
        outs = ports & self_driven

        # Go through subfragments and refine our approximation for inputs.
        for subfrag, name in self.subfragments:
            # Refine the input port approximation: if a subfragment requires a signal as an input,
            # and we aren't driving it, it has to be our input as well.
            sub_ins, sub_outs, sub_inouts = subfrag._propagate_ports(ports=())
            ins  |= sub_ins - self_driven

        for subfrag, name in self.subfragments:
            # Always ask subfragments to provide all signals that are our inputs.
            # If the subfragment is not driving it, it will silently ignore it.
            sub_ins, sub_outs, sub_inouts = subfrag._propagate_ports(ports=ins | ports)
            # Refine the input port appropximation further: if any subfragment is driving a signal
            # that we currently think should be our input, it shouldn't actually be our input.
            ins  -= sub_outs
            # Refine the output port approximation: if a subfragment is driving a signal,
            # and we're asked to provide it, we can provide it now.
            outs |= ports & sub_outs
            # All of our subfragments' bidirectional ports are also our bidirectional ports,
            # since these are only used for pins.
            self.add_ports(sub_inouts, dir="io")

        # We've computed the precise set of input and output ports.
        self.add_ports(ins,  dir="i")
        self.add_ports(outs, dir="o")

        return (SignalSet(self.iter_ports("i")),
                SignalSet(self.iter_ports("o")),
                SignalSet(self.iter_ports("io")))

    def prepare(self, ports=(), ensure_sync_exists=True):
        from .xfrm import SampleLowerer

        fragment = SampleLowerer()(self)
        fragment._propagate_domains(ensure_sync_exists)
        fragment._resolve_hierarchy_conflicts()
        fragment = fragment._insert_domain_resets()
        fragment = fragment._lower_domain_signals()
        fragment._propagate_ports(ports)
        return fragment


class Instance(Fragment):
    def __init__(self, type, **kwargs):
        super().__init__()

        self.type = type
        self.parameters = OrderedDict()
        self.named_ports = OrderedDict()

        for kw, arg in kwargs.items():
            if kw.startswith("p_"):
                self.parameters[kw[2:]] = arg
            elif kw.startswith("i_"):
                self.named_ports[kw[2:]] = arg
                # Unlike with "o_" and "io_", "i_" ports can be assigned an arbitrary value;
                # this includes unresolved ClockSignals etc. We rely on Fragment.prepare to
                # populate fragment ports for these named ports.
            elif kw.startswith("o_"):
                self.named_ports[kw[2:]] = arg
                self.add_ports(arg, dir="o")
            elif kw.startswith("io_"):
                self.named_ports[kw[3:]] = arg
                self.add_ports(arg, dir="io")
            else:
                raise NameError("Instance argument '{}' does not start with p_, i_, o_, or io_"
                                .format(arg))
