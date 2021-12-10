import warnings

from ..fhdl.structure import Signal, If, Case
from ..fhdl.module import CompatModule


__all__ = ["RoundRobin", "SP_WITHDRAW", "SP_CE"]

(SP_WITHDRAW, SP_CE) = range(2)

class CompatRoundRobin(CompatModule):
    def __init__(self, n, switch_policy=SP_WITHDRAW):
        self.request = Signal(n)
        self.grant = Signal(max=max(2, n))
        self.switch_policy = switch_policy
        if self.switch_policy == SP_CE:
            warnings.warn("instead of `migen.genlib.roundrobin.RoundRobin`, "
                          "use `amaranth.lib.scheduler.RoundRobin`; note that RoundRobin does not "
                          "require a policy anymore but to get the same behavior as SP_CE you"
                          "should use an EnableInserter",
                          DeprecationWarning, stacklevel=1)
            self.ce = Signal()
        else:
            warnings.warn("instead of `migen.genlib.roundrobin.RoundRobin`, "
                          "use `amaranth.lib.scheduler.RoundRobin`; note that RoundRobin does not "
                          "require a policy anymore",
                          DeprecationWarning, stacklevel=1)

        ###

        if n > 1:
            cases = {}
            for i in range(n):
                switch = []
                for j in reversed(range(i+1, i+n)):
                    t = j % n
                    switch = [
                        If(self.request[t],
                            self.grant.eq(t)
                        ).Else(
                            *switch
                        )
                    ]
                if self.switch_policy == SP_WITHDRAW:
                    case = [If(~self.request[i], *switch)]
                else:
                    case = switch
                cases[i] = case
            statement = Case(self.grant, cases)
            if self.switch_policy == SP_CE:
                statement = If(self.ce, statement)
            self.sync += statement
        else:
            self.comb += self.grant.eq(0)



RoundRobin = CompatRoundRobin
