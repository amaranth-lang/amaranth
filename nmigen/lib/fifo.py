"""First-in first-out queues."""

from .. import *
from ..formal import *


__all__ = ["FIFOInterface", "SyncFIFO", "SyncFIFOBuffered"]


class FIFOInterface:
    _doc_template = """
    {description}

    Parameters
    ----------
    width : int
        Bit width of data entries.
    depth : int
        Depth of the queue.
    {parameters}

    Attributes
    ----------
    din : in, width
        Input data.
    writable : out
        Asserted if there is space in the queue, i.e. ``we`` can be asserted to write a new entry.
    we : in
        Write strobe. Latches ``din`` into the queue. Does nothing if ``writable`` is not asserted.
    {w_attributes}
    dout : out, width
        Output data. {dout_valid}
    readable : out
        Asserted if there is an entry in the queue, i.e. ``re`` can be asserted to read this entry.
    re : in
        Read strobe. Makes the next entry (if any) available on ``dout`` at the next cycle.
        Does nothing if ``readable`` is not asserted.
    {r_attributes}
    """

    __doc__ = _doc_template.format(description="""
    Data written to the input interface (``din``, ``we``, ``writable``) is buffered and can be
    read at the output interface (``dout``, ``re``, ``readable`). The data entry written first
    to the input also appears first on the output.
    """,
    parameters="",
    dout_valid="The conditions in which ``dout`` is valid depends on the type of the queue.",
    w_attributes="",
    r_attributes="")

    def __init__(self, width, depth):
        self.width = width
        self.depth = depth

        self.din      = Signal(width, reset_less=True)
        self.writable = Signal() # not full
        self.we       = Signal()

        self.dout     = Signal(width, reset_less=True)
        self.readable = Signal() # not empty
        self.re       = Signal()

    def read(self):
        """Read method for simulation."""
        assert (yield self.readable)
        yield self.re.eq(1)
        yield
        value = (yield self.dout)
        yield self.re.eq(0)
        return value

    def write(self, data):
        """Write method for simulation."""
        assert (yield self.writable)
        yield self.din.eq(data)
        yield self.we.eq(1)
        yield
        yield self.we.eq(0)


def _incr(signal, modulo):
    if modulo == 2 ** len(signal):
        return signal + 1
    else:
        return Mux(signal == modulo - 1, 0, signal + 1)


def _decr(signal, modulo):
    if modulo == 2 ** len(signal):
        return signal - 1
    else:
        return Mux(signal == 0, modulo - 1, signal - 1)


class SyncFIFO(FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Synchronous first in, first out queue.

    Read and write interfaces are accessed from the same clock domain. If different clock domains
    are needed, use :class:`AsyncFIFO`.
    """.strip(),
    parameters="""
    fwft : bool
        First-word fallthrough. If set, when the queue is empty and an entry is written into it,
        that entry becomes available on the output on the same clock cycle. Otherwise, it is
        necessary to assert ``re`` for ``dout`` to become valid.
    """.strip(),
    dout_valid="""
    For FWFT queues, valid if ``readable`` is asserted. For non-FWFT queues, valid on the next
    cycle after ``readable`` and ``re`` have been asserted.
    """.strip(),
    r_attributes="""
    level : out
        Number of unread entries.
    """.strip(),
    w_attributes="""
    replace : in
        If asserted at the same time as ``we``, replaces the last entry written into the queue
        with ``din``. For FWFT queues, if ``level`` is 1, this replaces the value at ``dout``
        as well. Does nothing if the queue is empty.
    """.strip())

    def __init__(self, width, depth, fwft=True):
        super().__init__(width, depth)

        self.fwft    = fwft

        self.level   = Signal(max=depth + 1)
        self.replace = Signal()

    def get_fragment(self, platform):
        m = Module()
        m.d.comb += [
            self.writable.eq(self.level != self.depth),
            self.readable.eq(self.level != 0)
        ]

        do_read  = self.readable & self.re
        do_write = self.writable & self.we & ~self.replace

        storage = Memory(self.width, self.depth)
        wrport  = m.submodules.wrport = storage.write_port()
        rdport  = m.submodules.rdport = storage.read_port(
            synchronous=not self.fwft, transparent=self.fwft)
        produce = Signal(max=self.depth)
        consume = Signal(max=self.depth)

        m.d.comb += [
            wrport.addr.eq(produce),
            wrport.data.eq(self.din),
            wrport.en.eq(self.we & (self.writable | self.replace))
        ]
        with m.If(self.replace):
            m.d.comb += wrport.addr.eq(_decr(produce, self.depth))
        with m.If(do_write):
            m.d.sync += produce.eq(_incr(produce, self.depth))

        m.d.comb += [
            rdport.addr.eq(consume),
            self.dout.eq(rdport.data),
        ]
        if not self.fwft:
            m.d.comb += rdport.en.eq(self.re)
        with m.If(do_read):
            m.d.sync += consume.eq(_incr(consume, self.depth))

        with m.If(do_write & ~do_read):
            m.d.sync += self.level.eq(self.level + 1)
        with m.If(do_read & ~do_write):
            m.d.sync += self.level.eq(self.level - 1)

        if platform == "formal":
            # TODO: move this logic to SymbiYosys
            initstate = Signal()
            m.submodules += Instance("$initstate", o_Y=initstate)
            with m.If(initstate):
                m.d.comb += [
                    Assume(produce < self.depth),
                    Assume(consume < self.depth),
                ]
                with m.If(produce == consume):
                    m.d.comb += Assume((self.level == 0) | (self.level == self.depth))
                with m.If(produce > consume):
                    m.d.comb += Assume(self.level == (produce - consume))
                with m.If(produce < consume):
                    m.d.comb += Assume(self.level == (self.depth + produce - consume))
            with m.Else():
                m.d.comb += [
                    Assert(produce < self.depth),
                    Assert(consume < self.depth),
                ]
                with m.If(produce == consume):
                    m.d.comb += Assert((self.level == 0) | (self.level == self.depth))
                with m.If(produce > consume):
                    m.d.comb += Assert(self.level == (produce - consume))
                with m.If(produce < consume):
                    m.d.comb += Assert(self.level == (self.depth + produce - consume))

        return m.lower(platform)


class SyncFIFOBuffered(FIFOInterface):
    """
    Buffered synchronous first in, first out queue.

    This queue's interface is identical to :class:`SyncFIFO` configured as ``fwft=True``, but it
    does not use asynchronous memory reads, which are incompatible with FPGA block RAMs.

    In exchange, the latency between an entry being written to an empty queue and that entry
    becoming available on the output is increased to one cycle.
    """
    def __init__(self, width, depth):
        super().__init__(width, depth)

        self.fwft  = True

        self.level = Signal(max=depth + 1)

    def get_fragment(self, platform):
        m = Module()

        # Effectively, this queue treats the output register of the non-FWFT inner queue as
        # an additional storage element.
        m.submodules.unbuffered = fifo = SyncFIFO(self.width, self.depth - 1, fwft=False)

        m.d.comb += [
            fifo.din.eq(self.din),
            fifo.we.eq(self.we),
            self.writable.eq(fifo.writable),
            fifo.replace.eq(0),
        ]

        m.d.comb += [
            self.dout.eq(fifo.dout),
            fifo.re.eq(fifo.readable & (~self.readable | self.re)),
        ]
        with m.If(fifo.re):
            m.d.sync += self.readable.eq(1)
        with m.Elif(self.re):
            m.d.sync += self.readable.eq(0)

        m.d.comb += self.level.eq(fifo.level + self.readable)

        return m.lower(platform)
