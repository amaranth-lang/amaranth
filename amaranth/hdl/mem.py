import operator
from collections import OrderedDict

from .. import tracer
from .ast import *
from .ir import Elaboratable, Instance, Fragment


__all__ = ["Memory", "ReadPort", "WritePort", "DummyPort"]


class Memory(Elaboratable):
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
        self._read_ports = []
        self._write_ports = []

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

    def elaborate(self, platform):
        init = "".join(format(Const(elem, unsigned(self.width)).value, f"0{self.width}b") for elem in reversed(self.init))
        init = Const(int(init or "0", 2), self.depth * self.width)
        rd_clk = []
        rd_clk_enable = 0
        rd_transparency_mask = 0
        for index, port in enumerate(self._read_ports):
            if port.domain != "comb":
                rd_clk.append(ClockSignal(port.domain))
                rd_clk_enable |= 1 << index
                if port.transparent:
                    for write_index, write_port in enumerate(self._write_ports):
                        if port.domain == write_port.domain:
                            rd_transparency_mask |= 1 << (index * len(self._write_ports) + write_index)
            else:
                rd_clk.append(Const(0, 1))
        f = Instance("$mem_v2",
            *(("a", attr, value) for attr, value in self.attrs.items()),
            p_SIZE=self.depth,
            p_OFFSET=0,
            p_ABITS=Shape.cast(range(self.depth)).width,
            p_WIDTH=self.width,
            p_INIT=init,
            p_RD_PORTS=len(self._read_ports),
            p_RD_CLK_ENABLE=Const(rd_clk_enable, len(self._read_ports)) if self._read_ports else Const(0, 1),
            p_RD_CLK_POLARITY=Const(-1, unsigned(len(self._read_ports))) if self._read_ports else Const(0, 1),
            p_RD_TRANSPARENCY_MASK=Const(rd_transparency_mask, max(1, len(self._read_ports) * len(self._write_ports))),
            p_RD_COLLISION_X_MASK=Const(0, max(1, len(self._read_ports) * len(self._write_ports))),
            p_RD_WIDE_CONTINUATION=Const(0, len(self._read_ports)) if self._read_ports else Const(0, 1),
            p_RD_CE_OVER_SRST=Const(0, len(self._read_ports)) if self._read_ports else Const(0, 1),
            p_RD_ARST_VALUE=Const(0, len(self._read_ports) * self.width),
            p_RD_SRST_VALUE=Const(0, len(self._read_ports) * self.width),
            p_RD_INIT_VALUE=Const(0, len(self._read_ports) * self.width),
            p_WR_PORTS=len(self._write_ports),
            p_WR_CLK_ENABLE=Const(-1, unsigned(len(self._write_ports))) if self._write_ports else Const(0, 1),
            p_WR_CLK_POLARITY=Const(-1, unsigned(len(self._write_ports))) if self._write_ports else Const(0, 1),
            p_WR_PRIORITY_MASK=Const(0, len(self._write_ports) * len(self._write_ports)) if self._write_ports else Const(0, 1),
            p_WR_WIDE_CONTINUATION=Const(0, len(self._write_ports)) if self._write_ports else Const(0, 1),
            i_RD_CLK=Cat(rd_clk),
            i_RD_EN=Cat(port.en for port in self._read_ports),
            i_RD_ARST=Const(0, len(self._read_ports)),
            i_RD_SRST=Const(0, len(self._read_ports)),
            i_RD_ADDR=Cat(port.addr for port in self._read_ports),
            o_RD_DATA=Cat(port.data for port in self._read_ports),
            i_WR_CLK=Cat(ClockSignal(port.domain) for port in self._write_ports),
            i_WR_EN=Cat(Cat(en_bit.replicate(port.granularity) for en_bit in port.en) for port in self._write_ports),
            i_WR_ADDR=Cat(port.addr for port in self._write_ports),
            i_WR_DATA=Cat(port.data for port in self._write_ports),
        )
        for port in self._read_ports:
            port._MustUse__used = True
            if port.domain == "comb":
                # Asynchronous port
                f.add_statements(port.data.eq(self._array[port.addr]))
                f.add_driver(port.data)
            else:
                # Synchronous port
                data = self._array[port.addr]
                for write_port in self._write_ports:
                    if port.domain == write_port.domain and port.transparent:
                        if len(write_port.en) > 1:
                            parts = []
                            for index, en_bit in enumerate(write_port.en):
                                offset = index * write_port.granularity
                                bits   = slice(offset, offset + write_port.granularity)
                                cond = en_bit & (port.addr == write_port.addr)
                                parts.append(Mux(cond, write_port.data[bits], data[bits]))
                            data = Cat(parts)
                        else:
                            cond = write_port.en & (port.addr == write_port.addr)
                            data = Mux(cond, write_port.data, data)
                f.add_statements(
                    Switch(port.en, {
                        1: port.data.eq(data)
                    })
                )
                f.add_driver(port.data, port.domain)
        for port in self._write_ports:
            port._MustUse__used = True
            if len(port.en) > 1:
                for index, en_bit in enumerate(port.en):
                    offset = index * port.granularity
                    bits   = slice(offset, offset + port.granularity)
                    write_data = self._array[port.addr][bits].eq(port.data[bits])
                    f.add_statements(Switch(en_bit, { 1: write_data }))
            else:
                write_data = self._array[port.addr].eq(port.data)
                f.add_statements(Switch(port.en, { 1: write_data }))
            for signal in self._array:
                f.add_driver(signal, port.domain)
        return f

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
        Read enable. If asserted, ``data`` is updated with the word stored at ``addr``.

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
                           name=f"{memory.name}_r_addr", src_loc_at=1 + src_loc_at)
        self.data = Signal(memory.width,
                           name=f"{memory.name}_r_data", src_loc_at=1 + src_loc_at)
        if self.domain != "comb":
            self.en = Signal(name=f"{memory.name}_r_en", reset=1,
                             src_loc_at=1 + src_loc_at)
        else:
            self.en = Const(1)

        memory._read_ports.append(self)

    def elaborate(self, platform):
        if self is self.memory._read_ports[0]:
            return self.memory
        else:
            return Fragment()


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
                           name=f"{memory.name}_w_addr", src_loc_at=1 + src_loc_at)
        self.data = Signal(memory.width,
                           name=f"{memory.name}_w_data", src_loc_at=1 + src_loc_at)
        self.en   = Signal(memory.width // granularity,
                           name=f"{memory.name}_w_en", src_loc_at=1 + src_loc_at)

        memory._write_ports.append(self)

    def elaborate(self, platform):
        if not self.memory._read_ports and self is self.memory._write_ports[0]:
            return self.memory
        else:
            return Fragment()


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
                           name=f"{name}_addr", src_loc_at=1)
        self.data = Signal(data_width,
                           name=f"{name}_data", src_loc_at=1)
        self.en   = Signal(data_width // granularity,
                           name=f"{name}_en", src_loc_at=1)
