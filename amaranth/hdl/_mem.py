import operator
from collections import OrderedDict
from collections.abc import MutableSequence

from .. import tracer
from ._ast import *
from ._ast import _get_init_value
from ._ir import Elaboratable, Fragment, AlreadyElaborated
from ..utils import ceil_log2
from .._utils import deprecated, final


__all__ = ["MemoryData", "Memory", "ReadPort", "WritePort", "DummyPort"]


@final
class MemoryData:
    """Abstract description of a memory array.

    A :class:`MemoryData` object describes the geometry (shape and depth) and the initial contents
    of a memory array, without specifying the way in which it is accessed. It is conceptually
    similar to an array of :class:`Signal`\\ s.

    The :py:`init` parameter and assignment to the :py:`init` attribute have the same effect, with
    :class:`MemoryData.Init` converting elements of the iterable to match :py:`shape` and using
    a default value for rows that are not explicitly initialized.

    Changing the initial contents of a :class:`MemoryData` is only possible until it is used to
    elaborate a memory; afterwards, attempting to do so will raise the :class:`AlreadyElaborated`
    exception.

    .. warning::

        Uninitialized memories (including ASIC memories and some FPGA memories) are
        `not yet supported <https://github.com/amaranth-lang/amaranth/issues/270>`_, and
        the :py:`init` parameter must be always provided, if only as :py:`init=[]`.

    Parameters
    ----------
    shape : :ref:`shape-like <lang-shapelike>` object
        Shape of each memory row.
    depth : :class:`int`
        Number of memory rows.
    init : iterable of initial values
        Initial values for memory rows.
    """

    @final
    class Init(MutableSequence):
        """Init(...)

        Memory initialization data.

        This is a special container used only for initial contents of memories. It is similar
        to :class:`list`, but does not support inserting or deleting elements; its length is always
        the same as the depth of the memory it belongs to.

        If :py:`shape` is a :ref:`custom shape-castable object <lang-shapecustom>`, then:

        * Each element must be convertible to :py:`shape` via :meth:`.ShapeCastable.const`, and
        * Elements that are not explicitly initialized default to :py:`shape.const(None)`.

        Otherwise (when :py:`shape` is a :class:`.Shape`):

        * Each element must be an :class:`int`, and
        * Elements that are not explicitly initialized default to :py:`0`.
        """
        def __init__(self, elems, *, shape, depth):
            Shape.cast(shape)
            if not isinstance(depth, int) or depth < 0:
                raise TypeError("Memory depth must be a non-negative integer, not {!r}"
                                .format(depth))
            self._shape = shape
            self._depth = depth
            self._frozen = False

            if isinstance(shape, ShapeCastable):
                self._elems = [None] * depth
                self._raw = [Const.cast(Const(None, shape)).value] * depth
            else:
                self._elems = [0] * depth
                self._raw = self._elems # intentionally mutably aliased
            elems = list(elems)
            if len(elems) > depth:
                raise ValueError(f"Memory initialization value count exceeds memory depth ({len(elems)} > {depth})")
            for index, item in enumerate(elems):
                try:
                    self[index] = item
                except (TypeError, ValueError) as e:
                    raise type(e)(f"Memory initialization value at address {index:x}: {e}") from None

        @property
        def shape(self):
            return self._shape

        def __getitem__(self, index):
            return self._elems[index]

        def __setitem__(self, index, value):
            if self._frozen:
                raise AlreadyElaborated("Cannot set 'init' on a memory that has already been elaborated")

            if isinstance(index, slice):
                indices = range(*index.indices(len(self._elems)))
                if len(value) != len(indices):
                    raise ValueError("Changing length of Memory.init is not allowed")
                for actual_index, actual_value in zip(indices, value):
                    self[actual_index] = actual_value
            else:
                raw = _get_init_value(value, self._shape, "memory")
                if isinstance(self._shape, ShapeCastable):
                    self._raw[index] = raw
                else:
                    value = raw
                    # self._raw[index] assigned by the following line
                self._elems[index] = value

        def __delitem__(self, index):
            raise TypeError("Deleting elements from Memory.init is not allowed")

        def insert(self, index, value):
            """:meta private:"""
            raise TypeError("Inserting elements into Memory.init is not allowed")

        def __len__(self):
            return self._depth

        def __repr__(self):
            return f"MemoryData.Init({self._elems!r}, shape={self._shape!r}, depth={self._depth})"


    @final
    class _Row(Value):
        def __init__(self, memory, index, *, src_loc_at=0):
            assert isinstance(memory, MemoryData)
            self._memory = memory
            self._index = operator.index(index)
            assert self._index in range(memory.depth)
            super().__init__(src_loc_at=src_loc_at)

        def shape(self):
            return Shape.cast(self._memory.shape)

        def _lhs_signals(self):
            # This value cannot ever appear in a design.
            raise NotImplementedError # :nocov:

        _rhs_signals = _lhs_signals

        def __repr__(self):
            return f"(memory-row {self._memory!r} {self._index})"


    def __init__(self, *, shape, depth, init, src_loc_at=0):
        # shape and depth validation is performed in MemoryData.Init()
        self._shape = shape
        self._depth = depth
        self._init = MemoryData.Init(init, shape=shape, depth=depth)
        self.src_loc = tracer.get_src_loc(src_loc_at=src_loc_at)
        self.name = tracer.get_var_name(depth=2+src_loc_at, default="$memory")
        self._frozen = False

    def freeze(self):
        self._frozen = True
        self._init._frozen = True

    @property
    def shape(self):
        return self._shape

    @property
    def depth(self):
        return self._depth

    @property
    def init(self):
        return self._init

    @init.setter
    def init(self, init):
        if self._frozen:
            raise AlreadyElaborated("Cannot set 'init' on a memory that has already been elaborated")
        self._init = MemoryData.Init(init, shape=self._shape, depth=self._depth)

    def __repr__(self):
        return f"(memory-data {self.name})"

    def __getitem__(self, index):
        """Retrieve a memory row for simulation.

        A :class:`MemoryData` object can be indexed with an :class:`int` to construct a special
        value that can be used to read and write the selected memory row in a simulation testbench,
        without having to create a memory port.

        .. tip::

            Even in a simulation, the value returned by this function cannot be used in a module;
            it can only be used with :py:`sim.get()` and :py:`sim.set()`.

        Returns
        -------
        :class:`~amaranth.hdl.Value`, :ref:`assignable <lang-assignable>`
        """
        index = operator.index(index)
        if index not in range(self.depth):
            raise IndexError(f"Index {index} is out of bounds (memory has {self.depth} rows)")
        row = MemoryData._Row(self, index)
        if isinstance(self.shape, ShapeCastable):
            return self.shape(row)
        else:
            return row


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
                assert self._en.shape() == unsigned(1)
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


    def __init__(self, *, data, attrs=None, src_loc=None):
        super().__init__(src_loc=src_loc)
        assert isinstance(data, MemoryData)
        data.freeze()
        self._data = data
        self._attrs = attrs or {}
        self._read_ports: "list[MemoryInstance._ReadPort]" = []
        self._write_ports: "list[MemoryInstance._WritePort]" = []

    def read_port(self, *, domain, addr, data, en, transparent_for):
        port = self._ReadPort(domain=domain, addr=addr, data=data, en=en, transparent_for=transparent_for)
        shape = Shape.cast(self._data.shape)
        assert len(port._data) == shape.width
        assert len(port._addr) == ceil_log2(self._data.depth)
        for idx in port._transparent_for:
            assert isinstance(idx, int)
            assert idx in range(len(self._write_ports))
            assert self._write_ports[idx]._domain == port._domain
        self._read_ports.append(port)

    def write_port(self, *, domain, addr, data, en):
        port = self._WritePort(domain=domain, addr=addr, data=data, en=en)
        shape = Shape.cast(self._data.shape)
        assert len(port._data) == shape.width
        assert len(port._addr) == ceil_log2(self._data.depth)
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

        self._read_ports = []
        self._write_ports = []
        self._data = MemoryData(shape=width, depth=depth, init=init or [])

    @property
    def init(self):
        return self._data.init

    @init.setter
    def init(self, new_init):
        self._data.init = new_init

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
        return self._data[index]

    def elaborate(self, platform):
        f = MemoryInstance(data=self._data, attrs=self.attrs, src_loc=self.src_loc)
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
    @deprecated("`DummyPort` is deprecated, use `amaranth.lib.memory.ReadPort` or "
                "`amaranth.lib.memory.WritePort` instead")
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
