import enum
import operator
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable

from ..hdl import *
from ..lib import wiring, data
from ..lib.wiring import In, Out
from .._utils import deprecated, _ignore_deprecated
from .. import tracer


__all__ = [
    "Direction", "PortLike", "SingleEndedPort", "DifferentialPort", "SimulationPort",
    "Buffer", "FFBuffer", "DDRBuffer",
    "Pin",
]


class Direction(enum.Enum):
    """Represents direction of a library I/O port, or of an I/O buffer component."""

    #: Input direction (from outside world to Amaranth design).
    Input  = "i"
    #: Output direction (from Amaranth design to outside world).
    Output = "o"
    #: Bidirectional (can be switched between input and output).
    Bidir  = "io"

    def __and__(self, other):
        """Narrow the set of possible directions.

        * :py:`self & self` returns :py:`self`.
        * :py:`Bidir & other` returns :py:`other`.
        * :py:`Input & Output` raises :exc:`ValueError`.
        """
        if not isinstance(other, Direction):
            return NotImplemented
        if self == other:
            return self
        elif self is Direction.Bidir:
            return other
        elif other is Direction.Bidir:
            return self
        else:
            raise ValueError("Cannot combine input port with output port")


class PortLike(metaclass=ABCMeta):
    """Represents an abstract library I/O port that can be passed to a buffer.

    The port types supported by most platforms are :class:`SingleEndedPort` and
    :class:`DifferentialPort`. Platforms may define additional port types where appropriate.

    .. note::

        :class:`amaranth.hdl.IOPort` is not an instance of :class:`amaranth.lib.io.PortLike`.
    """

    # TODO(amaranth-0.6): remove
    def __init_subclass__(cls):
        if cls.__add__ is PortLike.__add__:
            warnings.warn(f"{cls.__module__}.{cls.__qualname__} must override the `__add__` method",
                          DeprecationWarning, stacklevel=2)

    @property
    @abstractmethod
    def direction(self):
        """Direction of the port.

        Returns
        -------
        :class:`Direction`
        """
        raise NotImplementedError # :nocov:

    @abstractmethod
    def __len__(self):
        """Computes the width of the port.

        Returns
        -------
        :class:`int`
            The number of wires (for single-ended library I/O ports) or wire pairs (for differential
            library I/O ports) this port consists of.
        """
        raise NotImplementedError # :nocov:

    @abstractmethod
    def __getitem__(self, key):
        """Slices the port.

        Returns
        -------
        :class:`PortLike`
            A new :class:`PortLike` instance of the same type as :py:`self`, containing a selection
            of wires of this port according to :py:`key`. Its width is the same as the length of
            the slice (if :py:`key` is a :class:`slice`); or 1 (if :py:`key` is an :class:`int`).
        """
        raise NotImplementedError # :nocov:

    @abstractmethod
    def __invert__(self):
        """Inverts polarity of the port.

        Inverting polarity of a library I/O port has the same effect as adding inverters to
        the :py:`i` and :py:`o` members of an I/O buffer component for that port.

        Returns
        -------
        :class:`PortLike`
            A new :class:`PortLike` instance of the same type as :py:`self`, containing the same
            wires as this port, but with polarity inverted.
        """
        raise NotImplementedError # :nocov:

    # TODO(amaranth-0.6): make abstract
    # @abstractmethod
    def __add__(self, other):
        """Concatenates two library I/O ports of the same type.

        The direction of the resulting port is:

        * The same as the direction of both, if the two ports have the same direction.
        * :attr:`Direction.Input` if a bidirectional port is concatenated with an input port.
        * :attr:`Direction.Output` if a bidirectional port is concatenated with an output port.

        Returns
        -------
        :py:`type(self)`
            A new :py:`type(self)` which contains wires from :py:`self` followed by wires
            from :py:`other`, preserving their polarity inversion.

        Raises
        ------
        :exc:`ValueError`
            If an input port is concatenated with an output port.
        :exc:`TypeError`
            If :py:`self` and :py:`other` have different types.
        """
        raise NotImplementedError # :nocov:


class SingleEndedPort(PortLike):
    """Represents a single-ended library I/O port.

    Implements the :class:`PortLike` interface.

    Parameters
    ----------
    io : :class:`IOValue`
        Underlying core I/O value.
    invert : :class:`bool` or iterable of :class:`bool`
        Polarity inversion. If the value is a simple :class:`bool`, it specifies inversion for
        the entire port. If the value is an iterable of :class:`bool`, the iterable must have the
        same length as the width of :py:`io`, and the inversion is specified for individual wires.
    direction : :class:`Direction` or :class:`str`
        Set of allowed buffer directions. A string is converted to a :class:`Direction` first.
        If equal to :attr:`~Direction.Input` or :attr:`~Direction.Output`, this port can only be
        used with buffers of matching direction. If equal to :attr:`~Direction.Bidir`, this port
        can be used with buffers of any direction.

    Attributes
    ----------
    io : :class:`IOValue`
        The :py:`io` parameter.
    invert : :class:`tuple` of :class:`bool`
        The :py:`invert` parameter, normalized to specify polarity inversion per-wire.
    direction : :class:`Direction`
        The :py:`direction` parameter, normalized to the :class:`Direction` enumeration.
    """
    def __init__(self, io, *, invert=False, direction=Direction.Bidir):
        self._io = IOValue.cast(io)
        if isinstance(invert, bool):
            self._invert = (invert,) * len(self._io)
        elif isinstance(invert, Iterable):
            self._invert = tuple(invert)
            if len(self._invert) != len(self._io):
                raise ValueError(f"Length of 'invert' ({len(self._invert)}) doesn't match "
                                 f"length of 'io' ({len(self._io)})")
            if not all(isinstance(item, bool) for item in self._invert):
                raise TypeError(f"'invert' must be a bool or iterable of bool, not {invert!r}")
        else:
            raise TypeError(f"'invert' must be a bool or iterable of bool, not {invert!r}")
        self._direction = Direction(direction)

    @property
    def io(self):
        return self._io

    @property
    def invert(self):
        return self._invert

    @property
    def direction(self):
        return self._direction

    def __len__(self):
        return len(self._io)

    def __invert__(self):
        return SingleEndedPort(self._io, invert=tuple(not inv for inv in self._invert),
                               direction=self._direction)

    def __getitem__(self, index):
        return SingleEndedPort(self._io[index], invert=self._invert[index],
                               direction=self._direction)

    def __add__(self, other):
        if not isinstance(other, SingleEndedPort):
            return NotImplemented
        return SingleEndedPort(Cat(self._io, other._io), invert=self._invert + other._invert,
                               direction=self._direction & other._direction)

    def __repr__(self):
        if all(self._invert):
            invert = True
        elif not any(self._invert):
            invert = False
        else:
            invert = self._invert
        return f"SingleEndedPort({self._io!r}, invert={invert!r}, direction={self._direction})"


class DifferentialPort(PortLike):
    """Represents a differential library I/O port.

    Implements the :class:`PortLike` interface.

    Parameters
    ----------
    p : :class:`IOValue`
        Underlying core I/O value for the true (positive) half of the port.
    n : :class:`IOValue`
        Underlying core I/O value for the complement (negative) half of the port.
        Must have the same width as :py:`p`.
    invert : :class:`bool` or iterable of :class:`bool`
        Polarity inversion. If the value is a simple :class:`bool`, it specifies inversion for
        the entire port. If the value is an iterable of :class:`bool`, the iterable must have the
        same length as the width of :py:`p` and :py:`n`, and the inversion is specified for
        individual wires.
    direction : :class:`Direction` or :class:`str`
        Set of allowed buffer directions. A string is converted to a :class:`Direction` first.
        If equal to :attr:`~Direction.Input` or :attr:`~Direction.Output`, this port can only be
        used with buffers of matching direction. If equal to :attr:`~Direction.Bidir`, this port
        can be used with buffers of any direction.

    Attributes
    ----------
    p : :class:`IOValue`
        The :py:`p` parameter.
    n : :class:`IOValue`
        The :py:`n` parameter.
    invert : :class:`tuple` of :class:`bool`
        The :py:`invert` parameter, normalized to specify polarity inversion per-wire.
    direction : :class:`Direction`
        The :py:`direction` parameter, normalized to the :class:`Direction` enumeration.
    """
    def __init__(self, p, n, *, invert=False, direction=Direction.Bidir):
        self._p = IOValue.cast(p)
        self._n = IOValue.cast(n)
        if len(self._p) != len(self._n):
            raise ValueError(f"Length of 'p' ({len(self._p)}) doesn't match length of 'n' "
                             f"({len(self._n)})")
        if isinstance(invert, bool):
            self._invert = (invert,) * len(self._p)
        elif isinstance(invert, Iterable):
            self._invert = tuple(invert)
            if len(self._invert) != len(self._p):
                raise ValueError(f"Length of 'invert' ({len(self._invert)}) doesn't match "
                                 f"length of 'p' ({len(self._p)})")
            if not all(isinstance(item, bool) for item in self._invert):
                raise TypeError(f"'invert' must be a bool or iterable of bool, not {invert!r}")
        else:
            raise TypeError(f"'invert' must be a bool or iterable of bool, not {invert!r}")
        self._direction = Direction(direction)

    @property
    def p(self):
        return self._p

    @property
    def n(self):
        return self._n

    @property
    def invert(self):
        return self._invert

    @property
    def direction(self):
        return self._direction

    def __len__(self):
        return len(self._p)

    def __invert__(self):
        return DifferentialPort(self._p, self._n, invert=tuple(not inv for inv in self._invert),
                                direction=self._direction)

    def __getitem__(self, index):
        return DifferentialPort(self._p[index], self._n[index], invert=self._invert[index],
                                direction=self._direction)

    def __add__(self, other):
        if not isinstance(other, DifferentialPort):
            return NotImplemented
        return DifferentialPort(Cat(self._p, other._p), Cat(self._n, other._n),
                                invert=self._invert + other._invert,
                                direction=self._direction & other._direction)

    def __repr__(self):
        if not any(self._invert):
            invert = False
        elif all(self._invert):
            invert = True
        else:
            invert = self._invert
        return (f"DifferentialPort({self._p!r}, {self._n!r}, invert={invert!r}, "
                f"direction={self._direction})")


class SimulationPort(PortLike):
    """Represents a simulation library I/O port.

    Implements the :class:`PortLike` interface.

    Parameters
    ----------
    direction : :class:`Direction` or :class:`str`
        Set of allowed buffer directions. A string is converted to a :class:`Direction` first.
        If equal to :attr:`~Direction.Input` or :attr:`~Direction.Output`, this port can only be
        used with buffers of matching direction. If equal to :attr:`~Direction.Bidir`, this port
        can be used with buffers of any direction.
    width : :class:`int`
        Width of the port. The width of each of the attributes :py:`i`, :py:`o`, :py:`oe` (whenever
        present) equals :py:`width`.
    invert : :class:`bool` or iterable of :class:`bool`
        Polarity inversion. If the value is a simple :class:`bool`, it specifies inversion for
        the entire port. If the value is an iterable of :class:`bool`, the iterable must have the
        same length as the width of :py:`p` and :py:`n`, and the inversion is specified for
        individual wires.
    name : :class:`str` or :py:`None`
        Name of the port. This name is only used to derive the names of the input, output, and
        output enable signals.
    src_loc_at : :class:`int`
        :ref:`Source location <lang-srcloc>`. Used to infer :py:`name` if not specified.

    Attributes
    ----------
    i : :class:`Signal`
        Input signal. Present if :py:`direction in (Input, Bidir)`.
    o : :class:`Signal`
        Ouptut signal. Present if :py:`direction in (Output, Bidir)`.
    oe : :class:`Signal`
        Output enable signal. Present if :py:`direction in (Output, Bidir)`.
    invert : :class:`tuple` of :class:`bool`
        The :py:`invert` parameter, normalized to specify polarity inversion per-wire.
    direction : :class:`Direction`
        The :py:`direction` parameter, normalized to the :class:`Direction` enumeration.
    """
    def __init__(self, direction, width, *, invert=False, name=None, src_loc_at=0):
        if name is not None and not isinstance(name, str):
            raise TypeError(f"Name must be a string, not {name!r}")
        if name is None:
            name = tracer.get_var_name(depth=2 + src_loc_at, default="$port")

        if not (isinstance(width, int) and width >= 0):
            raise TypeError(f"Width must be a non-negative integer, not {width!r}")

        self._direction = Direction(direction)

        self._i = self._o = self._oe = None
        if self._direction in (Direction.Input, Direction.Bidir):
            self._i  = Signal(width, name=f"{name}__i")
        if self._direction in (Direction.Output, Direction.Bidir):
            self._o  = Signal(width, name=f"{name}__o")
            self._oe = Signal(width, name=f"{name}__oe",
                              init=~0 if self._direction is Direction.Output else 0)

        if isinstance(invert, bool):
            self._invert = (invert,) * width
        elif isinstance(invert, Iterable):
            self._invert = tuple(invert)
            if len(self._invert) != width:
                raise ValueError(f"Length of 'invert' ({len(self._invert)}) doesn't match "
                                 f"port width ({width})")
            if not all(isinstance(item, bool) for item in self._invert):
                raise TypeError(f"'invert' must be a bool or iterable of bool, not {invert!r}")
        else:
            raise TypeError(f"'invert' must be a bool or iterable of bool, not {invert!r}")

    @property
    def i(self):
        if self._i is None:
            raise AttributeError(
                "Simulation port with output direction does not have an input signal")
        return self._i

    @property
    def o(self):
        if self._o is None:
            raise AttributeError(
                "Simulation port with input direction does not have an output signal")
        return self._o

    @property
    def oe(self):
        if self._oe is None:
            raise AttributeError(
                "Simulation port with input direction does not have an output enable signal")
        return self._oe

    @property
    def invert(self):
        return self._invert

    @property
    def direction(self):
        return self._direction

    def __len__(self):
        if self._direction is Direction.Input:
            return len(self._i)
        if self._direction is Direction.Output:
            assert len(self._o) == len(self._oe)
            return len(self._o)
        if self._direction is Direction.Bidir:
            assert len(self._i) == len(self._o) == len(self._oe)
            return len(self._i)
        assert False # :nocov:

    def __getitem__(self, key):
        result = object.__new__(type(self))
        result._i  = None if self._i  is None else self._i [key]
        result._o  = None if self._o  is None else self._o [key]
        result._oe = None if self._oe is None else self._oe[key]
        if isinstance(key, slice):
            result._invert = self._invert[key]
        else:
            result._invert = (self._invert[key],)
        result._direction = self._direction
        return result

    def __invert__(self):
        result = object.__new__(type(self))
        result._i = self._i
        result._o = self._o
        result._oe = self._oe
        result._invert = tuple(not invert for invert in self._invert)
        result._direction = self._direction
        return result

    def __add__(self, other):
        if not isinstance(other, SimulationPort):
            return NotImplemented
        direction = self._direction & other._direction
        result = object.__new__(type(self))
        result._i  = None if direction is Direction.Output else Cat(self._i,  other._i)
        result._o  = None if direction is Direction.Input  else Cat(self._o,  other._o)
        result._oe = None if direction is Direction.Input  else Cat(self._oe, other._oe)
        result._invert = self._invert + other._invert
        result._direction = direction
        return result

    def __repr__(self):
        parts = []
        if self._i is not None:
            parts.append(f"i={self._i!r}")
        if self._o is not None:
            parts.append(f"o={self._o!r}")
        if self._oe is not None:
            parts.append(f"oe={self._oe!r}")
        if not any(self._invert):
            invert = False
        elif all(self._invert):
            invert = True
        else:
            invert = self._invert
        return (f"SimulationPort({', '.join(parts)}, invert={invert!r}, "
                f"direction={self._direction})")


class Buffer(wiring.Component):
    """A combinational I/O buffer component.

    This buffer can be used on any platform; if the platform does not specialize its implementation,
    an :ref:`I/O buffer instance <lang-iobufferinstance>` is used.

    The following diagram defines the timing relationship between the underlying core I/O value
    (for differential ports, the core I/O value of the true half) and the :py:`i`, :py:`o`, and
    :py:`oe` members:

    .. wavedrom:: io/buffer

        {
            "signal": [
                {"name": "clk",  "wave": "p....."},
                {"name": "o",    "wave": "x345x.", "data": ["A", "B", "C"]},
                {"name": "oe",   "wave": "01..0."},
                {},
                {"name": "port", "wave": "z345z.", "data": ["A", "B", "C"]},
                {},
                {"name": "i",    "wave": "x345x.", "data": ["A", "B", "C"]}
            ],
            "config": {
                "hscale": 2
            }
        }

    Parameters
    ----------
    direction : :class:`Direction`
        Direction of the buffer.
    port : :class:`PortLike`
        Port driven by the buffer.

    Raises
    ------
    :exc:`ValueError`
        Unless :py:`port.direction in (direction, Bidir)`.

    Attributes
    ----------
    signature : :class:`Buffer.Signature`
        :py:`Signature(direction, len(port)).flip()`.
    """
    class Signature(wiring.Signature):
        """Signature of a combinational I/O buffer.

        Parameters
        ----------
        direction : :class:`Direction`
            Direction of the buffer.
        width : :class:`int`
            Width of the buffer.

        Members
        -------
        i: :py:`In(width)`
            Present if :py:`direction in (Input, Bidir)`.
        o: :py:`Out(width)`
            Present if :py:`direction in (Output, Bidir)`.
        oe: :py:`Out(1, init=0)`
            Present if :py:`direction is Bidir`.
        oe: :py:`Out(1, init=1)`
            Present if :py:`direction is Output`.
        """
        def __init__(self, direction, width):
            self._direction = Direction(direction)
            self._width = operator.index(width)
            members = {}
            if self._direction is not Direction.Output:
                members["i"] = wiring.In(self._width)
            if self._direction is not Direction.Input:
                members["o"] = wiring.Out(self._width)
                members["oe"] = wiring.Out(1, init=int(self._direction is Direction.Output))
            super().__init__(members)

        @property
        def direction(self):
            return self._direction

        @property
        def width(self):
            return self._width

        def __eq__(self, other):
            return (type(self) is type(other) and self.direction == other.direction and
                    self.width == other.width)

        def __repr__(self):
            return f"Buffer.Signature({self.direction}, {self.width})"

    def __init__(self, direction, port):
        if not isinstance(port, PortLike):
            raise TypeError(f"'port' must be a 'PortLike', not {port!r}")
        self._port = port
        super().__init__(Buffer.Signature(direction, len(port)).flip())
        if port.direction is Direction.Input and self.direction is not Direction.Input:
            raise ValueError(f"Input port cannot be used with {self.direction.name} buffer")
        if port.direction is Direction.Output and self.direction is not Direction.Output:
            raise ValueError(f"Output port cannot be used with {self.direction.name} buffer")

    @property
    def port(self):
        return self._port

    @property
    def direction(self):
        return self.signature.direction

    def elaborate(self, platform):
        if hasattr(platform, "get_io_buffer"):
            return platform.get_io_buffer(self)

        m = Module()

        invert = sum(bit << idx for idx, bit in enumerate(self._port.invert))
        if self.direction is not Direction.Input:
            if invert != 0:
                o_inv = Signal.like(self.o)
                m.d.comb += o_inv.eq(self.o ^ invert)
            else:
                o_inv = self.o
        if self.direction is not Direction.Output:
            if invert:
                i_inv = Signal.like(self.i)
                m.d.comb += self.i.eq(i_inv ^ invert)
            else:
                i_inv = self.i

        if isinstance(self._port, SingleEndedPort):
            if self.direction is Direction.Input:
                m.submodules += IOBufferInstance(self._port.io, i=i_inv)
            elif self.direction is Direction.Output:
                m.submodules += IOBufferInstance(self._port.io, o=o_inv, oe=self.oe)
            else:
                m.submodules += IOBufferInstance(self._port.io, o=o_inv, oe=self.oe, i=i_inv)
        elif isinstance(self._port, DifferentialPort):
            if self.direction is Direction.Input:
                m.submodules += IOBufferInstance(self._port.p, i=i_inv)
            elif self.direction is Direction.Output:
                m.submodules += IOBufferInstance(self._port.p, o=o_inv, oe=self.oe)
                m.submodules += IOBufferInstance(self._port.n, o=~o_inv, oe=self.oe)
            else:
                m.submodules += IOBufferInstance(self._port.p, o=o_inv, oe=self.oe, i=i_inv)
                m.submodules += IOBufferInstance(self._port.n, o=~o_inv, oe=self.oe)
        elif isinstance(self._port, SimulationPort):
            if self.direction is Direction.Bidir:
                # Loop back `o` if `oe` is asserted. This frees the test harness from having to
                # provide this functionality itself.
                for i_inv_bit, oe_bit, o_bit, i_bit in \
                        zip(i_inv, self._port.oe, self._port.o, self._port.i):
                    m.d.comb += i_inv_bit.eq(Cat(Mux(oe_bit, o_bit, i_bit)))
            if self.direction is Direction.Input:
                m.d.comb += i_inv.eq(self._port.i)
            if self.direction in (Direction.Output, Direction.Bidir):
                m.d.comb += self._port.o.eq(o_inv)
                m.d.comb += self._port.oe.eq(self.oe.replicate(len(self._port)))
        else:
            raise TypeError("Cannot elaborate generic 'Buffer' with port {self._port!r}") # :nocov:

        return m


class FFBuffer(wiring.Component):
    """A registered I/O buffer component.

    This buffer can be used on any platform; if the platform does not specialize its implementation,
    an :ref:`I/O buffer instance <lang-iobufferinstance>` is used, combined with reset-less
    registers on :py:`i`, :py:`o`, and  :py:`oe` members.

    The following diagram defines the timing relationship between the underlying core I/O value
    (for differential ports, the core I/O value of the true half) and the :py:`i`, :py:`o`, and
    :py:`oe` members:

    .. wavedrom:: io/ff-buffer

        {
            "signal": [
                {"name": "clk",  "wave": "p......"},
                {"name": "o",    "wave": "x345x..", "data": ["A", "B", "C"]},
                {"name": "oe",   "wave": "01..0.."},
                {},
                {"name": "port", "wave": "z.345z.", "data": ["A", "B", "C"]},
                {},
                {"name": "i",    "wave": "x..345x", "data": ["A", "B", "C"]}
            ],
            "config": {
                "hscale": 2
            }
        }

    .. warning::

        On some platforms, this buffer can only be used with rising edge clock domains, and will
        raise an exception during conversion of the design to a netlist otherwise.

        This limitation will be lifted in the future.

    Parameters
    ----------
    direction : :class:`Direction`
        Direction of the buffer.
    port : :class:`PortLike`
        Port driven by the buffer.
    i_domain : :class:`str`
        Name of the input register's clock domain. Used when :py:`direction in (Input, Bidir)`.
        Defaults to :py:`"sync"`.
    o_domain : :class:`str`
        Name of the output and output enable registers' clock domain. Used when
        :py:`direction in (Output, Bidir)`. Defaults to :py:`"sync"`.

    Attributes
    ----------
    signature : :class:`FFBuffer.Signature`
        :py:`Signature(direction, len(port)).flip()`.
    """
    class Signature(wiring.Signature):
        """Signature of a registered I/O buffer.

        Parameters
        ----------
        direction : :class:`Direction`
            Direction of the buffer.
        width : :class:`int`
            Width of the buffer.

        Members
        -------
        i: :py:`In(width)`
            Present if :py:`direction in (Input, Bidir)`.
        o: :py:`Out(width)`
            Present if :py:`direction in (Output, Bidir)`.
        oe: :py:`Out(1, init=0)`
            Present if :py:`direction is Bidir`.
        oe: :py:`Out(1, init=1)`
            Present if :py:`direction is Output`.
        """
        def __init__(self, direction, width):
            self._direction = Direction(direction)
            self._width = operator.index(width)
            members = {}
            if self._direction is not Direction.Output:
                members["i"] = wiring.In(self._width)
            if self._direction is not Direction.Input:
                members["o"] = wiring.Out(self._width)
                members["oe"] = wiring.Out(1, init=int(self._direction is Direction.Output))
            super().__init__(members)

        @property
        def direction(self):
            return self._direction

        @property
        def width(self):
            return self._width

        def __eq__(self, other):
            return (type(self) is type(other) and self.direction == other.direction and
                    self.width == other.width)

        def __repr__(self):
            return f"FFBuffer.Signature({self.direction}, {self.width})"

    def __init__(self, direction, port, *, i_domain=None, o_domain=None):
        if not isinstance(port, PortLike):
            raise TypeError(f"'port' must be a 'PortLike', not {port!r}")
        self._port = port
        super().__init__(FFBuffer.Signature(direction, len(port)).flip())
        if self.signature.direction is not Direction.Output:
            self._i_domain = i_domain or "sync"
        else:
            if i_domain is not None:
                raise ValueError("Output buffer doesn't have an input domain")
            self._i_domain = None
        if self.signature.direction is not Direction.Input:
            self._o_domain = o_domain or "sync"
        else:
            if o_domain is not None:
                raise ValueError("Input buffer doesn't have an output domain")
            self._o_domain = None
        if port.direction is Direction.Input and self.direction is not Direction.Input:
            raise ValueError(f"Input port cannot be used with {self.direction.name} buffer")
        if port.direction is Direction.Output and self.direction is not Direction.Output:
            raise ValueError(f"Output port cannot be used with {self.direction.name} buffer")

    @property
    def port(self):
        return self._port

    @property
    def direction(self):
        return self.signature.direction

    @property
    def i_domain(self):
        return self._i_domain

    @property
    def o_domain(self):
        return self._o_domain

    def elaborate(self, platform):
        if hasattr(platform, "get_io_buffer"):
            return platform.get_io_buffer(self)

        m = Module()

        m.submodules.io_buffer = io_buffer = Buffer(self.direction, self.port)

        if self.direction is not Direction.Output:
            i_ff = Signal(len(self.port), reset_less=True)
            m.d[self.i_domain] += i_ff.eq(io_buffer.i)
            m.d.comb += self.i.eq(i_ff)

        if self.direction is not Direction.Input:
            o_ff = Signal(len(self.port), reset_less=True)
            oe_ff = Signal(reset_less=True)
            m.d[self.o_domain] += o_ff.eq(self.o)
            m.d[self.o_domain] += oe_ff.eq(self.oe)
            m.d.comb += io_buffer.o.eq(o_ff)
            m.d.comb += io_buffer.oe.eq(oe_ff)

        return m


class DDRBuffer(wiring.Component):
    """A double data rate I/O buffer component.

    This buffer is only available on platforms that support double data rate I/O.

    The following diagram defines the timing relationship between the underlying core I/O value
    (for differential ports, the core I/O value of the true half) and the :py:`i`, :py:`o`, and
    :py:`oe` members:

    ..
        This diagram should have `port` phase shifted, but it hits wavedrom/wavedrom#416.
        It is also affected by wavedrom/wavedrom#417.

    .. wavedrom:: io/ddr-buffer

        {
            "head": {
                "tick": 0
            },
            "signal": [
                {"name": "clk",  "wave": "p......."},
                {"name": "o[0]", "wave": "x357x...", "node": ".a",
                 "data": ["A", "C", "E"]},
                {"name": "o[1]", "wave": "x468x...", "node": ".b",
                 "data": ["B", "D", "F"]},
                {"name": "oe",   "wave": "01..0..."},
                {                                            "node": "........R.S",
                 "period": 0.5},
                {"name": "port", "wave": "z...345678z.....", "node": "....123456",
                 "data": ["A", "B", "C", "D", "E", "F"],
                 "period": 0.5},
                {                                            "node": "..P.Q",
                 "period": 0.5},
                {"name": "i[0]", "wave": "x...468x", "node": ".....d",
                 "data": ["B", "D", "F"]},
                {"name": "i[1]", "wave": "x..357x.", "node": ".....e",
                 "data": ["A", "C", "E"]}
            ],
            "edge": [
                "a~1", "b-~2", "P+Q t1",
                "5~-d", "6~e", "R+S t2"
            ],
            "config": {
                "hscale": 2
            }
        }

    The output data (labelled *a*, *b*) is input from :py:`o` into internal registers at
    the beginning of clock cycle 2, and transmitted at points labelled *1*, *2* during the same
    clock cycle. The output latency *t1* is defined as the amount of cycles between the time of
    capture of :py:`o` and the time of transmission of rising edge data plus one cycle, and is 1
    for this diagram.

    The received data is captured into internal registers during the clock cycle 4 at points
    labelled *5*, *6*, and output to :py:`i` during the next clock cycle (labelled *d*, *e*).
    The input latency *t2* is defined as the amount of cycles between the time of reception of
    rising edge data and the time of update of :py:`i`, and is 1 for this diagram.

    The output enable signal is input from :py:`oe` once per cycle and affects the entire cycle it
    applies to. Its latency is defined in the same way as the output latency, and is equal to *t1*.

    .. warning::

        Some platforms include additional pipeline registers that may cause latencies *t1* and *t2*
        to be higher than one cycle. At the moment there is no way to query these latencies.

        This limitation will be lifted in the future.

    .. warning::

        On all supported platforms, this buffer can only be used with rising edge clock domains,
        and will raise an exception during conversion of the design to a netlist otherwise.

        This limitation may be lifted in the future.

    .. warning::

        Double data rate I/O buffers are not compatible with :class:`SimulationPort`.

        This limitation may be lifted in the future.

    Parameters
    ----------
    direction : :class:`Direction`
        Direction of the buffer.
    port : :class:`PortLike`
        Port driven by the buffer.
    i_domain : :class:`str`
        Name of the input register's clock domain. Used when :py:`direction in (Input, Bidir)`.
        Defaults to :py:`"sync"`.
    o_domain : :class:`str`
        Name of the output and output enable registers' clock domain. Used when
        :py:`direction in (Output, Bidir)`. Defaults to :py:`"sync"`.

    Attributes
    ----------
    signature : :class:`DDRBuffer.Signature`
        :py:`Signature(direction, len(port)).flip()`.
    """
    class Signature(wiring.Signature):
        """Signature of a double data rate I/O buffer.

        Parameters
        ----------
        direction : :class:`Direction`
            Direction of the buffer.
        width : :class:`int`
            Width of the buffer.

        Members
        -------
        i: :py:`In(ArrayLayout(width, 2))`
            Present if :py:`direction in (Input, Bidir)`.
        o: :py:`Out(ArrayLayout(width, 2))`
            Present if :py:`direction in (Output, Bidir)`.
        oe: :py:`Out(1, init=0)`
            Present if :py:`direction is Bidir`.
        oe: :py:`Out(1, init=1)`
            Present if :py:`direction is Output`.
        """
        def __init__(self, direction, width):
            self._direction = Direction(direction)
            self._width = operator.index(width)
            members = {}
            if self._direction is not Direction.Output:
                members["i"] = wiring.In(data.ArrayLayout(self._width, 2))
            if self._direction is not Direction.Input:
                members["o"] = wiring.Out(data.ArrayLayout(self._width, 2))
                members["oe"] = wiring.Out(1, init=int(self._direction is Direction.Output))
            super().__init__(members)

        @property
        def direction(self):
            return self._direction

        @property
        def width(self):
            return self._width

        def __eq__(self, other):
            return (type(self) is type(other) and self.direction == other.direction and
                    self.width == other.width)

        def __repr__(self):
            return f"DDRBuffer.Signature({self.direction}, {self.width})"

    def __init__(self, direction, port, *, i_domain=None, o_domain=None):
        if not isinstance(port, PortLike):
            raise TypeError(f"'port' must be a 'PortLike', not {port!r}")
        self._port = port
        super().__init__(DDRBuffer.Signature(direction, len(port)).flip())
        if self.signature.direction is not Direction.Output:
            self._i_domain = i_domain or "sync"
        else:
            if i_domain is not None:
                raise ValueError("Output buffer doesn't have an input domain")
            self._i_domain = None
        if self.signature.direction is not Direction.Input:
            self._o_domain = o_domain or "sync"
        else:
            if o_domain is not None:
                raise ValueError("Input buffer doesn't have an output domain")
            self._o_domain = None
        if port.direction is Direction.Input and self.direction is not Direction.Input:
            raise ValueError(f"Input port cannot be used with {self.direction.name} buffer")
        if port.direction is Direction.Output and self.direction is not Direction.Output:
            raise ValueError(f"Output port cannot be used with {self.direction.name} buffer")

    @property
    def port(self):
        return self._port

    @property
    def direction(self):
        return self.signature.direction

    @property
    def i_domain(self):
        return self._i_domain

    @property
    def o_domain(self):
        return self._o_domain

    def elaborate(self, platform):
        if hasattr(platform, "get_io_buffer"):
            return platform.get_io_buffer(self)

        if isinstance(self._port, SimulationPort):
            raise NotImplementedError(f"DDR buffers are not supported in simulation") # :nocov:

        raise NotImplementedError(f"DDR buffers are not supported on {platform!r}") # :nocov:


class Pin(wiring.PureInterface):
    """
    An interface to an I/O buffer or a group of them that provides uniform access to input, output,
    or tristate buffers that may include a 1:n gearbox. (A 1:2 gearbox is typically called "DDR".)

    This is an interface object using :class:`Pin.Signature` as its signature.  The signature flows
    are defined from the point of view of a component that drives the I/O buffer.

    Parameters
    ----------
    width : int
        Width of the ``i``/``iN`` and ``o``/``oN`` signals.
    dir : ``"i"``, ``"o"``, ``"io"``, ``"oe"``
        Direction of the buffers. If ``"i"`` is specified, only the ``i``/``iN`` signals are
        present. If ``"o"`` is specified, only the ``o``/``oN`` signals are present. If ``"oe"`` is
        specified, the ``o``/``oN`` signals are present, and an ``oe`` signal is present.
        If ``"io"`` is specified, both the ``i``/``iN`` and ``o``/``oN`` signals are present, and
        an ``oe`` signal is present.
    xdr : int
        Gearbox ratio. If equal to 0, the I/O buffer is combinational, and only ``i``/``o``
        signals are present. If equal to 1, the I/O buffer is SDR, and only ``i``/``o`` signals are
        present. If greater than 1, the I/O buffer includes a gearbox, and ``iN``/``oN`` signals
        are present instead, where ``N in range(0, N)``. For example, if ``xdr=2``, the I/O buffer
        is DDR; the signal ``i0`` reflects the value at the rising edge, and the signal ``i1``
        reflects the value at the falling edge.
    path : tuple of str
        As in :class:`PureInterface`, used to name the created signals.

    Attributes
    ----------
    i_clk:
        I/O buffer input clock. Synchronizes `i*`. Present if ``xdr`` is nonzero.
    i_fclk:
        I/O buffer input fast clock. Synchronizes `i*` on higher gearbox ratios. Present if ``xdr``
        is greater than 2.
    i : Signal, out
        I/O buffer input, without gearing. Present if ``dir="i"`` or ``dir="io"``, and ``xdr`` is
        equal to 0 or 1.
    i0, i1, ... : Signal, out
        I/O buffer inputs, with gearing. Present if ``dir="i"`` or ``dir="io"``, and ``xdr`` is
        greater than 1.
    o_clk:
        I/O buffer output clock. Synchronizes `o*`, including `oe`. Present if ``xdr`` is nonzero.
    o_fclk:
        I/O buffer output fast clock. Synchronizes `o*` on higher gearbox ratios. Present if
        ``xdr`` is greater than 2.
    o : Signal, in
        I/O buffer output, without gearing. Present if ``dir="o"`` or ``dir="io"``, and ``xdr`` is
        equal to 0 or 1.
    o0, o1, ... : Signal, in
        I/O buffer outputs, with gearing. Present if ``dir="o"`` or ``dir="io"``, and ``xdr`` is
        greater than 1.
    oe : Signal, in
        I/O buffer output enable. Present if ``dir="io"`` or ``dir="oe"``. Buffers generally
        cannot change direction more than once per cycle, so at most one output enable signal
        is present.
    """

    class Signature(wiring.Signature):
        """A signature for :class:`Pin`.  The parameters are as defined on the ``Pin`` class,
        and are accessible as attributes.
        """
        # TODO(amaranth-0.6): remove
        @deprecated("`amaranth.lib.io.Pin` is deprecated, use `amaranth.lib.io.*Buffer` instead")
        def __init__(self, width, dir, *, xdr=0):
            if not isinstance(width, int) or width < 0:
                raise TypeError("Width must be a non-negative integer, not {!r}"
                                .format(width))
            if dir not in ("i", "o", "oe", "io"):
                raise TypeError("Direction must be one of \"i\", \"o\", \"io\", or \"oe\", not {!r}"""
                                .format(dir))
            if not isinstance(xdr, int) or xdr < 0:
                raise TypeError("Gearing ratio must be a non-negative integer, not {!r}"
                                .format(xdr))

            self.width = width
            self.dir = dir
            self.xdr = xdr

            members = {}
            if dir in ("i", "io"):
                if xdr > 0:
                    members["i_clk"] = Out(1)
                if xdr > 2:
                    members["i_fclk"] = Out(1)
                if xdr in (0, 1):
                    members["i"] = In(width)
                else:
                    for n in range(xdr):
                        members[f"i{n}"] = In(width)
            if dir in ("o", "oe", "io"):
                if xdr > 0:
                    members["o_clk"] = Out(1)
                if xdr > 2:
                    members["o_fclk"] = Out(1)
                if xdr in (0, 1):
                    members["o"] = Out(width)
                else:
                    for n in range(xdr):
                        members[f"o{n}"] = Out(width)
            if dir in ("oe", "io"):
                members["oe"] = Out(1)
            super().__init__(members)

        def __eq__(self, other):
            return (type(self) is type(other) and
                    self.width == other.width and
                    self.dir == other.dir and
                    self.xdr == other.xdr)

        def __repr__(self):
            xdr = f", xdr={self.xdr}" if self.xdr != 0 else ""
            return f"Pin.Signature({self.width}, dir={self.dir!r}{xdr})"

        def create(self, *, path=None, src_loc_at=0):
            return Pin(self.width, self.dir, xdr=self.xdr, path=path, src_loc_at=1 + src_loc_at)

    # TODO(amaranth-0.6): remove
    @deprecated("`amaranth.lib.io.Pin` is deprecated, use `amaranth.lib.io.*Buffer` instead")
    def __init__(self, width, dir, *, xdr=0, name=None, path=None, src_loc_at=0):
        if name is not None:
            if path is not None:
                raise ValueError("Cannot pass both name and path")
            path = (name,)
        if path is None:
            name = tracer.get_var_name(depth=3 + src_loc_at, default="$pin")
            path = (name,)
        self.path = tuple(path)
        self.name = "__".join(path)
        with _ignore_deprecated():
            signature = Pin.Signature(width, dir, xdr=xdr)
        super().__init__(signature, path=path, src_loc_at=src_loc_at + 1)

    @property
    def width(self):
        return self.signature.width

    @property
    def dir(self):
        return self.signature.dir

    @property
    def xdr(self):
        return self.signature.xdr
