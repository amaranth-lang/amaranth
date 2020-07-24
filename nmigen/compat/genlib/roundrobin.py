from ..._utils import deprecated
from ...lib.roundrobin import RoundRobin as NativeRoundRobin


__all__ = ["RoundRobin", "SP_WITHDRAW", "SP_CE"]

(SP_WITHDRAW, SP_CE) = range(2)

@deprecated("instead of `migen.genlib.roundrobin.RoundRobin`, "
            "use `nmigen.lib.roundrobin.RoundRobin`; note that RoundRobin does not "
            "require a policy anymore, and that the `ce` attribute has been renamed"
            "to `en`")
class CompatRoundRobin(NativeRoundRobin):
    def __init__(self, n, switching_policy=SP_WITHDRAW):
        super().__init__(n)

        if switching_policy == SP_CE:
        	self.ce = Signal()
        	self.comb += self.en.eq(self.ce)


RoundRobin = CompatRoundRobin
