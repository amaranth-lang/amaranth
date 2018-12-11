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

    def drive(self, signal, cd_name=None):
        if cd_name not in self.drivers:
            self.drivers[cd_name] = ValueSet()
        self.drivers[cd_name].add(signal)

    def iter_domains(self):
        yield from self.drivers.items()

    def iter_drivers(self):
        for cd_name, signals in self.drivers.items():
            for signal in signals:
                yield cd_name, signal

    def iter_comb(self):
        yield from self.drivers[None]

    def iter_sync(self):
        for cd_name, signals in self.drivers.items():
            if cd_name is None:
                continue
            for signal in signals:
                yield cd_name, signal

    def add_statements(self, *stmts):
        self.statements += Statement.wrap(stmts)

    def add_subfragment(self, subfragment, name=None):
        assert isinstance(subfragment, Fragment)
        self.subfragments.append((subfragment, name))

    def prepare(self, ports, clock_domains):
        from .xfrm import ResetInserter

        resets = {cd.name: cd.rst for cd in clock_domains.values() if cd.rst is not None}
        frag   = ResetInserter(resets)(self)

        self_driven = union(s._lhs_signals() for s in self.statements)
        self_used   = union(s._rhs_signals() for s in self.statements)

        ins  = self_used - self_driven
        outs = ports & self_driven

        for n, (subfrag, name) in enumerate(frag.subfragments):
            subfrag, sub_ins, sub_outs = subfrag.prepare(ports=self_used | ports,
                                                         clock_domains=clock_domains)
            frag.subfragments[n] = (subfrag, name)
            ins  |= sub_ins - self_driven
            outs |= ports & sub_outs

        frag.add_ports(ins, outs)

        return frag, ins, outs
