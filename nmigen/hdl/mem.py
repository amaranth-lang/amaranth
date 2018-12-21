import traceback

from .. import tracer
from .ast import *
from .ir import Instance


class Memory:
    def __init__(self, width, depth, init=None, name=None):
        if not isinstance(width, int) or width < 0:
            raise TypeError("Memory width must be a non-negative integer, not '{!r}'"
                            .format(width))
        if not isinstance(depth, int) or depth < 0:
            raise TypeError("Memory depth must be a non-negative integer, not '{!r}'"
                            .format(depth))

        tb = traceback.extract_stack(limit=2)
        self.src_loc = (tb[0].filename, tb[0].lineno)

        if name is None:
            try:
                name = tracer.get_var_name(depth=2)
            except tracer.NameNotFound:
                name = "$memory"
        self.name  = name

        self.width = width
        self.depth = depth
        self.init  = None if init is None else list(init)

    def read_port(self, domain="sync", synchronous=False, transparent=True):
        return ReadPort(self, domain, synchronous, transparent)

    def write_port(self, domain="sync", priority=0, granularity=None):
        if granularity is None:
            granularity = self.width
        if not isinstance(granularity, int) or granularity < 0 or granularity > self.width:
            raise TypeError("Write port granularity must be a non-negative integer not greater "
                            "than memory width, not '{!r}'"
                            .format(granularity))
        return WritePort(self, domain, priority, granularity)


class ReadPort:
    def __init__(self, memory, domain, synchronous, transparent):
        self.memory      = memory
        self.domain      = domain
        self.synchronous = synchronous
        self.transparent = transparent

        self.addr = Signal(max=memory.depth)
        self.data = Signal(memory.width)
        if synchronous and transparent:
            self.en = Signal()
        else:
            self.en = Const(1)

    def get_fragment(self, platform):
        return Instance("$memrd",
            p_MEMID=self.memory,
            p_ABITS=self.addr.nbits,
            p_WIDTH=self.data.nbits,
            p_CLK_ENABLE=self.synchronous,
            p_CLK_POLARITY=1,
            p_TRANSPARENT=self.transparent,
            i_CLK=ClockSignal(self.domain),
            i_EN=self.en,
            i_ADDR=self.addr,
            o_DATA=self.data,
        )

class WritePort:
    def __init__(self, memory, domain, priority, granularity):
        self.memory       = memory
        self.domain       = domain
        self.priority     = priority
        self.granularity  = granularity

        self.addr = Signal(max=memory.depth)
        self.data = Signal(memory.width)
        self.en   = Signal(memory.width // granularity)

    def get_fragment(self, platform):
        return Instance("$memwr",
            p_MEMID=self.memory,
            p_ABITS=self.addr.nbits,
            p_WIDTH=self.data.nbits,
            p_CLK_ENABLE=1,
            p_CLK_POLARITY=1,
            p_PRIORITY=self.priority,
            i_CLK=ClockSignal(self.domain),
            i_EN=Cat(Repl(en_bit, self.granularity) for en_bit in self.en),
            i_ADDR=self.addr,
            i_DATA=self.data,
        )
