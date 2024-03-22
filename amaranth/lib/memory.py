import operator
from collections import OrderedDict
from collections.abc import MutableSequence

from ..hdl import MemoryIdentity, MemoryInstance, Shape, ShapeCastable, Const
from ..hdl._mem import MemorySimRead
from ..utils import ceil_log2
from .. import tracer
from . import wiring, data


__all__ = ["Memory", "ReadPort", "WritePort"]


class Memory(wiring.Component):
    """Addressable array of rows.

    This :ref:`component <wiring>` is used to construct a memory array by first specifying its
    dimensions and initial contents using the :py:`shape`, :py:`depth`, and :py:`init` parameters,
    and then adding memory ports using the :meth:`read_port` and :meth:`write_port` methods.
    Because it is mutable, it should be created and used locally within
    the :ref:`elaborate <lang-elaboration>` method.

    The :py:`init` parameter and assignment to the :py:`init` attribute have the same effect, with
    :class:`Memory.Init` converting elements of the iterable to match :py:`shape` and using
    a default value for rows that are not explicitly initialized.

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

    Platform overrides
    ------------------
    Define the :py:`get_memory()` platform method to override the implementation of
    :class:`Memory`, e.g. to instantiate library cells directly.
    """

    class Init(MutableSequence):
        """Memory initialization data.

        This is a special container used only for the :attr:`Memory.init` attribute. It is similar
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

            if isinstance(shape, ShapeCastable):
                self._elems = [None] * depth
                self._raw = [Const.cast(shape.const(None)).value] * depth
            else:
                self._elems = [0] * depth
                self._raw = self._elems # intentionally mutably aliased
            try:
                for index, item in enumerate(elems):
                    self[index] = item
            except (TypeError, ValueError) as e:
                raise type(e)("Memory initialization value at address {:x}: {}"
                              .format(index, e)) from None

        @property
        def shape(self):
            return self._shape

        def __getitem__(self, index):
            return self._elems[index]

        def __setitem__(self, index, value):
            if isinstance(index, slice):
                indices = range(*index.indices(len(self._elems)))
                if len(value) != len(indices):
                    raise ValueError("Changing length of Memory.init is not allowed")
                for actual_index, actual_value in zip(indices, value):
                    self[actual_index] = actual_value
            else:
                if isinstance(self._shape, ShapeCastable):
                    self._raw[index] = Const.cast(self._shape.const(value)).value
                else:
                    value = operator.index(value)
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
            return f"Memory.Init({self._elems!r}, shape={self._shape!r}, depth={self._depth})"


    def __init__(self, *, shape, depth, init, attrs=None, src_loc_at=0):
        # shape and depth validation is performed in Memory.Init()
        self._shape = shape
        self._depth = depth
        self._init = Memory.Init(init, shape=shape, depth=depth)
        self._attrs = {} if attrs is None else dict(attrs)
        self.src_loc = tracer.get_src_loc(src_loc_at=src_loc_at)

        self._identity = MemoryIdentity()
        self._read_ports: "list[ReadPort]" = []
        self._write_ports: "list[WritePort]" = []

        super().__init__(wiring.Signature({}))

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
        self._init = Memory.Init(init, shape=self._shape, depth=self._depth)

    @property
    def attrs(self):
        return self._attrs

    def read_port(self, *, domain="sync", transparent_for=(), src_loc_at=0):
        """Request a read port.

        If :py:`domain` is :py:`"comb"`, the created read port is asynchronous and always enabled
        (with its enable input is tied to :py:`Const(1)`), and its data output always reflects
        the contents of the selected row. Otherwise, the created read port is synchronous,
        and its data output is updated with the contents of the selected row at each
        :ref:`active edge <lang-sync>` of :py:`domain` where the enable input is asserted.

        The :py:`transparent_for` parameter specifies the *transparency set* of this port: zero or
        more :class:`WritePort`\\ s, all of which must belong to the same memory and clock domain.
        If another port writes to a memory row at the same time as this port reads from the same
        memory row, and that write port is a part of the transparency set, then this port retrieves
        the new contents of the row; otherwise, this port retrieves the old contents of the row.

        If another write port belonging to a different clock domain updates a memory row that this
        port is reading at the same time, the behavior is undefined.

        The signature of the returned port is
        :py:`ReadPort.Signature(shape=self.shape, addr_width=ceil_log2(self.depth))`.

        Returns
        -------
        :class:`ReadPort`
        """
        signature = ReadPort.Signature(shape=self.shape, addr_width=ceil_log2(self.depth))
        return ReadPort(signature, memory=self, domain=domain, transparent_for=transparent_for,
                        src_loc_at=1 + src_loc_at)

    def write_port(self, *, domain="sync", granularity=None, src_loc_at=0):
        """Request a write port.

        The created write port is synchronous, updating the contents of the selected row at each
        :ref:`active edge <lang-sync>` of :py:`domain` where the enable input is asserted.

        Specifying a *granularity* when :py:`shape` is :func:`unsigned(width) <.unsigned>` or
        :class:`data.ArrayLayout(_, width) <.data.ArrayLayout>` makes it possible to partially
        update a memory row. In this case, :py:`granularity` must be an integer that evenly divides
        :py:`width`, and the memory row is split into :py:`width // granularity` equally sized
        parts, each of which is updated if the corresponding bit of the enable input is asserted.

        The signature of the new port is
        :py:`WritePort.Signature(shape=self.shape, addr_width=ceil_log2(self.depth), granularity=granularity)`.

        Returns
        -------
        :class:`WritePort`
        """
        signature = WritePort.Signature(
            shape=self.shape, addr_width=ceil_log2(self.depth), granularity=granularity)
        return WritePort(signature, memory=self, domain=domain,
                         src_loc_at=1 + src_loc_at)

    @property
    def read_ports(self):
        """All read ports defined so far.

        This property is provided for the :py:`platform.get_memory()` override.
        """
        return tuple(self._read_ports)

    @property
    def write_ports(self):
        """All write ports defined so far.

        This property is provided for the :py:`platform.get_memory()` override.
        """
        return tuple(self._write_ports)

    def elaborate(self, platform):
        if hasattr(platform, "get_memory"):
            return platform.get_memory(self)

        shape = Shape.cast(self.shape)
        instance = MemoryInstance(identity=self._identity, width=shape.width, depth=self.depth,
                                  init=self.init._raw, attrs=self.attrs, src_loc=self.src_loc)
        write_ports = {}
        for port in self._write_ports:
            write_ports[port] = instance.write_port(
                domain=port.domain, addr=port.addr, data=port.data, en=port.en)
        for port in self._read_ports:
            transparent_for = tuple(write_ports[write_port] for write_port in port.transparent_for)
            instance.read_port(
                domain=port.domain, data=port.data, addr=port.addr, en=port.en,
                transparent_for=transparent_for)
        return instance

    def __getitem__(self, index):
        """Simulation only."""
        return MemorySimRead(self._identity, index)


class ReadPort:
    """A read memory port.

    Memory read ports, which are :ref:`interface objects <wiring>`, can be constructed by calling
    :meth:`Memory.read_port` or via :meth:`ReadPort.Signature.create() <.Signature.create>`.

    An asynchronous (:py:`"comb"` domain) memory read port is always enabled. The :py:`en` input of
    such a port is tied to :py:`Const(1)`.

    Attributes
    ----------
    signature : :class:`ReadPort.Signature`
        Signature of this memory port.
    memory : :class:`Memory` or :py:`None`
        Memory associated with this memory port.
    domain : :class:`str`
        Name of this memory port's clock domain. For asynchronous ports, :py:`"comb"`.
    transparent_for : :class:`tuple` of :class:`WritePort`
        Transparency set of this memory port.
    """

    class Signature(wiring.Signature):
        """Signature of a memory read port.

        Parameters
        ----------
        addr_width : :class:`int`
            Width of the address port.
        shape : :ref:`shape-like <lang-shapelike>` object
            Shape of the data port.

        Members
        -------
        en: :py:`In(1, init=1)`
            Enable input.
        addr: :py:`In(addr_width)`
            Address input.
        data: :py:`Out(shape)`
            Data output.
        """

        def __init__(self, *, addr_width, shape):
            if not isinstance(addr_width, int) or addr_width < 0:
                raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
            self._addr_width = addr_width
            self._shape = shape
            super().__init__({
                "en": wiring.In(1, init=1),
                "addr": wiring.In(addr_width),
                "data": wiring.Out(shape),
            })

        def create(self, *, path=None, src_loc_at=0):
            """:meta private:""" # work around Sphinx bug
            return ReadPort(self, memory=None, domain="sync", path=path, src_loc_at=1 + src_loc_at)

        @property
        def addr_width(self):
            return self._addr_width

        @property
        def shape(self):
            return self._shape

        def __eq__(self, other):
            return (type(self) is type(other) and
                    self.addr_width == other.addr_width and
                    self.shape == other.shape)

        def __repr__(self):
            return f"ReadPort.Signature(addr_width={self.addr_width}, shape={self.shape})"


    def __init__(self, signature, *, memory, domain, transparent_for=(), path=None, src_loc_at=0):
        if not isinstance(signature, ReadPort.Signature):
            raise TypeError(f"Expected signature to be ReadPort.Signature, not {signature!r}")
        if memory is not None: # may be None if created via `Signature.create()`
            if not isinstance(memory, Memory):
                raise TypeError(f"Expected memory to be Memory or None, not {memory!r}")
            if (signature.shape != memory.shape or
                    Shape.cast(signature.shape) != Shape.cast(memory.shape)):
                raise ValueError(f"Memory shape {memory.shape!r} doesn't match "
                                 f"port shape {signature.shape!r}")
            if signature.addr_width != ceil_log2(memory.depth):
                raise ValueError(f"Memory address width {ceil_log2(memory.depth)!r} doesn't match "
                                 f"port address width {signature.addr_width!r}")
        if not isinstance(domain, str):
            raise TypeError(f"Domain must be a string, not {domain!r}")
        transparent_for = tuple(transparent_for)
        for port in transparent_for:
            if not isinstance(port, WritePort):
                raise TypeError("Transparency set must contain only WritePort instances")
            if memory is not None and port not in memory._write_ports:
                raise ValueError("Ports in transparency set must belong to the same memory")
            if port.domain != domain:
                raise ValueError("Ports in transparency set must belong to the same domain")
        self._signature = signature
        self._memory = memory
        self._domain = domain
        self._transparent_for = transparent_for
        self.__dict__.update(signature.members.create(path=path, src_loc_at=1 + src_loc_at))
        if domain == "comb":
            self.en = Const(1)
        if memory is not None:
            memory._read_ports.append(self)

    @property
    def signature(self):
        return self._signature

    @property
    def memory(self):
        return self._memory

    @property
    def domain(self):
        return self._domain

    @property
    def transparent_for(self):
        return self._transparent_for


class WritePort:
    """A write memory port.

    Memory write ports, which are :ref:`interface objects <wiring>`, can be constructed by calling
    :meth:`Memory.write_port` or via :meth:`WritePort.Signature.create() <.Signature.create>`.

    Attributes
    ----------
    signature : :class:`WritePort.Signature`
        Signature of this memory port.
    memory : :class:`Memory` or :py:`None`
        Memory associated with this memory port.
    domain : :class:`str`
        Name of this memory port's clock domain. Never :py:`"comb"`.
    """

    class Signature(wiring.Signature):
        """Signature of a memory write port.

        Width of the enable input is determined as follows:

        * If :py:`granularity` is :py:`None`,
          then :py:`en_width == 1`.
        * If :py:`shape` is :func:`unsigned(data_width) <.unsigned>`,
          then :py:`en_width == data_width // granularity`.
        * If :py:`shape` is :class:`data.ArrayLayout(_, elem_count) <.data.ArrayLayout>`,
          then :py:`en_width == elem_count // granularity`.

        Parameters
        ----------
        addr_width : :class:`int`
            Width of the address port.
        shape : :ref:`shape-like <lang-shapelike>` object
            Shape of the data port.
        granularity : :class:`int` or :py:`None`
            Granularity of memory access.

        Members
        -------
        en: :py:`In(en_width)`
            Enable input.
        addr: :py:`In(addr_width)`
            Address input.
        data: :py:`In(shape)`
            Data input.
        """

        def __init__(self, *, addr_width, shape, granularity=None):
            if not isinstance(addr_width, int) or addr_width < 0:
                raise TypeError(f"Address width must be a non-negative integer, not {addr_width!r}")
            self._addr_width = addr_width
            self._shape = shape
            self._granularity = granularity
            if granularity is None:
                en_width = 1
            elif not isinstance(granularity, int) or granularity < 0:
                raise TypeError(f"Granularity must be a non-negative integer or None, "
                                f"not {granularity!r}")
            elif not isinstance(shape, ShapeCastable):
                actual_shape = Shape.cast(shape)
                if actual_shape.signed:
                    raise ValueError("Granularity cannot be specified for a memory with "
                                     "a signed shape")
                elif actual_shape.width == 0:
                    en_width = 0
                elif granularity == 0:
                    raise ValueError("Granularity must be positive")
                elif actual_shape.width % granularity != 0:
                    raise ValueError("Granularity must evenly divide data width")
                else:
                    en_width = actual_shape.width // granularity
            elif isinstance(shape, data.ArrayLayout):
                if shape.length == 0:
                    en_width = 0
                elif granularity == 0:
                    raise ValueError("Granularity must be positive")
                elif shape.length % granularity != 0:
                    raise ValueError("Granularity must evenly divide data array length")
                else:
                    en_width = shape.length // granularity
            else:
                raise TypeError("Granularity can only be specified for memories whose shape "
                                "is unsigned or data.ArrayLayout")
            super().__init__({
                "en": wiring.In(en_width),
                "addr": wiring.In(addr_width),
                "data": wiring.In(shape),
            })

        def create(self, *, path=None, src_loc_at=0):
            """:meta private:""" # work around Sphinx bug
            return WritePort(self, memory=None, domain="sync", path=path, src_loc_at=1 + src_loc_at)

        @property
        def addr_width(self):
            return self._addr_width

        @property
        def shape(self):
            return self._shape

        @property
        def granularity(self):
            return self._granularity

        def __eq__(self, other):
            return (type(self) is type(other) and
                    self.addr_width == other.addr_width and
                    self.shape == other.shape and
                    self.granularity == other.granularity)

        def __repr__(self):
            granularity = f", granularity={self.granularity}" if self.granularity is not None else ""
            return f"WritePort.Signature(addr_width={self.addr_width}, shape={self.shape}{granularity})"


    def __init__(self, signature, *, memory, domain, path=None, src_loc_at=0):
        if not isinstance(signature, WritePort.Signature):
            raise TypeError(f"Expected signature to be WritePort.Signature, not {signature!r}")
        if memory is not None: # may be None if created via `Signature.create()`
            if not isinstance(memory, Memory):
                raise TypeError(f"Expected memory to be Memory or None, not {memory!r}")
            if (signature.shape != memory.shape or
                    Shape.cast(signature.shape) != Shape.cast(memory.shape)):
                raise ValueError(f"Memory shape {memory.shape!r} doesn't match "
                                 f"port shape {signature.shape!r}")
            if signature.addr_width != ceil_log2(memory.depth):
                raise ValueError(f"Memory address width {ceil_log2(memory.depth)!r} doesn't match "
                                 f"port address width {signature.addr_width!r}")
        if not isinstance(domain, str):
            raise TypeError(f"Domain must be a string, not {domain!r}")
        if domain == "comb":
            raise ValueError("Write ports cannot be asynchronous")
        self._signature = signature
        self._memory = memory
        self._domain = domain
        self.__dict__.update(signature.members.create(path=path, src_loc_at=1 + src_loc_at))
        if memory is not None:
            memory._write_ports.append(self)

    @property
    def signature(self):
        return self._signature

    @property
    def memory(self):
        return self._memory

    @property
    def domain(self):
        return self._domain
