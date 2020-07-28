from .. import *


__all__ = ["RoundRobin"]


class RoundRobin(Elaboratable):
    """Round-robin scheduler.

    For a given set of requests, the round-robin scheduler will
    grant one request.

    Parameters
    ----------
    width : int
        Number of requests.

    Attributes
    ----------
    requests : Signal(width), in
        Set of requests.
    grant : Signal(range(width)), out
        Number of the granted request. Indeterminate if `valid` is deasserted.
    valid : Signal(), out
        Asserted if grant corresponds to an active request. Deasserted
        otherwise, i.e. if no requests are active.
    """
    def __init__(self, *, width):
        if not isinstance(width, int) or width < 0:
            raise ValueError("Width must be a non-negative integer, not {!r}"
                             .format(width))
        self.width    = width

        self.requests = Signal(width)
        self.grant    = Signal(range(width))
        self.valid    = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.grant):
            for i in range(self.width):
                with m.Case(i):
                    for pred in reversed(range(i)):
                        with m.If(self.requests[pred]):
                            m.d.sync += self.grant.eq(pred)
                    for succ in reversed(range(i + 1, self.width)):
                        with m.If(self.requests[succ]):
                            m.d.sync += self.grant.eq(succ)

        m.d.sync += self.valid.eq(self.requests.any())

        return m
