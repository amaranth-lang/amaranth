from ...tools import deprecated
from ...lib.fifo import FIFOInterface as NativeFIFOInterface, \
  SyncFIFO, SyncFIFOBuffered, AsyncFIFO, AsyncFIFOBuffered


__all__ = ["_FIFOInterface", "SyncFIFO", "SyncFIFOBuffered", "AsyncFIFO", "AsyncFIFOBuffered"]


class CompatFIFOInterface(NativeFIFOInterface):
    @deprecated("attribute `fwft` must be provided to FIFOInterface constructor")
    def __init__(self, width, depth):
        super().__init__(width, depth, fwft=False)
        del self.fwft


_FIFOInterface = CompatFIFOInterface
