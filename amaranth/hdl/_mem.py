import operator
from collections.abc import MutableSequence

from .. import tracer
from ._ast import *
from ._ast import _get_init_value
from ._ir import Fragment, AlreadyElaborated
from ..utils import ceil_log2
from .._utils import final


__all__ = ["MemoryData", "MemoryInstance"]


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
