from .. import *


__all__ = ["MultiReg", "ResetSynchronizer"]


class MultiReg:
    def __init__(self, i, o, odomain="sync", n=2, reset=0):
        self.i = i
        self.o = o
        self.odomain = odomain

        self._regs = [Signal(self.i.shape(), name="cdc{}".format(i),
                             reset=reset, reset_less=True, attrs={"no_retiming": True})
                      for i in range(n)]

    def elaborate(self, platform):
        if hasattr(platform, "get_multi_reg"):
            return platform.get_multi_reg(self)

        m = Module()
        for i, o in zip((self.i, *self._regs), self._regs):
            m.d[self.odomain] += o.eq(i)
        m.d.comb += self.o.eq(self._regs[-1])
        return m


class ResetSynchronizer:
    def __init__(self, arst, domain="sync", n=2):
        self.arst = arst
        self.domain = domain

        self._regs = [Signal(name="arst{}".format(i), reset=1,
                             attrs={"no_retiming": True})
                      for i in range(n)]

    def elaborate(self, platform):
        if hasattr(platform, "get_reset_sync"):
            return platform.get_reset_sync(self)

        m = Module()
        m.domains += ClockDomain("_reset_sync", async_reset=True)
        for i, o in zip((0, *self._regs), self._regs):
            m.d._reset_sync += o.eq(i)
        m.d.comb += [
            ClockSignal("_reset_sync").eq(ClockSignal(self.domain)),
            ResetSignal("_reset_sync").eq(self.arst),
            ResetSignal(self.domain).eq(self._regs[-1])
        ]
        return m
