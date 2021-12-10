import warnings

from ..._utils import deprecated
from ...lib.cdc import FFSynchronizer as NativeFFSynchronizer
from ...lib.cdc import PulseSynchronizer as NativePulseSynchronizer
from ...hdl.ast import *
from ..fhdl.module import CompatModule
from ..fhdl.structure import If


__all__ = ["MultiReg", "PulseSynchronizer", "GrayCounter", "GrayDecoder"]


class MultiReg(NativeFFSynchronizer):
    def __init__(self, i, o, odomain="sync", n=2, reset=0):
        old_opts = []
        new_opts = []
        if odomain != "sync":
            old_opts.append(", odomain={!r}".format(odomain))
            new_opts.append(", o_domain={!r}".format(odomain))
        if n != 2:
            old_opts.append(", n={!r}".format(n))
            new_opts.append(", stages={!r}".format(n))
        warnings.warn("instead of `MultiReg(...{})`, use `FFSynchronizer(...{})`"
                      .format("".join(old_opts), "".join(new_opts)),
                      DeprecationWarning, stacklevel=2)
        super().__init__(i, o, o_domain=odomain, stages=n, reset=reset)
        self.odomain = odomain


@deprecated("instead of `migen.genlib.cdc.PulseSynchronizer`, use `amaranth.lib.cdc.PulseSynchronizer`")
class PulseSynchronizer(NativePulseSynchronizer):
    def __init__(self, idomain, odomain):
        super().__init__(i_domain=idomain, o_domain=odomain)


@deprecated("instead of `migen.genlib.cdc.GrayCounter`, use `amaranth.lib.coding.GrayEncoder`")
class GrayCounter(CompatModule):
    def __init__(self, width):
        self.ce = Signal()
        self.q = Signal(width)
        self.q_next = Signal(width)
        self.q_binary = Signal(width)
        self.q_next_binary = Signal(width)

        ###

        self.comb += [
            If(self.ce,
                self.q_next_binary.eq(self.q_binary + 1)
            ).Else(
                self.q_next_binary.eq(self.q_binary)
            ),
            self.q_next.eq(self.q_next_binary ^ self.q_next_binary[1:])
        ]
        self.sync += [
            self.q_binary.eq(self.q_next_binary),
            self.q.eq(self.q_next)
        ]


@deprecated("instead of `migen.genlib.cdc.GrayDecoder`, use `amaranth.lib.coding.GrayDecoder`")
class GrayDecoder(CompatModule):
    def __init__(self, width):
        self.i = Signal(width)
        self.o = Signal(width, reset_less=True)

        # # #

        o_comb = Signal(width)
        self.comb += o_comb[-1].eq(self.i[-1])
        for i in reversed(range(width-1)):
            self.comb += o_comb[i].eq(o_comb[i+1] ^ self.i[i])
        self.sync += self.o.eq(o_comb)
