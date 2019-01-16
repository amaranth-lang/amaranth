from .tools import *
from ..hdl.ast import *
from ..hdl.dsl import *
from ..back.pysim import *
from ..lib.fifo import *


class FIFOSmokeTestCase(FHDLTestCase):
    def assertSyncFIFOWorks(self, fifo):
        with Simulator(fifo) as sim:
            sim.add_clock(1e-6)
            def process():
                yield from fifo.write(1)
                yield from fifo.write(2)
                yield
                self.assertEqual((yield from fifo.read()), 1)
                self.assertEqual((yield from fifo.read()), 2)
            sim.add_sync_process(process)
            sim.run()

    def test_sync_fwft(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=True)
        self.assertSyncFIFOWorks(SyncFIFO(width=8, depth=4))

    def test_sync_not_fwft(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=False)
        self.assertSyncFIFOWorks(SyncFIFO(width=8, depth=4))

    def test_sync_buffered(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=True)
        self.assertSyncFIFOWorks(SyncFIFOBuffered(width=8, depth=4))
