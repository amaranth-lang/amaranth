from ...tools import deprecated, extend
from ...lib.fifo import FIFOInterface as NativeFIFOInterface, \
  SyncFIFO, SyncFIFOBuffered, AsyncFIFO, AsyncFIFOBuffered


__all__ = ["_FIFOInterface", "SyncFIFO", "SyncFIFOBuffered", "AsyncFIFO", "AsyncFIFOBuffered"]


class CompatFIFOInterface(NativeFIFOInterface):
    @deprecated("attribute `fwft` must be provided to FIFOInterface constructor")
    def __init__(self, width, depth):
        super().__init__(width, depth, fwft=False)
        del self.fwft


_FIFOInterface = CompatFIFOInterface


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
