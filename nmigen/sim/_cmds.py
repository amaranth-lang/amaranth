from ..hdl.cd import *


__all__ = ["Settle", "Delay", "Tick", "Passive", "Active"]


class Command:
    pass


class Settle(Command):
    def __repr__(self):
        return "(settle)"


class Delay(Command):
    def __init__(self, interval=None):
        self.interval = None if interval is None else float(interval)

    def __repr__(self):
        if self.interval is None:
            return "(delay ε)"
        else:
            return "(delay {:.3}us)".format(self.interval * 1e6)


class Tick(Command):
    def __init__(self, domain="sync"):
        if not isinstance(domain, (str, ClockDomain)):
            raise TypeError("Domain must be a string or a ClockDomain instance, not {!r}"
                            .format(domain))
        assert domain != "comb"
        self.domain = domain

    def __repr__(self):
        return "(tick {})".format(self.domain)


class Passive(Command):
    def __repr__(self):
        return "(passive)"


class Active(Command):
    def __repr__(self):
        return "(active)"
