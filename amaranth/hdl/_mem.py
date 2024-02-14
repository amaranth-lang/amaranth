import operator
from collections import OrderedDict

from .. import tracer
from ._ast import *
from ._ir import Elaboratable, Fragment
from ..utils import ceil_log2
from .._utils import deprecated


__all__ = ["Memory", "ReadPort", "WritePort", "DummyPort"]


class MemoryIdentity: pass


class MemorySimRead:
    def __init__(self, identity, addr):
        assert isinstance(identity, MemoryIdentity)
        self._identity = identity
        self._addr = Value.cast(addr)

    def eq(self, value):
        return MemorySimWrite(self._identity, self._addr, value)


class MemorySimWrite:
    def __init__(self, identity, addr, data):
        assert isinstance(identity, MemoryIdentity)
        self._identity = identity
        self._addr = Value.cast(addr)
        self._data = Value.cast(data)


class MemoryInstance(Fragment):
    class _ReadPort:
        def __init__(self, *, domain, addr, data, en, transparent_for):
            assert isinstance(domain, str)
            self._domain = domain
            self._addr = Value.cast(addr)
            self._data = Value.cast(data)
            self._en = Value.cast(en)
            self._transparent_for = tuple(transparent_for)
            assert len(self._en) == 1
            if domain == "comb":
                assert isinstance(self._en, Const)
                assert self._en.width == 1
                assert self._en.value == 1
                assert not self._transparent_for

    class _WritePort:
        def __init__(self, *, domain, addr, data, en):
            assert isinstance(domain, str)
            assert domain != "comb"
            self._domain = domain
            self._addr = Value.cast(addr)
            self._data = Value.cast(data)
            self._en = Value.cast(en)
            if len(self._data):
                assert len(self._data) % len(self._en) == 0

        @property
        def _granularity(self):
            if not len(self._data):
                return 1
            return len(self._data) // len(self._en)


    def __init__(self, *, identity, width, depth, init=None, attrs=None, src_loc=None):
        super().__init__(src_loc=src_loc)
        assert isinstance(identity, MemoryIdentity)
        self._identity = identity
        self._width = operator.index(width)
        self._depth = operator.index(depth)
        mask = (1 << self._width) - 1
        self._init = tuple(item & mask for item in init) if init is not None else ()
        assert len(self._init) <= self._depth
        self._init += (0,) * (self._depth - len(self._init))
        for x in self._init:
            assert isinstance(x, int)
        self._attrs = attrs or {}
        self._read_ports: "list[MemoryInstance._ReadPort]" = []
        self._write_ports: "list[MemoryInstance._WritePort]" = []

    def read_port(self, *, domain, addr, data, en, transparent_for):
        port = self._ReadPort(domain=domain, addr=addr, data=data, en=en, transparent_for=transparent_for)
        assert len(port._data) == self._width
        assert len(port._addr) == ceil_log2(self._depth)
        for idx in port._transparent_for:
            assert isinstance(idx, int)
            assert idx in range(len(self._write_ports))
            assert self._write_ports[idx]._domain == port._domain
        for signal in port._data._rhs_signals():
            self.add_driver(signal, port._domain)
        self._read_ports.append(port)

    def write_port(self, *, domain, addr, data, en):
        port = self._WritePort(domain=domain, addr=addr, data=data, en=en)
        assert len(port._data) == self._width
        assert len(port._addr) == ceil_log2(self._depth)
        self._write_ports.append(port)
        return len(self._write_ports) - 1


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
    # TODO(amaranth-0.6): remove
    @deprecated("`amaranth.hdl.Memory` is deprecated, use `amaranth.lib.memory.Memory` instead")
    def __init__(self, *, width, depth, init=None, name=None, attrs=None, simulate=True):
        if not isinstance(width, int) or width < 0:
            raise TypeError("Memory width must be a non-negative integer, not {!r}"
                            .format(width))
        if not isinstance(depth, int) or depth < 0:
            raise TypeError("Memory depth must be a non-negative integer, not {!r}"
                            .format(depth))

        self.name    = name or tracer.get_var_name(depth=3, default="$memory")
        self.src_loc = tracer.get_src_loc(src_loc_at=1)

        self.width = width
        self.depth = depth
        self.attrs = OrderedDict(() if attrs is None else attrs)

        self.init = init
        self._read_ports = []
        self._write_ports = []
        self._identity = MemoryIdentity()

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
            for addr, val in enumerate(self._init):
                operator.index(val)
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
        return MemorySimRead(self._identity, index)

    def elaborate(self, platform):
        f = MemoryInstance(identity=self._identity, width=self.width, depth=self.depth, init=self.init, attrs=self.attrs, src_loc=self.src_loc)
        write_ports = {}
        for port in self._write_ports:
            port._MustUse__used = True
            iport = f.write_port(domain=port.domain, addr=port.addr, data=port.data, en=port.en)
            write_ports.setdefault(port.domain, []).append(iport)
        for port in self._read_ports:
            port._MustUse__used = True
            if port.domain == "comb":
                f.read_port(domain="comb", addr=port.addr, data=port.data, en=Const(1), transparent_for=())
            else:
                transparent_for = []
                if port.transparent:
                    transparent_for = write_ports.get(port.domain, [])
                f.read_port(domain=port.domain, addr=port.addr, data=port.data, en=port.en, transparent_for=transparent_for)
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
            self.en = Signal(name=f"{memory.name}_r_en", init=1,
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
    # TODO(amaranth-0.6): remove
    @deprecated("`DummyPort` is deprecated, use `amaranth.lib.memory.ReadPort` or `amaranth.lib.memory.WritePort` instead")
    def __init__(self, *, data_width, addr_width, domain="sync", name=None, granularity=None):
        self.domain = domain

        if granularity is None:
            granularity = data_width
        if name is None:
            name = tracer.get_var_name(depth=3, default="dummy")

        self.addr = Signal(addr_width,
                           name=f"{name}_addr", src_loc_at=1)
        self.data = Signal(data_width,
                           name=f"{name}_data", src_loc_at=1)
        self.en   = Signal(data_width // granularity,
                           name=f"{name}_en", src_loc_at=1)
