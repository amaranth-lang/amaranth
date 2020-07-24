from ..._utils import deprecated
from ..fhdl.module import CompatModule


__all__ = ["RoundRobin", "SP_WITHDRAW", "SP_CE"]

(SP_WITHDRAW, SP_CE) = range(2)

@deprecated("instead of `migen.genlib.roundrobin.RoundRobin`, "
            "use `nmigen.lib.roundrobin.RoundRobin`; note that RoundRobin does not "
            "require a policy anymore, and that the `ce` attribute has been renamed"
            "to `en`")
class CompatRoundRobin(CompatModule):
    def __init__(self, n, switch_policy=SP_WITHDRAW):
        self.request = Signal(n)
        self.grant = Signal(max=max(2, n))
        self.switch_policy = switch_policy
        if self.switch_policy == SP_CE:
            self.ce = Signal()

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
