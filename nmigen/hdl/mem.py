import operator
from collections import OrderedDict

from .. import tracer
from .ast import *
from .ir import Elaboratable, Instance


__all__ = ["Memory", "ReadPort", "WritePort", "DummyPort"]


class Memory:
    """A word addressable storage.

    Parameters
    ----------
    width : int
        Access granularity. Each storage element of this memory is ``width`` bits in size.
    depth : int
        Word count. This memory contains ``depth`` storage elements.
    init : list of int
        Initial values. At power on, each storage element in this memory is initialized to
        the corresponding element of ``init``, if any, or to zero otherwise.
        Uninitialized memories are not currently supported.
    name : str
        Name hint for this memory. If ``None`` (default) the name is inferred from the variable
        name this ``Signal`` is assigned to.
    attrs : dict
        Dictionary of synthesis attributes.

    Attributes
    ----------
    width : int
    depth : int
    init : list of int
    attrs : dict
    """
    def __init__(self, *, width, depth, init=None, name=None, attrs=None, simulate=True):
        if not isinstance(width, int) or width < 0:
            raise TypeError("Memory width must be a non-negative integer, not {!r}"
                            .format(width))
        if not isinstance(depth, int) or depth < 0:
            raise TypeError("Memory depth must be a non-negative integer, not {!r}"
                            .format(depth))

        self.name    = name or tracer.get_var_name(depth=2, default="$memory")
        self.src_loc = tracer.get_src_loc()

        self.width = width
        self.depth = depth
        self.attrs = OrderedDict(() if attrs is None else attrs)

        # Array of signals for simulation.
        self._array = Array()
        if simulate:
            for addr in range(self.depth):
                self._array.append(Signal(self.width, name="{}({})"
                                          .format(name or "memory", addr)))

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

        try:
            for addr in range(len(self._array)):
                if addr < len(self._init):
                    self._array[addr].reset = operator.index(self._init[addr])
                else:
                    self._array[addr].reset = 0
        except TypeError as e:
            raise TypeError("Memory initialization value at address {:x}: {}"
                            .format(addr, e)) from None

    def read_port(self, *, src_loc_at=0, **kwargs):
        """Get a read port.

        See :class:`ReadPort` for details.

        Arguments
        ---------
        domain : str
        transparent : bool

        Returns
        -------
        An instance of :class:`ReadPort` associated with this memory.
        """
        return ReadPort(self, src_loc_at=1 + src_loc_at, **kwargs)

    def write_port(self, *, src_loc_at=0, **kwargs):
        """Get a write port.

        See :class:`WritePort` for details.

        Arguments
        ---------
        domain : str
        granularity : int

        Returns
        -------
        An instance of :class:`WritePort` associated with this memory.
        """
        return WritePort(self, src_loc_at=1 + src_loc_at, **kwargs)

    def __getitem__(self, index):
        """Simulation only."""
        return self._array[index]


class ReadPort(Elaboratable):
    """A memory read port.

    Parameters
    ----------
    memory : :class:`Memory`
        Memory associated with the port.
    domain : str
        Clock domain. Defaults to ``"sync"``. If set to ``"comb"``, the port is asynchronous.
        Otherwise, the read data becomes available on the next clock cycle.
    transparent : bool
        Port transparency. If set (default), a read at an address that is also being written to in
        the same clock cycle will output the new value. Otherwise, the old value will be output
        first. This behavior only applies to ports in the same domain.

    Attributes
    ----------
    memory : :class:`Memory`
    domain : str
    transparent : bool
    addr : Signal(range(memory.depth)), in
        Read address.
    data : Signal(memory.width), out
        Read data.
    en : Signal or Const, in
        Read enable. If asserted, ``data`` is updated with the word stored at ``addr``. Note that
        transparent ports cannot assign ``en`` (which is hardwired to 1 instead), as doing so is
        currently not supported by Yosys.

    Exceptions
    ----------
    Raises :exn:`ValueError` if the read port is simultaneously asynchronous and non-transparent.
    """
    def __init__(self, memory, *, domain="sync", transparent=True, src_loc_at=0):
        if domain == "comb" and not transparent:
            raise ValueError("Read port cannot be simultaneously asynchronous and non-transparent")

        self.memory      = memory
        self.domain      = domain
        self.transparent = transparent

        self.addr = Signal(range(memory.depth),
                           name="{}_r_addr".format(memory.name), src_loc_at=1 + src_loc_at)
        self.data = Signal(memory.width,
                           name="{}_r_data".format(memory.name), src_loc_at=1 + src_loc_at)
        if self.domain != "comb" and not transparent:
            self.en = Signal(name="{}_r_en".format(memory.name), reset=1,
                             src_loc_at=1 + src_loc_at)
        else:
            self.en = Const(1)

    def elaborate(self, platform):
        f = Instance("$memrd",
            p_MEMID=self.memory,
            p_ABITS=self.addr.width,
            p_WIDTH=self.data.width,
            p_CLK_ENABLE=self.domain != "comb",
            p_CLK_POLARITY=1,
            p_TRANSPARENT=self.transparent,
            i_CLK=ClockSignal(self.domain) if self.domain != "comb" else Const(0),
            i_EN=self.en,
            i_ADDR=self.addr,
            o_DATA=self.data,
        )
        if self.domain == "comb":
            # Asynchronous port
            f.add_statements(self.data.eq(self.memory._array[self.addr]))
            f.add_driver(self.data)
        elif not self.transparent:
            # Synchronous, read-before-write port
            f.add_statements(
                Switch(self.en, {
                    1: self.data.eq(self.memory._array[self.addr])
                })
            )
            f.add_driver(self.data, self.domain)
        else:
            # Synchronous, write-through port
            # This model is a bit unconventional. We model transparent ports as asynchronous ports
            # that are latched when the clock is high. This isn't exactly correct, but it is very
            # close to the correct behavior of a transparent port, and the difference should only
            # be observable in pathological cases of clock gating. A register is injected to
            # the address input to achieve the correct address-to-data latency. Also, the reset
            # value of the data output is forcibly set to the 0th initial value, if any--note that
            # many FPGAs do not guarantee this behavior!
            if len(self.memory.init) > 0:
                self.data.reset = operator.index(self.memory.init[0])
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
        return f


class WritePort(Elaboratable):
    """A memory write port.

    Parameters
    ----------
    memory : :class:`Memory`
        Memory associated with the port.
    domain : str
        Clock domain. Defaults to ``"sync"``. Writes have a latency of 1 clock cycle.
    granularity : int
        Port granularity. Defaults to ``memory.width``. Write data is split evenly in
        ``memory.width // granularity`` chunks, which can be updated independently.

    Attributes
    ----------
    memory : :class:`Memory`
    domain : str
    granularity : int
    addr : Signal(range(memory.depth)), in
        Write address.
    data : Signal(memory.width), in
        Write data.
    en : Signal(memory.width // granularity), in
        Write enable. Each bit selects a non-overlapping chunk of ``granularity`` bits on the
        ``data`` signal, which is written to memory at ``addr``. Unselected chunks are ignored.

    Exceptions
    ----------
    Raises :exn:`ValueError` if the write port granularity is greater than memory width, or does not
    divide memory width evenly.
    """
    def __init__(self, memory, *, domain="sync", granularity=None, src_loc_at=0):
        if granularity is None:
            granularity = memory.width
        if not isinstance(granularity, int) or granularity < 0:
            raise TypeError("Write port granularity must be a non-negative integer, not {!r}"
                            .format(granularity))
        if granularity > memory.width:
            raise ValueError("Write port granularity must not be greater than memory width "
                             "({} > {})"
                             .format(granularity, memory.width))
        if memory.width // granularity * granularity != memory.width:
            raise ValueError("Write port granularity must divide memory width evenly")

        self.memory       = memory
        self.domain       = domain
        self.granularity  = granularity

        self.addr = Signal(range(memory.depth),
                           name="{}_w_addr".format(memory.name), src_loc_at=1 + src_loc_at)
        self.data = Signal(memory.width,
                           name="{}_w_data".format(memory.name), src_loc_at=1 + src_loc_at)
        self.en   = Signal(memory.width // granularity,
                           name="{}_w_en".format(memory.name), src_loc_at=1 + src_loc_at)

    def elaborate(self, platform):
        f = Instance("$memwr",
            p_MEMID=self.memory,
            p_ABITS=self.addr.width,
            p_WIDTH=self.data.width,
            p_CLK_ENABLE=1,
            p_CLK_POLARITY=1,
            p_PRIORITY=0,
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
    def __init__(self, *, data_width, addr_width, domain="sync", name=None, granularity=None):
        self.domain = domain

        if granularity is None:
            granularity = data_width
        if name is None:
            name = tracer.get_var_name(depth=2, default="dummy")

        self.addr = Signal(addr_width,
                           name="{}_addr".format(name), src_loc_at=1)
        self.data = Signal(data_width,
                           name="{}_data".format(name), src_loc_at=1)
        self.en   = Signal(data_width // granularity,
                           name="{}_en".format(name), src_loc_at=1)
