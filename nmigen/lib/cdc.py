from .. import *


__all__ = ["MultiReg"]


class MultiReg:
    def __init__(self, i, o, odomain="sync", n=2, reset=0):
        self.i = i
        self.o = o
        self.odomain = odomain

        self._regs = [Signal(self.i.shape(), name="cdc{}".format(i),
                             reset=reset, reset_less=True, attrs={"no_retiming": True})
                      for i in range(n)]

    def get_fragment(self, platform):
        if hasattr(platform, "get_multi_reg"):
            return platform.get_multi_reg(self)

        m = Module()
        for i, o in zip((self.i, *self._regs), self._regs):
            m.d[self.odomain] += o.eq(i)
        m.d.comb += self.o.eq(self._regs[-1])
        return m.lower(platform)
