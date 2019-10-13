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
