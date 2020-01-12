from ..._utils import deprecated, extend
from ...lib.fifo import (FIFOInterface as NativeFIFOInterface,
  SyncFIFO as NativeSyncFIFO, SyncFIFOBuffered as NativeSyncFIFOBuffered,
  AsyncFIFO as NativeAsyncFIFO, AsyncFIFOBuffered as NativeAsyncFIFOBuffered)


__all__ = ["_FIFOInterface", "SyncFIFO", "SyncFIFOBuffered", "AsyncFIFO", "AsyncFIFOBuffered"]


class CompatFIFOInterface(NativeFIFOInterface):
    @deprecated("attribute `fwft` must be provided to FIFOInterface constructor")
    def __init__(self, width, depth):
        super().__init__(width=width, depth=depth, fwft=False)
        del self.fwft


@extend(NativeFIFOInterface)
@property
@deprecated("instead of `fifo.din`, use `fifo.w_data`")
def din(self):
    return self.w_data


@extend(NativeFIFOInterface)
@NativeFIFOInterface.din.setter
@deprecated("instead of `fifo.din = x`, use `fifo.w_data = x`")
def din(self, w_data):
    self.w_data = w_data


@extend(NativeFIFOInterface)
@property
@deprecated("instead of `fifo.writable`, use `fifo.w_rdy`")
def writable(self):
    return self.w_rdy


@extend(NativeFIFOInterface)
@NativeFIFOInterface.writable.setter
@deprecated("instead of `fifo.writable = x`, use `fifo.w_rdy = x`")
def writable(self, w_rdy):
    self.w_rdy = w_rdy


@extend(NativeFIFOInterface)
@property
@deprecated("instead of `fifo.we`, use `fifo.w_en`")
def we(self):
    return self.w_en


@extend(NativeFIFOInterface)
@NativeFIFOInterface.we.setter
@deprecated("instead of `fifo.we = x`, use `fifo.w_en = x`")
def we(self, w_en):
    self.w_en = w_en


@extend(NativeFIFOInterface)
@property
@deprecated("instead of `fifo.dout`, use `fifo.r_data`")
def dout(self):
    return self.r_data


@extend(NativeFIFOInterface)
@NativeFIFOInterface.dout.setter
@deprecated("instead of `fifo.dout = x`, use `fifo.r_data = x`")
def dout(self, r_data):
    self.r_data = r_data


@extend(NativeFIFOInterface)
@property
@deprecated("instead of `fifo.readable`, use `fifo.r_rdy`")
def readable(self):
    return self.r_rdy


@extend(NativeFIFOInterface)
@NativeFIFOInterface.readable.setter
@deprecated("instead of `fifo.readable = x`, use `fifo.r_rdy = x`")
def readable(self, r_rdy):
    self.r_rdy = r_rdy


@extend(NativeFIFOInterface)
@property
@deprecated("instead of `fifo.re`, use `fifo.r_en`")
def re(self):
    return self.r_en


@extend(NativeFIFOInterface)
@NativeFIFOInterface.re.setter
@deprecated("instead of `fifo.re = x`, use `fifo.r_en = x`")
def re(self, r_en):
    self.r_en = r_en


@extend(NativeFIFOInterface)
def read(self):
    """Read method for simulation."""
    assert (yield self.r_rdy)
    value = (yield self.r_data)
    yield self.r_en.eq(1)
    yield
    yield self.r_en.eq(0)
    yield
    return value

@extend(NativeFIFOInterface)
def write(self, data):
    """Write method for simulation."""
    assert (yield self.w_rdy)
    yield self.w_data.eq(data)
    yield self.w_en.eq(1)
    yield
    yield self.w_en.eq(0)
    yield


class CompatSyncFIFO(NativeSyncFIFO):
    def __init__(self, width, depth, fwft=True):
        super().__init__(width=width, depth=depth, fwft=fwft)


class CompatSyncFIFOBuffered(NativeSyncFIFOBuffered):
    def __init__(self, width, depth):
        super().__init__(width=width, depth=depth)


class CompatAsyncFIFO(NativeAsyncFIFO):
    def __init__(self, width, depth):
        super().__init__(width=width, depth=depth)


class CompatAsyncFIFOBuffered(NativeAsyncFIFOBuffered):
    def __init__(self, width, depth):
        super().__init__(width=width, depth=depth)


_FIFOInterface = CompatFIFOInterface
SyncFIFO = CompatSyncFIFO
SyncFIFOBuffered = CompatSyncFIFOBuffered
AsyncFIFO = CompatAsyncFIFO
AsyncFIFOBuffered = CompatAsyncFIFOBuffered
