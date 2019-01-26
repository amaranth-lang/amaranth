from .. import tracer
from .ast import *
from .ir import Instance


__all__ = ["Memory", "ReadPort", "WritePort", "DummyPort"]


class Memory:
    def __init__(self, width, depth, init=None, name=None, simulate=True):
        if not isinstance(width, int) or width < 0:
            raise TypeError("Memory width must be a non-negative integer, not '{!r}'"
                            .format(width))
        if not isinstance(depth, int) or depth < 0:
            raise TypeError("Memory depth must be a non-negative integer, not '{!r}'"
                            .format(depth))

        if name is None:
            try:
                name = tracer.get_var_name(depth=2)
            except tracer.NameNotFound:
                name = "$memory"
        self.name    = name
        self.src_loc = tracer.get_src_loc()

        self.width = width
        self.depth = depth

        # Array of signals for simulation.
        self._array = Array()
        if simulate:
            for addr in range(self.depth):
                self._array.append(Signal(self.width, name="{}({})".format(name, addr)))

        self.init = init

    @property
    def init(self):
        return self._init

    @init.setter
    def init(self, new_init):
        self._init = [] if new_init is None else list(new_init)
        if len(self.init) > self.depth:
            raise ValueError("Memory initialization value count exceed memory depth ({} > {})"
                             .format(len(self.init), self.depth))

        for addr in range(len(self._array)):
            if addr < len(self._init):
                self._array[addr].reset = self._init[addr]
            else:
                self._array[addr].reset = 0

    def read_port(self, domain="sync", synchronous=True, transparent=True):
        if not synchronous and not transparent:
            raise ValueError("Read port cannot be simultaneously asynchronous and non-transparent")
        return ReadPort(self, domain, synchronous, transparent)

    def write_port(self, domain="sync", priority=0, granularity=None):
        if granularity is None:
            granularity = self.width
        if not isinstance(granularity, int) or granularity < 0:
            raise TypeError("Write port granularity must be a non-negative integer, not '{!r}'"
                            .format(granularity))
        if granularity > self.width:
            raise ValueError("Write port granularity must not be greater than memory width "
                             "({} > {})"
                             .format(granularity, self.width))
        if self.width // granularity * granularity != self.width:
            raise ValueError("Write port granularity must divide memory width evenly")
        return WritePort(self, domain, priority, granularity)

    def __getitem__(self, index):
        """Simulation only."""
        return self._array[index]


class ReadPort:
    def __init__(self, memory, domain, synchronous, transparent):
        self.memory      = memory
        self.domain      = domain
        self.synchronous = synchronous
        self.transparent = transparent

        self.addr = Signal(max=memory.depth,
                           name="{}_r_addr".format(memory.name))
        self.data = Signal(memory.width,
                           name="{}_r_data".format(memory.name))
        if synchronous and not transparent:
            self.en = Signal(name="{}_r_en".format(memory.name))
        else:
            self.en = Const(1)

    def elaborate(self, platform):
        f = Instance("$memrd",
            p_MEMID=self.memory,
            p_ABITS=self.addr.nbits,
            p_WIDTH=self.data.nbits,
            p_CLK_ENABLE=self.synchronous,
            p_CLK_POLARITY=1,
            p_TRANSPARENT=self.transparent,
            i_CLK=ClockSignal(self.domain) if self.synchronous else Const(0),
            i_EN=self.en,
            i_ADDR=self.addr,
            o_DATA=self.data,
        )
        if self.synchronous and not self.transparent:
            # Synchronous, read-before-write port
            f.add_statements(
                Switch(self.en, {
                    1: self.data.eq(self.memory._array[self.addr])
                })
            )
            f.add_driver(self.data, self.domain)
        elif self.synchronous:
            # Synchronous, write-through port
            # This model is a bit unconventional. We model transparent ports as asynchronous ports
            # that are latched when the clock is high. This isn't exactly correct, but it is very
            # close to the correct behavior of a transparent port, and the difference should only
            # be observable in pathological cases of clock gating. A register is injected to
            # the address input to achieve the correct address-to-data latency. Also, the reset
            # value of the data output is forcibly set to the 0th initial value, if any--note that
            # many FPGAs do not guarantee this behavior!
            if len(self.memory.init) > 0:
                self.data.reset = self.memory.init[0]
            latch_addr = Signal.like(self.addr)
            f.add_statements(
                latch_addr.eq(self.addr),
                Switch(ClockSignal(self.domain), {
                    0: self.data.eq(self.data),
                    1: self.data.eq(self.memory._array[latch_addr]),
                }),
            )
            f.add_driver(latch_addr, self.domain)
            f.add_driver(self.data)
        else:
            # Asynchronous port
            f.add_statements(self.data.eq(self.memory._array[self.addr]))
            f.add_driver(self.data)
        return f


class WritePort:
    def __init__(self, memory, domain, priority, granularity):
        self.memory       = memory
        self.domain       = domain
        self.priority     = priority
        self.granularity  = granularity

        self.addr = Signal(max=memory.depth,
                           name="{}_w_addr".format(memory.name))
        self.data = Signal(memory.width,
                           name="{}_w_data".format(memory.name))
        self.en   = Signal(memory.width // granularity,
                           name="{}_w_en".format(memory.name))

    def elaborate(self, platform):
        f = Instance("$memwr",
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
        if len(self.en) > 1:
            for index, en_bit in enumerate(self.en):
                offset = index * self.granularity
                bits   = slice(offset, offset + self.granularity)
                write_data = self.memory._array[self.addr][bits].eq(self.data[bits])
                f.add_statements(Switch(en_bit, { 1: write_data }))
        else:
            write_data = self.memory._array[self.addr].eq(self.data)
            f.add_statements(Switch(self.en, { 1: write_data }))
        for signal in self.memory._array:
            f.add_driver(signal, self.domain)
        return f


class DummyPort:
    """Dummy memory port.

    This port can be used in place of either a read or a write port for testing and verification.
    It does not include any read/write port specific attributes, i.e. none besides ``"domain"``;
    any such attributes may be set manually.
    """
    def __init__(self, width, addr_bits, domain="sync", name=None, granularity=None):
        self.domain = domain

        if granularity is None:
            granularity = width
        if name is None:
            try:
                name = tracer.get_var_name(depth=2)
            except tracer.NameNotFound:
                name = "dummy"

        self.addr = Signal(addr_bits,
                           name="{}_addr".format(name))
        self.data = Signal(width,
                           name="{}_data".format(name))
        self.en   = Signal(width // granularity,
                           name="{}_en".format(name))
