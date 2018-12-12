from ..fhdl import *


__all__ = ["MultiReg"]


class MultiReg(Module):
    def __init__(self, i, o, odomain="sys", n=2, reset=0):
        self.i = i
        self.o = o
        self.odomain = odomain

        self._regs = [Signal(self.i.bits_sign(), name="cdc{}".format(i),
                             reset=reset, reset_less=True)#, attrs=("no_retiming",))
                      for i in range(n)]

    def get_fragment(self, platform):
        f = Module()
        for i, o in zip((self.i, *self._regs), self._regs):
            f.sync[self.odomain] += o.eq(i)
        f.comb += self.o.eq(self._regs[-1])
        return f.lower(platform)
