import warnings
from collections import defaultdict, OrderedDict

from ..tools import *
from .ast import *
from .cd import *


__all__ = ["Fragment", "DriverConflict"]


class DriverConflict(UserWarning):
    pass


class Fragment:
    def __init__(self):
        self.ports = SignalDict()
        self.drivers = OrderedDict()
        self.statements = []
        self.domains = OrderedDict()
        self.subfragments = []

    def add_ports(self, *ports, kind):
        assert kind in ("i", "o", "io")
        for port in flatten(ports):
            self.ports[port] = kind

    def iter_ports(self):
        yield from self.ports.keys()

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

    def _resolve_driver_conflicts(self, hierarchy=("top",), mode="warn"):
        assert mode in ("silent", "warn", "error")

        driver_subfrags = SignalDict()

        # For each signal driven by this fragment and/or its subfragments, determine which
        # subfragments also drive it.
        for domain, signal in self.iter_drivers():
            if signal not in driver_subfrags:
                driver_subfrags[signal] = set()
            driver_subfrags[signal].add((None, hierarchy))

        for i, (subfrag, name) in enumerate(self.subfragments):
            # First, recurse into subfragments and let them detect driver conflicts as well.
            if name is None:
                name = "<unnamed #{}>".format(i)
            subfrag_hierarchy = hierarchy + (name,)
            subfrag_drivers = subfrag._resolve_driver_conflicts(subfrag_hierarchy, mode)

            # Second, classify subfragments by domains they define.
            for signal in subfrag_drivers:
                if signal not in driver_subfrags:
                    driver_subfrags[signal] = set()
                driver_subfrags[signal].add((subfrag, subfrag_hierarchy))

        # Find out the set of subfragments that needs to be flattened into this fragment
        # to resolve driver-driver conflicts.
        flatten_subfrags = set()
        for signal, subfrags in driver_subfrags.items():
            if len(subfrags) > 1:
                flatten_subfrags.update((f, h) for f, h in subfrags if f is not None)

                # While we're at it, show a message.
                subfrag_names = ", ".join(sorted(".".join(h) for f, h in subfrags))
                message = ("Signal '{}' is driven from multiple fragments: {}"
                           .format(signal, subfrag_names))
                if mode == "error":
                    raise DriverConflict(message)
                elif mode == "warn":
                    message += "; hierarchy will be flattened"
                    warnings.warn_explicit(message, DriverConflict, *signal.src_loc)

        for subfrag, subfrag_hierarchy in sorted(flatten_subfrags, key=lambda x: x[1]):
            # Merge subfragment's everything except clock domains into this fragment.
            # Flattening is done after clock domain propagation, so we can assume the domains
            # are already the same in every involved fragment in the first place.
            self.ports.update(subfrag.ports)
            for domain, signal in subfrag.iter_drivers():
                self.add_driver(signal, domain)
            self.statements += subfrag.statements
            self.subfragments += subfrag.subfragments

            # Remove the merged subfragment.
            for i, (check_subfrag, check_name) in enumerate(self.subfragments): # :nobr:
                if subfrag == check_subfrag:
                    del self.subfragments[i]
                    break

        # If we flattened anything, we might be in a situation where we have a driver conflict
        # again, e.g. if we had a tree of fragments like A --- B --- C where only fragments
        # A and C were driving a signal S. In that case, since B is not driving S itself,
        # processing B will not result in any flattening, but since B is transitively driving S,
        # processing A will flatten B into it. Afterwards, we have a tree like AB --- C, which
        # has another conflict.
        if any(flatten_subfrags):
            # Try flattening again.
            return self._resolve_driver_conflicts(hierarchy, mode)

        # Nothing was flattened, we're done!
        return SignalSet(driver_subfrags.keys())

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
        self_driven = union(s._lhs_signals() for s in self.statements) or SignalSet()
        self_used   = union(s._rhs_signals() for s in self.statements) or SignalSet()
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

        # Go through subfragments and refine our approximation for ports.
        for subfrag, name in self.subfragments:
            # Always ask subfragments to provide all signals we're using and signals we're asked
            # to provide. If the subfragment is not driving it, it will silently ignore it.
            sub_ins, sub_outs = subfrag._propagate_ports(ports=self_used | ports)
            # Refine the input port approximation: if a subfragment is driving a signal,
            # it is definitely not our input. But, if a subfragment requires a signal as an input,
            # and we aren't driving it, it has to be our input as well.
            ins  -= sub_outs
            ins  |= sub_ins - self_driven
            # Refine the output port approximation: if a subfragment is driving a signal,
            # and we're asked to provide it, we can provide it now.
            outs |= ports & sub_outs

        # We've computed the precise set of input and output ports.
        self.add_ports(ins,  kind="i")
        self.add_ports(outs, kind="o")

        return ins, outs

    def prepare(self, ports=(), ensure_sync_exists=True):
        from .xfrm import FragmentTransformer

        fragment = FragmentTransformer()(self)
        fragment._propagate_domains(ensure_sync_exists)
        fragment._resolve_driver_conflicts()
        fragment = fragment._insert_domain_resets()
        fragment = fragment._lower_domain_signals()
        fragment._propagate_ports(ports)
        return fragment
