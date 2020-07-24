from .. import *


__all__ = ["RoundRobin"]


class RoundRobin(Elaboratable):
    def __init__(self, n):
        self.requests = Signal(n)
        self.grant = Signal(range(n))
        self.en = Signal(reset=1)

    def elaborate(self, platform):
        m = Module()

        n = self.requests.width

        with m.Switch(self.grant):
            for i in range(n):
                with m.Case(i):
                    for pred in reversed(range(i)):
                        with m.If(self.requests[pred]):
                            m.d.sync += self.grant.eq(pred)
                    for succ in reversed(range(i + 1, n)):
                        with m.If(self.requests[succ]):
                            m.d.sync += self.grant.eq(succ)

        return EnableInserter(self.en)(m)
