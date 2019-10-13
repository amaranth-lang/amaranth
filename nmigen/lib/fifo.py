"""First-in first-out queues."""

from .. import *
from ..asserts import *
from .._utils import log2_int, deprecated
from .coding import GrayEncoder
from .cdc import FFSynchronizer


__all__ = ["FIFOInterface", "SyncFIFO", "SyncFIFOBuffered", "AsyncFIFO", "AsyncFIFOBuffered"]


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
    w_data : in, width
        Input data.
    w_rdy : out
        Asserted if there is space in the queue, i.e. ``w_en`` can be asserted to write
        a new entry.
    w_en : in
        Write strobe. Latches ``w_data`` into the queue. Does nothing if ``w_rdy`` is not asserted.
    {w_attributes}
    r_data : out, width
        Output data. {r_data_valid}
    r_rdy : out
        Asserted if there is an entry in the queue, i.e. ``r_en`` can be asserted to read
        an existing entry.
    r_en : in
        Read strobe. Makes the next entry (if any) available on ``r_data`` at the next cycle.
        Does nothing if ``r_rdy`` is not asserted.
    {r_attributes}
    """

    __doc__ = _doc_template.format(description="""
    Data written to the input interface (``w_data``, ``w_rdy``, ``w_en``) is buffered and can be
    read at the output interface (``r_data``, ``r_rdy``, ``r_en`). The data entry written first
    to the input also appears first on the output.
    """,
    parameters="",
    r_data_valid="The conditions in which ``r_data`` is valid depends on the type of the queue.",
    attributes="""
    fwft : bool
        First-word fallthrough. If set, when ``r_rdy`` rises, the first entry is already
        available, i.e. ``r_data`` is valid. Otherwise, after ``r_rdy`` rises, it is necessary
        to strobe ``r_en`` for ``r_data`` to become valid.
    """.strip(),
    w_attributes="",
    r_attributes="")

    def __init__(self, *, width, depth, fwft):
        if not isinstance(width, int) or width < 0:
            raise TypeError("FIFO width must be a non-negative integer, not {!r}"
                            .format(width))
        if not isinstance(depth, int) or depth < 0:
            raise TypeError("FIFO depth must be a non-negative integer, not {!r}"
                            .format(depth))
        self.width = width
        self.depth = depth
        self.fwft  = fwft

        self.w_data = Signal(width, reset_less=True)
        self.w_rdy  = Signal() # writable; not full
        self.w_en   = Signal()

        self.r_data = Signal(width, reset_less=True)
        self.r_rdy  = Signal() # readable; not empty
        self.r_en   = Signal()

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `fifo.din`, use `fifo.w_data`")
    def din(self):
        return self.w_data

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @din.setter
    @deprecated("instead of `fifo.din = x`, use `fifo.w_data = x`")
    def din(self, w_data):
        self.w_data = w_data

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `fifo.writable`, use `fifo.w_rdy`")
    def writable(self):
        return self.w_rdy

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @writable.setter
    @deprecated("instead of `fifo.writable = x`, use `fifo.w_rdy = x`")
    def writable(self, w_rdy):
        self.w_rdy = w_rdy

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `fifo.we`, use `fifo.w_en`")
    def we(self):
        return self.w_en

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @we.setter
    @deprecated("instead of `fifo.we = x`, use `fifo.w_en = x`")
    def we(self, w_en):
        self.w_en = w_en

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `fifo.dout`, use `fifo.r_data`")
    def dout(self):
        return self.r_data

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @dout.setter
    @deprecated("instead of `fifo.dout = x`, use `fifo.r_data = x`")
    def dout(self, r_data):
        self.r_data = r_data

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `fifo.readable`, use `fifo.r_rdy`")
    def readable(self):
        return self.r_rdy

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @readable.setter
    @deprecated("instead of `fifo.readable = x`, use `fifo.r_rdy = x`")
    def readable(self, r_rdy):
        self.r_rdy = r_rdy

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `fifo.re`, use `fifo.r_en`")
    def re(self):
        return self.r_en

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @re.setter
    @deprecated("instead of `fifo.re = x`, use `fifo.r_en = x`")
    def re(self, r_en):
        self.r_en = r_en


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
    parameters="""
    fwft : bool
        First-word fallthrough. If set, when the queue is empty and an entry is written into it,
        that entry becomes available on the output on the same clock cycle. Otherwise, it is
        necessary to assert ``r_en`` for ``r_data`` to become valid.
    """.strip(),
    r_data_valid="""
    For FWFT queues, valid if ``r_rdy`` is asserted. For non-FWFT queues, valid on the next
    cycle after ``r_rdy`` and ``r_en`` have been asserted.
    """.strip(),
    attributes="",
    r_attributes="""
    level : out
        Number of unread entries.
    """.strip(),
    w_attributes="")

    def __init__(self, *, width, depth, fwft=True):
        super().__init__(width=width, depth=depth, fwft=fwft)

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
            self.r_rdy.eq(self.level != 0)
        ]

        do_read  = self.r_rdy & self.r_en
        do_write = self.w_rdy & self.w_en

        storage = Memory(width=self.width, depth=self.depth)
        w_port  = m.submodules.w_port = storage.write_port()
        r_port  = m.submodules.r_port = storage.read_port(
            domain="comb" if self.fwft else "sync", transparent=self.fwft)
        produce = Signal(range(self.depth))
        consume = Signal(range(self.depth))

        m.d.comb += [
            w_port.addr.eq(produce),
            w_port.data.eq(self.w_data),
            w_port.en.eq(self.w_en & self.w_rdy)
        ]
        with m.If(do_write):
            m.d.sync += produce.eq(_incr(produce, self.depth))

        m.d.comb += [
            r_port.addr.eq(consume),
            self.r_data.eq(r_port.data),
        ]
        if not self.fwft:
            m.d.comb += r_port.en.eq(self.r_en)
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

    This queue's interface is identical to :class:`SyncFIFO` configured as ``fwft=True``, but it
    does not use asynchronous memory reads, which are incompatible with FPGA block RAMs.

    In exchange, the latency between an entry being written to an empty queue and that entry
    becoming available on the output is increased by one cycle compared to :class:`SyncFIFO`.
    """.strip(),
    parameters="""
    fwft : bool
        Always set.
    """.strip(),
    attributes="",
    r_data_valid="Valid if ``r_rdy`` is asserted.",
    r_attributes="""
    level : out
        Number of unread entries.
    """.strip(),
    w_attributes="")

    def __init__(self, *, width, depth):
        super().__init__(width=width, depth=depth, fwft=True)

        self.level = Signal(range(depth + 1))

    def elaborate(self, platform):
        m = Module()
        if self.depth == 0:
            m.d.comb += [
                self.w_rdy.eq(0),
                self.r_rdy.eq(0),
            ]
            return m

        # Effectively, this queue treats the output register of the non-FWFT inner queue as
        # an additional storage element.
        m.submodules.unbuffered = fifo = SyncFIFO(width=self.width, depth=self.depth - 1,
                                                  fwft=False)

        m.d.comb += [
            fifo.w_data.eq(self.w_data),
            fifo.w_en.eq(self.w_en),
            self.w_rdy.eq(fifo.w_rdy),
        ]

        m.d.comb += [
            self.r_data.eq(fifo.r_data),
            fifo.r_en.eq(fifo.r_rdy & (~self.r_rdy | self.r_en)),
        ]
        with m.If(fifo.r_en):
            m.d.sync += self.r_rdy.eq(1)
        with m.Elif(self.r_en):
            m.d.sync += self.r_rdy.eq(0)

        m.d.comb += self.level.eq(fifo.level + self.r_rdy)

        return m


class AsyncFIFO(Elaboratable, FIFOInterface):
    __doc__ = FIFOInterface._doc_template.format(
    description="""
    Asynchronous first in, first out queue.

    Read and write interfaces are accessed from different clock domains, which can be set when
    constructing the FIFO.

    :class:`AsyncFIFO` only supports power of 2 depths. Unless ``exact_depth`` is specified,
    the ``depth`` parameter is rounded up to the next power of 2.
    """.strip(),
    parameters="""
    r_domain : str
        Read clock domain.
    w_domain : str
        Write clock domain.
    """.strip(),
    attributes="""
    fwft : bool
        Always set.
    """.strip(),
    r_data_valid="Valid if ``r_rdy`` is asserted.",
    r_attributes="",
    w_attributes="")

    def __init__(self, *, width, depth, r_domain="read", w_domain="write", exact_depth=False):
        if depth != 0:
            try:
                depth_bits = log2_int(depth, need_pow2=exact_depth)
                depth = 1 << depth_bits
            except ValueError as e:
                raise ValueError("AsyncFIFO only supports depths that are powers of 2; requested "
                                 "exact depth {} is not"
                                 .format(depth)) from None
        else:
            depth_bits = 0
        super().__init__(width=width, depth=depth, fwft=True)

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

        consume_r_bin = Signal(self._ctr_bits)
        consume_r_nxt = Signal(self._ctr_bits)
        m.d.comb += consume_r_nxt.eq(consume_r_bin + do_read)
        m.d[self._r_domain] += consume_r_bin.eq(consume_r_nxt)

        produce_w_gry = Signal(self._ctr_bits)
        produce_r_gry = Signal(self._ctr_bits)
        produce_enc = m.submodules.produce_enc = \
            GrayEncoder(self._ctr_bits)
        produce_cdc = m.submodules.produce_cdc = \
            FFSynchronizer(produce_w_gry, produce_r_gry, o_domain=self._r_domain)
        m.d.comb += produce_enc.i.eq(produce_w_nxt),
        m.d[self._w_domain] += produce_w_gry.eq(produce_enc.o)

        consume_r_gry = Signal(self._ctr_bits)
        consume_w_gry = Signal(self._ctr_bits)
        consume_enc = m.submodules.consume_enc = \
            GrayEncoder(self._ctr_bits)
        consume_cdc = m.submodules.consume_cdc = \
            FFSynchronizer(consume_r_gry, consume_w_gry, o_domain=self._w_domain)
        m.d.comb += consume_enc.i.eq(consume_r_nxt)
        m.d[self._r_domain] += consume_r_gry.eq(consume_enc.o)

        w_full  = Signal()
        r_empty = Signal()
        m.d.comb += [
            w_full.eq((produce_w_gry[-1]  != consume_w_gry[-1]) &
                      (produce_w_gry[-2]  != consume_w_gry[-2]) &
                      (produce_w_gry[:-2] == consume_w_gry[:-2])),
            r_empty.eq(consume_r_gry == produce_r_gry),
        ]

        storage = Memory(width=self.width, depth=self.depth)
        w_port  = m.submodules.w_port = storage.write_port(domain=self._w_domain)
        r_port  = m.submodules.r_port = storage.read_port (domain=self._r_domain,
                                                           transparent=False)
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
    attributes="""
    fwft : bool
        Always set.
    """.strip(),
    r_data_valid="Valid if ``r_rdy`` is asserted.",
    r_attributes="",
    w_attributes="")

    def __init__(self, *, width, depth, r_domain="read", w_domain="write", exact_depth=False):
        if depth != 0:
            try:
                depth_bits = log2_int(max(0, depth - 1), need_pow2=exact_depth)
                depth = (1 << depth_bits) + 1
            except ValueError as e:
                raise ValueError("AsyncFIFOBuffered only supports depths that are one higher "
                                 "than powers of 2; requested exact depth {} is not"
                                 .format(depth)) from None
        super().__init__(width=width, depth=depth, fwft=True)

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

        with m.If(self.r_en | ~self.r_rdy):
            m.d[self._r_domain] += [
                self.r_data.eq(fifo.r_data),
                self.r_rdy.eq(fifo.r_rdy),
            ]
            m.d.comb += [
                fifo.r_en.eq(1)
            ]

        return m
