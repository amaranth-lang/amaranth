"""First-in first-out queues."""

from .. import *
from ..formal import *
from ..tools import log2_int
from .coding import GrayEncoder


__all__ = ["FIFOInterface", "SyncFIFO", "SyncFIFOBuffered", "AsyncFIFO", "AsyncFIFOBuffered"]


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
    {attributes}
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
    attributes="""
    fwft : bool
        First-word fallthrough. If set, when ``readable`` rises, the first entry is already
        available, i.e. ``dout`` is valid. Otherwise, after ``readable`` rises, it is necessary
        to strobe ``re`` for ``dout`` to become valid.
    """.strip(),
    w_attributes="",
    r_attributes="")

    def __init__(self, width, depth, fwft):
        self.width = width
        self.depth = depth
        self.fwft  = fwft

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
    attributes="",
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
        super().__init__(width, depth, fwft)

        self.level   = Signal(max=depth + 1)
        self.replace = Signal()

    def elaborate(self, platform):
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

        return m


class SyncFIFOBuffered(FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Buffered synchronous first in, first out queue.

    This queue's interface is identical to :class:`SyncFIFO` configured as ``fwft=True``, but it
    does not use asynchronous memory reads, which are incompatible with FPGA block RAMs.

    In exchange, the latency between an entry being written to an empty queue and that entry
    becoming available on the output is increased to one cycle.
    """.strip(),
    parameters="""
    fwft : bool
        Always set.
    """.strip(),
    attributes="",
    dout_valid="Valid if ``readable`` is asserted.",
    r_attributes="""
    level : out
        Number of unread entries.
    """.strip(),
    w_attributes="")

    def __init__(self, width, depth):
        super().__init__(width, depth, fwft=True)

        self.level = Signal(max=depth + 1)

    def elaborate(self, platform):
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

        return m


class AsyncFIFO(FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Asynchronous first in, first out queue.

    Read and write interfaces are accessed from different clock domains, called ``read``
    and ``write``; use :class:`DomainsRenamer` to rename them as appropriate for the design.
    """.strip(),
    parameters="""
    fwft : bool
        Always set.
    """.strip(),
    attributes="",
    dout_valid="Valid if ``readable`` is asserted.",
    r_attributes="",
    w_attributes="")

    def __init__(self, width, depth):
        super().__init__(width, depth, fwft=True)

        try:
            self._ctr_bits = log2_int(depth, need_pow2=True) + 1
        except ValueError as e:
            raise ValueError("AsyncFIFO only supports power-of-2 depths") from e

    def elaborate(self, platform):
        # The design of this queue is the "style #2" from Clifford E. Cummings' paper "Simulation
        # and Synthesis Techniques for Asynchronous FIFO Design":
        # http://www.sunburst-design.com/papers/CummingsSNUG2002SJ_FIFO1.pdf

        m = Module()

        do_write = self.writable & self.we
        do_read  = self.readable & self.re

        # TODO: extract this pattern into lib.cdc.GrayCounter
        produce_w_bin = Signal(self._ctr_bits)
        produce_w_nxt = Signal(self._ctr_bits)
        m.d.comb  += produce_w_nxt.eq(produce_w_bin + do_write)
        m.d.write += produce_w_bin.eq(produce_w_nxt)

        consume_r_bin = Signal(self._ctr_bits)
        consume_r_nxt = Signal(self._ctr_bits)
        m.d.comb  += consume_r_nxt.eq(consume_r_bin + do_read)
        m.d.read  += consume_r_bin.eq(consume_r_nxt)

        produce_w_gry = Signal(self._ctr_bits)
        produce_r_gry = Signal(self._ctr_bits)
        produce_enc = m.submodules.produce_enc = \
            GrayEncoder(self._ctr_bits)
        produce_cdc = m.submodules.produce_cdc = \
            MultiReg(produce_w_gry, produce_r_gry, odomain="read")
        m.d.comb  += produce_enc.i.eq(produce_w_nxt),
        m.d.write += produce_w_gry.eq(produce_enc.o)

        consume_r_gry = Signal(self._ctr_bits)
        consume_w_gry = Signal(self._ctr_bits)
        consume_enc = m.submodules.consume_enc = \
            GrayEncoder(self._ctr_bits)
        consume_cdc = m.submodules.consume_cdc = \
            MultiReg(consume_r_gry, consume_w_gry, odomain="write")
        m.d.comb  += consume_enc.i.eq(consume_r_nxt)
        m.d.read  += consume_r_gry.eq(consume_enc.o)

        m.d.comb += [
            self.writable.eq(
                (produce_w_gry[-1]  == consume_w_gry[-1]) |
                (produce_w_gry[-2]  == consume_w_gry[-2]) |
                (produce_w_gry[:-2] != consume_w_gry[:-2])),
            self.readable.eq(consume_r_gry != produce_r_gry)
        ]

        storage = Memory(self.width, self.depth)
        wrport  = m.submodules.wrport = storage.write_port(domain="write")
        rdport  = m.submodules.rdport = storage.read_port (domain="read")
        m.d.comb += [
            wrport.addr.eq(produce_w_bin[:-1]),
            wrport.data.eq(self.din),
            wrport.en.eq(do_write)
        ]
        m.d.comb += [
            rdport.addr.eq((consume_r_bin + do_read)[:-1]),
            self.dout.eq(rdport.data),
        ]

        if platform == "formal":
            # TODO: move this logic elsewhere
            initstate = Signal()
            m.submodules += Instance("$initstate", o_Y=initstate)
            with m.If(initstate):
                m.d.comb += Assume(produce_w_gry == (produce_w_bin ^ produce_w_bin[1:]))
                m.d.comb += Assume(consume_r_gry == (consume_r_bin ^ consume_r_bin[1:]))

        return m


class AsyncFIFOBuffered(FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Buffered asynchronous first in, first out queue.

    This queue's interface is identical to :class:`AsyncFIFO`, but it has an additional register
    on the output, improving timing in case of block RAM that has large clock-to-output delay.

    In exchange, the latency between an entry being written to an empty queue and that entry
    becoming available on the output is increased to one cycle.
    """.strip(),
    parameters="""
    fwft : bool
        Always set.
    """.strip(),
    attributes="",
    dout_valid="Valid if ``readable`` is asserted.",
    r_attributes="",
    w_attributes="")

    def __init__(self, width, depth):
        super().__init__(width, depth, fwft=True)

    def elaborate(self, platform):
        m = Module()
        m.submodules.unbuffered = fifo = AsyncFIFO(self.width, self.depth - 1)

        m.d.comb += [
            fifo.din.eq(self.din),
            self.writable.eq(fifo.writable),
            fifo.we.eq(self.we),
        ]

        with m.If(self.re | ~self.readable):
            m.d.read += [
                self.dout.eq(fifo.dout),
                self.readable.eq(fifo.readable)
            ]
            m.d.comb += \
                fifo.re.eq(1)

        return m
