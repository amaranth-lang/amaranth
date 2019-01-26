import warnings

from ...tools import deprecated, extend
from ...hdl.ast import *
from ...hdl.mem import Memory as NativeMemory
from ...hdl.ir import Fragment, Instance
from ...lib.io import TSTriple as NativeTSTriple, Tristate as NativeTristate
from .module import Module as CompatModule


__all__ = ["TSTriple", "Instance", "Memory", "READ_FIRST", "WRITE_FIRST", "NO_CHANGE"]


class CompatTSTriple(NativeTSTriple):
    def __init__(self, bits_sign=None, min=None, max=None, reset_o=0, reset_oe=0, reset_i=0,
                 name=None):
        super().__init__(shape=bits_sign, min=min, max=max,
                         reset_o=reset_o, reset_oe=reset_oe, reset_i=reset_i,
                         name=name)


class CompatTristate(NativeTristate):
    def __init__(self, target, o, oe, i=None):
        triple = TSTriple()
        triple.o = o
        triple.oe = oe
        if i is not None:
            triple.i = i
        super().__init__(triple, target)

    @property
    @deprecated("instead of `Tristate.target`, use `Tristate.io`")
    def target(self):
        return self.io


TSTriple = CompatTSTriple
Tristate = CompatTristate


(READ_FIRST, WRITE_FIRST, NO_CHANGE) = range(3)


class _MemoryPort(CompatModule):
    def __init__(self, adr, dat_r, we=None, dat_w=None, async_read=False, re=None,
                 we_granularity=0, mode=WRITE_FIRST, clock_domain="sys"):
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


class CompatMemory(NativeMemory):
    @deprecated("instead of `get_port()`, use `read_port()` and `write_port()`")
    def get_port(self, write_capable=False, async_read=False, has_re=False, we_granularity=0,
                 mode=WRITE_FIRST, clock_domain="sys"):
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
        rdport = self.read_port(synchronous=not async_read, transparent=mode == WRITE_FIRST)
        rdport.addr.name = "{}_addr".format(self.name)
        adr = rdport.addr
        dat_r = rdport.data
        if write_capable:
            wrport = self.write_port(granularity=we_granularity)
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
