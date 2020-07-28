from .. import *


__all__ = ["RoundRobin"]


class RoundRobin(Elaboratable):
    """Round-robin scheduler.

    For a given set of requests, the round-robin scheduler will
    grant one request. Once it grants a request, if any other
    requests are active, it grants the next active request with
    a greater number, restarting from zero once it reaches the
    highest one.

    Use :class:`EnableInserter` to control when the scheduler
    is updated.

    Parameters
    ----------
    count : int
        Number of requests.

    Attributes
    ----------
    requests : Signal(count), in
        Set of requests.
    grant : Signal(range(count)), out
        Number of the granted request. Does not change if there are no
        active requests.
    valid : Signal(), out
        Asserted if grant corresponds to an active request. Deasserted
        otherwise, i.e. if no requests are active.
    """
    def __init__(self, *, count):
        if not isinstance(count, int) or count < 0:
            raise ValueError("Count must be a non-negative integer, not {!r}"
                             .format(count))
        self.count    = count

        self.requests = Signal(count)
        self.grant    = Signal(range(count))
        self.valid    = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.grant):
            for i in range(self.count):
                with m.Case(i):
                    for pred in reversed(range(i)):
                        with m.If(self.requests[pred]):
                            m.d.sync += self.grant.eq(pred)
                    for succ in reversed(range(i + 1, self.count)):
                        with m.If(self.requests[succ]):
                            m.d.sync += self.grant.eq(succ)

        m.d.sync += self.valid.eq(self.requests.any())

        return m
