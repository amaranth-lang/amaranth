"""First-in first-out queues."""

from .. import *
from ..hdl import Assume
from ..asserts import Initial
from ..utils import ceil_log2
from .cdc import FFSynchronizer, AsyncFFSynchronizer
from .memory import Memory
from . import stream


__all__ = ["FIFOInterface", "SyncFIFO", "SyncFIFOBuffered", "AsyncFIFO", "AsyncFIFOBuffered"]


def _gray_encode(val):
    return val ^ val[1:]


def _gray_decode(val):
    rhs = Const(0)
    out = [None] * len(val)
    for i in reversed(range(len(val))):
        rhs = rhs ^ val[i]
        out[i] = rhs
    return Cat(*out)


class FIFOInterface:
    _doc_template = """
    {description}

    Parameters
    ----------
    width : int
        Bit width of data entries.
    depth : int
        Depth of the queue. If zero, the FIFO cannot be read from or written to.
    {parameters}

    Attributes
    ----------
    {attributes}
    w_data : Signal(width), in
        Input data.
    w_rdy : Signal(1), out
        Asserted if there is space in the queue, i.e. ``w_en`` can be asserted to write
        a new entry.
    w_en : Signal(1), in
        Write strobe. Latches ``w_data`` into the queue. Does nothing if ``w_rdy`` is not asserted.
    w_level : Signal(range(depth + 1)), out
        Number of unread entries.
    {w_attributes}
    r_data : Signal(width), out
        Output data. {r_data_valid}
    r_rdy : Signal(1), out
        Asserted if there is an entry in the queue, i.e. ``r_en`` can be asserted to read
        an existing entry.
    r_en : Signal(1), in
        Read strobe. Makes the next entry (if any) available on ``r_data`` at the next cycle.
        Does nothing if ``r_rdy`` is not asserted.
    r_level : Signal(range(depth + 1)), out
        Number of unread entries.
    {r_attributes}
    """

    __doc__ = _doc_template.format(description="""
    Data written to the input interface (``w_data``, ``w_rdy``, ``w_en``) is buffered and can be
    read at the output interface (``r_data``, ``r_rdy``, ``r_en``). The data entry written first
    to the input also appears first on the output.
    """,
    parameters="",
    r_data_valid="The conditions in which ``r_data`` is valid depends on the type of the queue.",
    attributes="",
    w_attributes="",
    r_attributes="")

    def __init__(self, *, width, depth):
        if not isinstance(width, int) or width < 0:
            raise TypeError("FIFO width must be a non-negative integer, not {!r}"
                            .format(width))
        if not isinstance(depth, int) or depth < 0:
            raise TypeError("FIFO depth must be a non-negative integer, not {!r}"
                            .format(depth))
        self.width = width
        self.depth = depth

        self.w_data = Signal(width, reset_less=True)
        self.w_rdy  = Signal() # writable; not full
        self.w_en   = Signal()
        self.w_level = Signal(range(depth + 1))

        self.r_data = Signal(width, reset_less=True)
        self.r_rdy  = Signal() # readable; not empty
        self.r_en   = Signal()
        self.r_level = Signal(range(depth + 1))

    @property
    def w_stream(self):
        w_stream = stream.Signature(self.width).flip().create()
        w_stream.payload = self.w_data
        w_stream.valid = self.w_en
        w_stream.ready = self.w_rdy
        return w_stream

    @property
    def r_stream(self):
        r_stream = stream.Signature(self.width).create()
        r_stream.payload = self.r_data
        r_stream.valid = self.r_rdy
        r_stream.ready = self.r_en
        return r_stream


def _incr(signal, modulo):
    if modulo == 2 ** len(signal):
        return signal + 1
    else:
        return Mux(signal == modulo - 1, 0, signal + 1)


class SyncFIFO(Elaboratable, FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Synchronous first in, first out queue.

    Read and write interfaces are accessed from the same clock domain. If different clock domains
    are needed, use :class:`AsyncFIFO`.
    """.strip(),
    parameters="",
    r_data_valid="Valid if ``r_rdy`` is asserted.",
    attributes="""
    level : Signal(range(depth + 1)), out
        Number of unread entries. This level is the same between read and write for synchronous FIFOs.
    """.strip(),
    r_attributes="",
    w_attributes="")

    def __init__(self, *, width, depth):
        super().__init__(width=width, depth=depth)

        self.level = Signal(range(depth + 1))

    def elaborate(self, platform):
        m = Module()
        if self.depth == 0:
            m.d.comb += [
                self.w_rdy.eq(0),
                self.r_rdy.eq(0),
            ]
            return m

        m.d.comb += [
            self.w_rdy.eq(self.level != self.depth),
            self.r_rdy.eq(self.level != 0),
            self.w_level.eq(self.level),
            self.r_level.eq(self.level),
        ]

        do_read  = self.r_rdy & self.r_en
        do_write = self.w_rdy & self.w_en

        storage = m.submodules.storage = Memory(shape=self.width, depth=self.depth, init=[])
        w_port  = storage.write_port()
        r_port  = storage.read_port(domain="comb")
        produce = Signal(range(self.depth))
        consume = Signal(range(self.depth))

        m.d.comb += [
            w_port.addr.eq(produce),
            w_port.data.eq(self.w_data),
            w_port.en.eq(self.w_en & self.w_rdy),
        ]
        with m.If(do_write):
            m.d.sync += produce.eq(_incr(produce, self.depth))

        m.d.comb += [
            r_port.addr.eq(consume),
            self.r_data.eq(r_port.data),
        ]
        with m.If(do_read):
            m.d.sync += consume.eq(_incr(consume, self.depth))

        with m.If(do_write & ~do_read):
            m.d.sync += self.level.eq(self.level + 1)
        with m.If(do_read & ~do_write):
            m.d.sync += self.level.eq(self.level - 1)

        if platform == "formal":
            # TODO: move this logic to SymbiYosys
            with m.If(Initial()):
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


class SyncFIFOBuffered(Elaboratable, FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Buffered synchronous first in, first out queue.

    This queue's interface is identical to :class:`SyncFIFO`, but it
    does not use asynchronous memory reads, which are incompatible with FPGA block RAMs.

    In exchange, the latency between an entry being written to an empty queue and that entry
    becoming available on the output is increased by one cycle compared to :class:`SyncFIFO`.
    """.strip(),
    parameters="",
    attributes="""
    level : Signal(range(depth + 1)), out
        Number of unread entries. This level is the same between read and write for synchronous FIFOs.
    """.strip(),
    r_data_valid="Valid if ``r_rdy`` is asserted.",
    r_attributes="",
    w_attributes="")

    def __init__(self, *, width, depth):
        super().__init__(width=width, depth=depth)

        self.level = Signal(range(depth + 1))

    def elaborate(self, platform):
        m = Module()
        if self.depth == 0:
            m.d.comb += [
                self.w_rdy.eq(0),
                self.r_rdy.eq(0),
            ]
            return m

        do_write = self.w_rdy & self.w_en
        do_read = self.r_rdy & self.r_en

        m.d.comb += [
            self.w_level.eq(self.level),
            self.r_level.eq(self.level),
        ]

        if self.depth == 1:
            # Special case: a single register. Note that, by construction, this will
            # only be able to push a value every other cycle (alternating between
            # full and empty).
            m.d.comb += [
                self.w_rdy.eq(self.level == 0),
                self.r_rdy.eq(self.level == 1),
            ]
            with m.If(do_write):
                m.d.sync += [
                    self.r_data.eq(self.w_data),
                    self.level.eq(1),
                ]
            with m.If(do_read):
                m.d.sync += [
                    self.level.eq(0),
                ]

            return m

        inner_depth = self.depth - 1
        inner_level = Signal(range(inner_depth + 1))
        inner_r_rdy = Signal()

        m.d.comb += [
            self.w_rdy.eq(inner_level != inner_depth),
            inner_r_rdy.eq(inner_level != 0),
        ]

        do_inner_read  = inner_r_rdy & (~self.r_rdy | self.r_en)

        storage = m.submodules.storage = Memory(shape=self.width, depth=inner_depth, init=[])
        w_port  = storage.write_port()
        r_port  = storage.read_port(domain="sync")
        produce = Signal(range(inner_depth))
        consume = Signal(range(inner_depth))

        m.d.comb += [
            w_port.addr.eq(produce),
            w_port.data.eq(self.w_data),
            w_port.en.eq(do_write),
        ]
        with m.If(do_write):
            m.d.sync += produce.eq(_incr(produce, inner_depth))

        m.d.comb += [
            r_port.addr.eq(consume),
            self.r_data.eq(r_port.data),
            r_port.en.eq(do_inner_read)
        ]
        with m.If(do_inner_read):
            m.d.sync += consume.eq(_incr(consume, inner_depth))

        with m.If(do_write & ~do_inner_read):
            m.d.sync += inner_level.eq(inner_level + 1)
        with m.If(do_inner_read & ~do_write):
            m.d.sync += inner_level.eq(inner_level - 1)

        with m.If(do_inner_read):
            m.d.sync += self.r_rdy.eq(1)
        with m.Elif(self.r_en):
            m.d.sync += self.r_rdy.eq(0)

        m.d.comb += [
            self.level.eq(inner_level + self.r_rdy),
        ]

        if platform == "formal":
            # TODO: move this logic to SymbiYosys
            with m.If(Initial()):
                m.d.comb += [
                    Assume(produce < inner_depth),
                    Assume(consume < inner_depth),
                ]
                with m.If(produce == consume):
                    m.d.comb += Assume((inner_level == 0) | (inner_level == inner_depth))
                with m.If(produce > consume):
                    m.d.comb += Assume(inner_level == (produce - consume))
                with m.If(produce < consume):
                    m.d.comb += Assume(inner_level == (inner_depth + produce - consume))
            with m.Else():
                m.d.comb += [
                    Assert(produce < inner_depth),
                    Assert(consume < inner_depth),
                ]
                with m.If(produce == consume):
                    m.d.comb += Assert((inner_level == 0) | (inner_level == inner_depth))
                with m.If(produce > consume):
                    m.d.comb += Assert(inner_level == (produce - consume))
                with m.If(produce < consume):
                    m.d.comb += Assert(inner_level == (inner_depth + produce - consume))

        return m


class AsyncFIFO(Elaboratable, FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Asynchronous first in, first out queue.

    Read and write interfaces are accessed from different clock domains, which can be set when
    constructing the FIFO.

    :class:`AsyncFIFO` can be reset from the write clock domain. When the write domain reset is
    asserted, the FIFO becomes empty. When the read domain is reset, data remains in the FIFO - the
    read domain logic should correctly handle this case.

    :class:`AsyncFIFO` only supports power of 2 depths. Unless ``exact_depth`` is specified,
    the ``depth`` parameter is rounded up to the next power of 2.
    """.strip(),
    parameters="""
    r_domain : str
        Read clock domain.
    w_domain : str
        Write clock domain.
    """.strip(),
    attributes="",
    r_data_valid="Valid if ``r_rdy`` is asserted.",
    r_attributes="""
    r_rst : Signal(1), out
        Asserted, for at least one read-domain clock cycle, after the FIFO has been reset by
        the write-domain reset.
    """.strip(),
    w_attributes="")

    def __init__(self, *, width, depth, r_domain="read", w_domain="write", exact_depth=False):
        if depth != 0:
            depth_bits = ceil_log2(depth)
            if exact_depth and depth != 1 << depth_bits:
                raise ValueError("AsyncFIFO only supports depths that are powers of 2; requested "
                                 "exact depth {} is not"
                                 .format(depth)) from None
            depth = 1 << depth_bits
        else:
            depth_bits = 0
        super().__init__(width=width, depth=depth)

        self.r_rst = Signal()
        self._r_domain = r_domain
        self._w_domain = w_domain
        self._ctr_bits = depth_bits + 1

    def elaborate(self, platform):
        m = Module()
        if self.depth == 0:
            m.d.comb += [
                self.w_rdy.eq(0),
                self.r_rdy.eq(0),
            ]
            return m

        # The design of this queue is the "style #2" from Clifford E. Cummings' paper "Simulation
        # and Synthesis Techniques for Asynchronous FIFO Design":
        # http://www.sunburst-design.com/papers/CummingsSNUG2002SJ_FIFO1.pdf

        do_write = self.w_rdy & self.w_en
        do_read  = self.r_rdy & self.r_en

        # TODO: extract this pattern into lib.cdc.GrayCounter
        produce_w_bin = Signal(self._ctr_bits)
        produce_w_nxt = Signal(self._ctr_bits)
        m.d.comb += produce_w_nxt.eq(produce_w_bin + do_write)
        m.d[self._w_domain] += produce_w_bin.eq(produce_w_nxt)

        # Note: Both read-domain counters must be reset_less (see comments below)
        consume_r_bin = Signal(self._ctr_bits, reset_less=True)
        consume_r_nxt = Signal(self._ctr_bits)
        m.d.comb += consume_r_nxt.eq(consume_r_bin + do_read)
        m.d[self._r_domain] += consume_r_bin.eq(consume_r_nxt)

        produce_w_gry = Signal(self._ctr_bits)
        produce_r_gry = Signal(self._ctr_bits)
        produce_cdc = m.submodules.produce_cdc = \
            FFSynchronizer(produce_w_gry, produce_r_gry, o_domain=self._r_domain)
        m.d[self._w_domain] += produce_w_gry.eq(_gray_encode(produce_w_nxt))

        consume_r_gry = Signal(self._ctr_bits, reset_less=True)
        consume_w_gry = Signal(self._ctr_bits)
        consume_cdc = m.submodules.consume_cdc = \
            FFSynchronizer(consume_r_gry, consume_w_gry, o_domain=self._w_domain)
        m.d[self._r_domain] += consume_r_gry.eq(_gray_encode(consume_r_nxt))

        consume_w_bin = Signal(self._ctr_bits)
        m.d[self._w_domain] += consume_w_bin.eq(_gray_decode(consume_w_gry))

        produce_r_bin = Signal(self._ctr_bits)
        m.d.comb += produce_r_bin.eq(_gray_decode(produce_r_gry))

        w_full  = Signal()
        r_empty = Signal()
        m.d.comb += [
            w_full.eq((produce_w_gry[-1]  != consume_w_gry[-1]) &
                      (produce_w_gry[-2]  != consume_w_gry[-2]) &
                      (produce_w_gry[:-2] == consume_w_gry[:-2])),
            r_empty.eq(consume_r_gry == produce_r_gry),
        ]

        m.d[self._w_domain] += self.w_level.eq(produce_w_bin - consume_w_bin)
        m.d.comb += self.r_level.eq(produce_r_bin - consume_r_bin)

        storage = m.submodules.storage = Memory(shape=self.width, depth=self.depth, init=[])
        w_port  = storage.write_port(domain=self._w_domain)
        r_port  = storage.read_port (domain=self._r_domain)
        m.d.comb += [
            w_port.addr.eq(produce_w_bin[:-1]),
            w_port.data.eq(self.w_data),
            w_port.en.eq(do_write),
            self.w_rdy.eq(~w_full),
        ]
        m.d.comb += [
            r_port.addr.eq(consume_r_nxt[:-1]),
            self.r_data.eq(r_port.data),
            r_port.en.eq(1),
            self.r_rdy.eq(~r_empty),
        ]

        # Reset handling to maintain FIFO and CDC invariants in the presence of a write-domain
        # reset.
        # There is a CDC hazard associated with resetting an async FIFO - Gray code counters which
        # are reset to 0 violate their Gray code invariant. One way to handle this is to ensure
        # that both sides of the FIFO are asynchronously reset by the same signal. We adopt a
        # slight variation on this approach - reset control rests entirely with the write domain.
        # The write domain's reset signal is used to asynchronously reset the read domain's
        # counters and force the FIFO to be empty when the write domain's reset is asserted.
        # This requires the two read domain counters to be marked as "reset_less", as they are
        # reset through another mechanism. See https://github.com/amaranth-lang/amaranth/issues/181
        # for the full discussion.
        w_rst = ResetSignal(domain=self._w_domain, allow_reset_less=True)
        r_rst = Signal()

        # Async-set-sync-release synchronizer avoids CDC hazards
        rst_cdc = m.submodules.rst_cdc = \
            AsyncFFSynchronizer(w_rst, r_rst, o_domain=self._r_domain)

        # Decode Gray code counter synchronized from write domain to overwrite binary
        # counter in read domain.
        with m.If(r_rst):
            m.d.comb += r_empty.eq(1)
            m.d[self._r_domain] += consume_r_gry.eq(produce_r_gry)
            m.d[self._r_domain] += consume_r_bin.eq(_gray_decode(produce_r_gry))
            m.d[self._r_domain] += self.r_rst.eq(1)
        with m.Else():
            m.d[self._r_domain] += self.r_rst.eq(0)

        if platform == "formal":
            with m.If(Initial()):
                m.d.comb += Assume(produce_w_gry == (produce_w_bin ^ produce_w_bin[1:]))
                m.d.comb += Assume(consume_r_gry == (consume_r_bin ^ consume_r_bin[1:]))

        return m


class AsyncFIFOBuffered(Elaboratable, FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Buffered asynchronous first in, first out queue.

    Read and write interfaces are accessed from different clock domains, which can be set when
    constructing the FIFO.

    :class:`AsyncFIFOBuffered` only supports power of 2 plus one depths. Unless ``exact_depth``
    is specified, the ``depth`` parameter is rounded up to the next power of 2 plus one.
    (The output buffer acts as an additional queue element.)

    This queue's interface is identical to :class:`AsyncFIFO`, but it has an additional register
    on the output, improving timing in case of block RAM that has large clock-to-output delay.

    In exchange, the latency between an entry being written to an empty queue and that entry
    becoming available on the output is increased by one cycle compared to :class:`AsyncFIFO`.
    """.strip(),
    parameters="""
    r_domain : str
        Read clock domain.
    w_domain : str
        Write clock domain.
    """.strip(),
    attributes="",
    r_data_valid="Valid if ``r_rdy`` is asserted.",
    r_attributes="""
    r_rst : Signal(1), out
        Asserted, for at least one read-domain clock cycle, after the FIFO has been reset by
        the write-domain reset.
    """.strip(),
    w_attributes="")

    def __init__(self, *, width, depth, r_domain="read", w_domain="write", exact_depth=False):
        if depth != 0:
            depth_bits = ceil_log2(max(0, depth - 1))
            if exact_depth and depth != (1 << depth_bits) + 1:
                raise ValueError("AsyncFIFOBuffered only supports depths that are one higher "
                                 "than powers of 2; requested exact depth {} is not"
                                 .format(depth)) from None
            depth = (1 << depth_bits) + 1
        super().__init__(width=width, depth=depth)

        self.r_rst = Signal()
        self._r_domain = r_domain
        self._w_domain = w_domain

    def elaborate(self, platform):
        m = Module()
        if self.depth == 0:
            m.d.comb += [
                self.w_rdy.eq(0),
                self.r_rdy.eq(0),
            ]
            return m

        m.submodules.unbuffered = fifo = AsyncFIFO(width=self.width, depth=self.depth - 1,
            r_domain=self._r_domain, w_domain=self._w_domain)

        m.d.comb += [
            fifo.w_data.eq(self.w_data),
            self.w_rdy.eq(fifo.w_rdy),
            fifo.w_en.eq(self.w_en),
        ]

        r_consume_buffered = Signal()
        m.d.comb += r_consume_buffered.eq((self.r_rdy - self.r_en) & self.r_rdy)
        m.d[self._r_domain] += self.r_level.eq(fifo.r_level + r_consume_buffered)

        w_consume_buffered = Signal()
        m.submodules.consume_buffered_cdc = FFSynchronizer(r_consume_buffered, w_consume_buffered, o_domain=self._w_domain, stages=4)
        m.d.comb += self.w_level.eq(fifo.w_level + w_consume_buffered)

        with m.If(self.r_en | ~self.r_rdy):
            m.d[self._r_domain] += [
                self.r_data.eq(fifo.r_data),
                self.r_rdy.eq(fifo.r_rdy),
                self.r_rst.eq(fifo.r_rst),
            ]
            m.d.comb += [
                fifo.r_en.eq(1)
            ]

        return m
