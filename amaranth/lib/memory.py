import operator
from collections import OrderedDict
from collections.abc import MutableSequence

from ..hdl import MemoryIdentity, MemoryInstance, Shape, ShapeCastable, Const
from ..hdl._mem import MemorySimRead
from ..utils import ceil_log2
from .data import ArrayLayout
from . import wiring
from .. import tracer


__all__ = ["WritePort", "ReadPort", "Memory"]


class WritePort:
    """A memory write port.

    Parameters
    ----------
    signature : :class:`WritePort.Signature`
        The signature of the port.
    memory : :class:`Memory` or ``None``
        Memory associated with the port.
    domain : str
        Clock domain. Defaults to ``"sync"``. Writes have a latency of 1 clock cycle.

    Attributes
    ----------
    signature : :class:`WritePort.Signature`
    memory : :class:`Memory`
    domain : str
    """

    class Signature(wiring.Signature):
        """A signature of a write port.

        Parameters
        ----------
        addr_width : int
            Address width in bits. If the port is associated with a :class:`Memory`,
            it must be equal to :py:`ceil_log2(memory.depth)`.
        shape : :ref:`shape-like <lang-shapelike>` object
            The shape of the port data. If the port is associated with a :class:`Memory`,
            it must be equal to its element shape.
        granularity : int or ``None``
            Port granularity. If ``None``, the entire storage element is written at once.
            Otherwise, determines the size of access covered by a single bit of ``en``.
            One of the following must hold:

            - ``granularity is None``, in which case ``en_width == 1``, or
            - ``shape == unsigned(data_width)`` and ``data_width == 0 or data_width % granularity == 0`` in which case ``en_width == data_width // granularity`` (or 0 if ``data_width == 0``)
            - ``shape == amaranth.lib.data.ArrayLayout(_, elem_count)`` and ``elem_count == 0 or elem_count % granularity == 0`` in which case ``en_width == elem_count // granularity`` (or 0 if ``elem_count == 0``)

        Members
        -------
        addr: :py:`unsigned(data_width)`
        data: ``shape``
        en: :py:`unsigned(en_width)`
        """

        def __init__(self, *, addr_width, shape, granularity=None):
            if not isinstance(addr_width, int) or addr_width < 0:
                raise TypeError(f"`addr_width` must be a non-negative int, not {addr_width!r}")
            self._addr_width = addr_width
            self._shape = shape
            self._granularity = granularity
            if granularity is None:
                en_width = 1
            elif not isinstance(granularity, int) or granularity < 0:
                raise TypeError(f"Granularity must be a non-negative int or None, not {granularity!r}")
            elif not isinstance(shape, ShapeCastable):
                actual_shape = Shape.cast(shape)
                if actual_shape.signed:
                    raise ValueError("Granularity cannot be specified with signed shape")
                elif actual_shape.width == 0:
                    en_width = 0
                elif granularity == 0:
                    raise ValueError("Granularity must be positive")
                elif actual_shape.width % granularity != 0:
                    raise ValueError("Granularity must divide data width")
                else:
                    en_width = actual_shape.width // granularity
            elif isinstance(shape, ArrayLayout):
                if shape.length == 0:
                    en_width = 0
                elif granularity == 0:
                    raise ValueError("Granularity must be positive")
                elif shape.length % granularity != 0:
                    raise ValueError("Granularity must divide data array length")
                else:
                    en_width = shape.length // granularity
            else:
                raise TypeError("Granularity can only be specified for plain unsigned `Shape` or `ArrayLayout`")
            super().__init__({
                "addr": wiring.In(addr_width),
                "data": wiring.In(shape),
                "en": wiring.In(en_width),
            })

        @property
        def addr_width(self):
            return self._addr_width

        @property
        def shape(self):
            return self._shape

        @property
        def granularity(self):
            return self._granularity

        def __repr__(self):
            granularity = f", granularity={self.granularity}" if self.granularity is not None else ""
            return f"WritePort.Signature(addr_width={self.addr_width}, shape={self.shape}{granularity})"


    def __init__(self, signature, *, memory, domain):
        if not isinstance(signature, WritePort.Signature):
            raise TypeError(f"Expected `WritePort.Signature`, not {signature!r}")
        if memory is not None:
            if not isinstance(memory, Memory):
                raise TypeError(f"Expected `Memory` or `None`, not {memory!r}")
            if signature.shape != memory.shape or Shape.cast(signature.shape) != Shape.cast(memory.shape):
                raise ValueError(f"Memory shape {memory.shape!r} doesn't match port shape {signature.shape!r}")
            if signature.addr_width != ceil_log2(memory.depth):
                raise ValueError(f"Memory address width {ceil_log2(memory.depth)!r} doesn't match port address width {signature.addr_width!r}")
        if not isinstance(domain, str):
            raise TypeError(f"Domain has to be a string, not {domain!r}")
        if domain == "comb":
            raise ValueError("Write port domain cannot be \"comb\"")
        self._signature = signature
        self._memory = memory
        self._domain = domain
        self.__dict__.update(signature.members.create())
        if memory is not None:
            memory._w_ports.append(self)

    @property
    def signature(self):
        return self._signature
    
    @property
    def memory(self):
        return self._memory
    
    @property
    def domain(self):
        return self._domain


class ReadPort:
    """A memory read port.

    Parameters
    ----------
    signature : :class:`ReadPort.Signature`
        The signature of the port.
    memory : :class:`Memory`
        Memory associated with the port.
    domain : str
        Clock domain. Defaults to ``"sync"``. If set to ``"comb"``, the port is asynchronous.
        Otherwise, the read data becomes available on the next clock cycle.
    transparent_for : iterable of :class:`WritePort`
        The set of write ports that this read port should be transparent with. All ports
        must belong to the same memory and the same clock domain.

    Attributes
    ----------
    signature : :class:`ReadPort.Signature`
    memory : :class:`Memory`
    domain : str
    transparent_for : tuple of :class:`WritePort`
    """

    class Signature(wiring.Signature):
        """A signature of a read port.

        Parameters
        ----------
        addr_width : int
            Address width in bits. If the port is associated with a :class:`Memory`,
            it must be equal to :py:`ceil_log2(memory.depth)`.
        shape : :ref:`shape-like <lang-shapelike>` object
            The shape of the port data. If the port is associated with a :class:`Memory`,
            it must be equal to its element shape.

        Members
        -------
        addr: :py:`unsigned(data_width)`
        data: ``shape``
        en: :py:`unsigned(1)`
            The enable signal. If ``domain == "comb"``, this is tied to ``Const(1)``.
            Otherwise it is a signal with ``init=1``.
        """

        def __init__(self, *, addr_width, shape):
            if not isinstance(addr_width, int) or addr_width < 0:
                raise TypeError(f"`addr_width` must be a non-negative int, not {addr_width!r}")
            self._addr_width = addr_width
            self._shape = shape
            super().__init__({
                "addr": wiring.In(addr_width),
                "data": wiring.Out(shape),
                "en": wiring.In(1, init=1),
            })

        @property
        def addr_width(self):
            return self._addr_width

        @property
        def shape(self):
            return self._shape

        def __repr__(self):
            return f"ReadPort.Signature(addr_width={self.addr_width}, shape={self.shape})"


    def __init__(self, signature, *, memory, domain, transparent_for=()):
        if not isinstance(signature, ReadPort.Signature):
            raise TypeError(f"Expected `ReadPort.Signature`, not {signature!r}")
        if memory is not None:
            if not isinstance(memory, Memory):
                raise TypeError(f"Expected `Memory` or `None`, not {memory!r}")
            if signature.shape != memory.shape or Shape.cast(signature.shape) != Shape.cast(memory.shape):
                raise ValueError(f"Memory shape {memory.shape!r} doesn't match port shape {signature.shape!r}")
            if signature.addr_width != ceil_log2(memory.depth):
                raise ValueError(f"Memory address width {ceil_log2(memory.depth)!r} doesn't match port address width {signature.addr_width!r}")
        if not isinstance(domain, str):
            raise TypeError(f"Domain has to be a string, not {domain!r}")
        transparent_for = tuple(transparent_for)
        for port in transparent_for:
            if not isinstance(port, WritePort):
                raise TypeError("`transparent_for` must contain only `WritePort` instances")
            if memory is not None and port not in memory._w_ports:
                raise ValueError("Transparent write ports must belong to the same memory")
            if port.domain != domain:
                raise ValueError("Transparent write ports must belong to the same domain")
        self._signature = signature
        self._memory = memory
        self._domain = domain
        self._transparent_for = transparent_for
        self.__dict__.update(signature.members.create())
        if domain == "comb":
            self.en = Const(1)
        if memory is not None:
            memory._r_ports.append(self)

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


class Memory(wiring.Component):
    """A word addressable storage.

    Parameters
    ----------
    shape : :ref:`shape-like <lang-shapelike>` object
        The shape of a single element of the storage.
    depth : int
        Word count. This memory contains ``depth`` storage elements.
    init : iterable of int or of any objects accepted by ``shape.const()``
        Initial values. At power on, each storage element in this memory is initialized to
        the corresponding element of ``init``, if any, or to the default value of ``shape`` otherwise.
        Uninitialized memories are not currently supported.
    attrs : dict
        Dictionary of synthesis attributes.

    Attributes
    ----------
    shape : :ref:`shape-like <lang-shapelike>`
    depth : int
    init : :class:`Memory.Init`
    attrs : dict
    r_ports : tuple of :class:`ReadPort`
    w_ports : tuple of :class:`WritePort`
    """

    class Init(MutableSequence):
        """Initial data of a :class:`Memory`.

        This is a container implementing the ``MutableSequence`` protocol, enforcing two constraints:

        - the length is immutable and must equal ``depth``
        - if ``shape`` is a :class:`ShapeCastable`, each element can be cast to ``shape`` via :py:`shape.const()`
        - otherwise, each element is an :py:`int`
        """
        def __init__(self, items, *, shape, depth):
            Shape.cast(shape)
            if not isinstance(depth, int) or depth < 0:
                raise TypeError("Memory depth must be a non-negative integer, not {!r}"
                                .format(depth))
            self._shape = shape
            self._depth = depth
            if isinstance(shape, ShapeCastable):
                self._items = [None] * depth
                default = Const.cast(shape.const(None)).value
                self._raw = [default] * depth
            else:
                self._raw = self._items = [0] * depth
            try:
                for idx, item in enumerate(items):
                    self[idx] = item
            except (TypeError, ValueError) as e:
                raise type(e)("Memory initialization value at address {:x}: {}"
                                .format(idx, e)) from None
        
        def __getitem__(self, index):
            return self._items[index]

        def __setitem__(self, index, value):
            if isinstance(index, slice):
                start, stop, step = index.indices(len(self._items))
                indices = range(start, stop, step)
                if len(value) != len(indices):
                    raise ValueError("Changing length of Memory.init is not allowed")
                for actual_index, actual_value in zip(indices, value):
                    self[actual_index] = actual_value
            else:
                if isinstance(self._shape, ShapeCastable):
                    self._raw[index] = Const.cast(self._shape.const(value)).value
                else:
                    value = operator.index(value)
                self._items[index] = value

        def __delitem__(self, index):
            raise TypeError("Deleting items from Memory.init is not allowed")
        
        def insert(self, index, value):
            raise TypeError("Inserting items into Memory.init is not allowed")
        
        def __len__(self):
            return self._depth

        @property
        def depth(self):
            return self._depth

        @property
        def shape(self):
            return self._shape
        
        def __repr__(self):
            return f"Memory.Init({self._items!r})"

    def __init__(self, *, depth, shape, init, attrs=None, src_loc_at=0, src_loc=None):
        # shape and depth validation performed in Memory.Init constructor.
        self._depth = depth
        self._shape = shape
        self._init = Memory.Init(init, shape=shape, depth=depth)
        self._attrs = {} if attrs is None else dict(attrs)
        self.src_loc = src_loc or tracer.get_src_loc(src_loc_at=src_loc_at)
        self._identity = MemoryIdentity()
        self._r_ports: "list[ReadPort]" = []
        self._w_ports: "list[WritePort]" = []
        super().__init__(wiring.Signature({}))

    def read_port(self, *, domain="sync", transparent_for=()):
        """Adds a new read port and returns it.

        Equivalent to creating a :class:`ReadPort` with a signature of :py:`ReadPort.Signature(addr_width=ceil_log2(self.depth), shape=self.shape)`
        """
        signature = ReadPort.Signature(addr_width=ceil_log2(self.depth), shape=self.shape)
        return ReadPort(signature, memory=self, domain=domain, transparent_for=transparent_for)

    def write_port(self, *, domain="sync", granularity=None):
        """Adds a new write port and returns it.

        Equivalent to creating a :class:`WritePort` with a signature of :py:`WritePort.Signature(addr_width=ceil_log2(self.depth), shape=self.shape, granularity=granularity)`
        """
        signature = WritePort.Signature(addr_width=ceil_log2(self.depth), shape=self.shape, granularity=granularity)
        return WritePort(signature, memory=self, domain=domain)

    @property
    def depth(self):
        return self._depth

    @property
    def shape(self):
        return self._shape

    @property
    def init(self):
        return self._init

    @property
    def attrs(self):
        return self._attrs

    @property
    def w_ports(self):
        """Returns a tuple of all write ports defined so far."""
        return tuple(self._w_ports)

    @property
    def r_ports(self):
        """Returns a tuple of all read ports defined so far."""
        return tuple(self._r_ports)

    def elaborate(self, platform):
        if hasattr(platform, "get_memory"):
            return platform.get_memory(self)
        shape = Shape.cast(self.shape)
        instance = MemoryInstance(identity=self._identity, width=shape.width, depth=self.depth, init=self.init._raw, attrs=self.attrs, src_loc=self.src_loc)
        w_ports = {}
        for port in self._w_ports:
            idx = instance.write_port(domain=port.domain, addr=port.addr, data=port.data, en=port.en)
            w_ports[port] = idx
        for port in self._r_ports:
            transparent_for = [w_ports[write_port] for write_port in port.transparent_for]
            instance.read_port(domain=port.domain, data=port.data, addr=port.addr, en=port.en, transparent_for=transparent_for)
        return instance

    def __getitem__(self, index):
        """Simulation only."""
        return MemorySimRead(self._identity, index)
