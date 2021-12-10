import warnings

from ..._utils import deprecated, extend
from ...hdl.ast import *
from ...hdl.ir import Elaboratable
from ...hdl.mem import Memory as NativeMemory
from ...hdl.ir import Fragment, Instance
from ...hdl.dsl import Module
from .module import Module as CompatModule
from .structure import Signal
from ...lib.io import Pin


__all__ = ["TSTriple", "Instance", "Memory", "READ_FIRST", "WRITE_FIRST", "NO_CHANGE"]


class TSTriple:
    def __init__(self, bits_sign=None, min=None, max=None, reset_o=0, reset_oe=0, reset_i=0,
                 name=None):
        self.o  = Signal(bits_sign, min=min, max=max, reset=reset_o,
                         name=None if name is None else name + "_o")
        self.oe = Signal(reset=reset_oe,
                         name=None if name is None else name + "_oe")
        self.i  = Signal(bits_sign, min=min, max=max, reset=reset_i,
                         name=None if name is None else name + "_i")

    def __len__(self):
        return len(self.o)

    def get_tristate(self, io):
        return Tristate(io, self.o, self.oe, self.i)


class Tristate(Elaboratable):
    def __init__(self, target, o, oe, i=None):
        self.target = target
        self.o = o
        self.oe = oe
        self.i = i if i is not None else None

    def elaborate(self, platform):
        if self.i is None:
            pin = Pin(len(self.target), dir="oe")
            pin.o = self.o
            pin.oe = self.oe
            return platform.get_tristate(pin, self.target, attrs={}, invert=None)
        else:
            pin = Pin(len(self.target), dir="io")
            pin.o = self.o
            pin.oe = self.oe
            pin.i = self.i
            return platform.get_input_output(pin, self.target, attrs={}, invert=None)

        m = Module()
        if self.i is not None:
            m.d.comb += self.i.eq(self.target)
        m.submodules += Instance("$tribuf",
            p_WIDTH=len(self.target),
            i_EN=self.oe,
            i_A=self.o,
            o_Y=self.target,
        )

        f = m.elaborate(platform)
        f.flatten = True
        return f


(READ_FIRST, WRITE_FIRST, NO_CHANGE) = range(3)


class _MemoryPort(CompatModule):
    def __init__(self, adr, dat_r, we=None, dat_w=None, async_read=False, re=None,
                 we_granularity=0, mode=WRITE_FIRST, clock_domain="sync"):
        self.adr = adr
        self.dat_r = dat_r
        self.we = we
        self.dat_w = dat_w
        self.async_read = async_read
        self.re = re
        self.we_granularity = we_granularity
        self.mode = mode
        self.clock = ClockSignal(clock_domain)


@extend(NativeMemory)
@deprecated("it is not necessary or permitted to add Memory as a special or submodule")
def elaborate(self, platform):
    return Fragment()


class CompatMemory(NativeMemory, Elaboratable):
    def __init__(self, width, depth, init=None, name=None):
        super().__init__(width=width, depth=depth, init=init, name=name)

    @deprecated("instead of `get_port()`, use `read_port()` and `write_port()`")
    def get_port(self, write_capable=False, async_read=False, has_re=False, we_granularity=0,
                 mode=WRITE_FIRST, clock_domain="sync"):
        if we_granularity >= self.width:
            warnings.warn("do not specify `we_granularity` greater than memory width, as it "
                          "is a hard error in non-compatibility mode",
                          DeprecationWarning, stacklevel=1)
            we_granularity = 0
        if we_granularity == 0:
            warnings.warn("instead of `we_granularity=0`, use `we_granularity=None` or avoid "
                          "specifying it at all, as it is a hard error in non-compatibility mode",
                          DeprecationWarning, stacklevel=1)
            we_granularity = None
        assert mode != NO_CHANGE
        rdport = self.read_port(domain="comb" if async_read else clock_domain,
                                transparent=mode == WRITE_FIRST)
        rdport.addr.name = "{}_addr".format(self.name)
        adr = rdport.addr
        dat_r = rdport.data
        if write_capable:
            wrport = self.write_port(domain=clock_domain, granularity=we_granularity)
            wrport.addr = rdport.addr
            we = wrport.en
            dat_w = wrport.data
        else:
            we = None
            dat_w = None
        if has_re:
            if mode == READ_FIRST:
                re = rdport.en
            else:
                warnings.warn("the combination of `has_re=True` and `mode=WRITE_FIRST` has "
                              "surprising behavior: keeping `re` low would merely latch "
                              "the address, while the data will change with changing memory "
                              "contents; avoid using `re` with transparent ports as it is a hard "
                              "error in non-compatibility mode",
                              DeprecationWarning, stacklevel=1)
                re = Signal()
        else:
            re = None
        mp = _MemoryPort(adr, dat_r, we, dat_w,
          async_read, re, we_granularity, mode,
          clock_domain)
        mp.submodules.rdport = rdport
        if write_capable:
            mp.submodules.wrport = wrport
        return mp


Memory = CompatMemory
