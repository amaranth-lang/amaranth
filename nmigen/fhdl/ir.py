from collections import defaultdict, OrderedDict

from ..tools import *
from .ast import *


__all__ = ["Fragment"]


class Fragment:
    def __init__(self):
        self.ports = ValueSet()
        self.drivers = OrderedDict()
        self.statements = []
        self.subfragments = []

    def add_ports(self, *ports):
        self.ports.update(flatten(ports))

    def iter_ports(self):
        yield from self.ports

    def drive(self, signal, domain=None):
        if domain not in self.drivers:
            self.drivers[domain] = ValueSet()
        self.drivers[domain].add(signal)

    def iter_drivers(self):
        for domain, signals in self.drivers.items():
            for signal in signals:
                yield domain, signal

    def iter_comb(self):
        yield from self.drivers[None]

    def iter_sync(self):
        for domain, signals in self.drivers.items():
            if domain is None:
                continue
            for signal in signals:
                yield domain, signal

    def add_statements(self, *stmts):
        self.statements += Statement.wrap(stmts)

    def add_subfragment(self, subfragment, name=None):
        assert isinstance(subfragment, Fragment)
        self.subfragments.append((subfragment, name))

    def _propagate_ports(self, ports, clock_domains={}):
        # Collect all signals we're driving (on LHS of statements), and signals we're using
        # (on RHS of statements, or in clock domains).
        self_driven = union(s._lhs_signals() for s in self.statements)
        self_used   = union(s._rhs_signals() for s in self.statements)
        for domain, _ in self.iter_sync():
            cd = clock_domains[domain]
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
            sub_ins, sub_outs = subfrag._propagate_ports(ports=self_used | ports,
                                                         clock_domains=clock_domains)
            # Refine the input port approximation: if a subfragment is driving a signal,
            # it is definitely not our input.
            ins  -= sub_outs
            # Refine the output port approximation: if a subfragment is driving a signal,
            # and we're asked to provide it, we can provide it now.
            outs |= ports & sub_outs

        # We've computed the precise set of input and output ports.
        self.add_ports(ins, outs)

        return ins, outs
