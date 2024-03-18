import enum
from collections.abc import Iterable

from ..hdl import *
from ..lib import wiring
from ..lib.wiring import In, Out
from .. import tracer


__all__ = ["Direction", "SingleEndedPort", "DifferentialPort", "Pin"]


class Direction(enum.Enum):
    """Represents a direction of an I/O port, or of an I/O buffer."""

    #: Input direction (from world to Amaranth design)
    Input  = "i"
    #: Output direction (from Amaranth design to world)
    Output = "o"
    #: Bidirectional (can be switched between input and output)
    Bidir  = "io"

    def __or__(self, other):
        if not isinstance(other, Direction):
            return NotImplemented
        if self == other:
            return self
        else:
            return Direction.Bidir

    def __and__(self, other):
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


class SingleEndedPort:
    """Represents a single-ended I/O port with optional inversion.

    Parameters
    ----------
    io : IOValue
        The raw I/O value being wrapped.
    invert : bool or iterable of bool
        If true, the electrical state of the physical pin will be opposite from the Amaranth value
        (the ``*Buffer`` classes will insert inverters on ``o`` and ``i`` pins, as appropriate).

        This can be used for various purposes:

        - Normalizing active-low pins (such as ``CS_B``) to be active-high in Amaranth code
        - Compensating for boards where an inverting level-shifter (or similar circuitry) was used
          on the pin

        If the value is a simple :class:`bool`, it is used for all bits of this port. If the value
        is an iterable of :class:`bool`, the iterable must have the same length as ``io``, and
        the inversion is specified per-bit.
    direction : Direction or str
        Represents the allowed directions of this port. If equal to :attr:`Direction.Input` or
        :attr:`Direction.Output`, this port can only be used with buffers of matching direction.
        If equal to :attr:`Direction.Bidir`, this port can be used with buffers of any direction.
        If a string is passed, it is cast to :class:`Direction`.
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
        """The ``io`` argument passed to the constructor."""
        return self._io

    @property
    def invert(self):
        """The ``invert`` argument passed to the constructor, normalized to a :class:`tuple`
        of :class:`bool`."""
        return self._invert

    @property
    def direction(self):
        """The ``direction`` argument passed to the constructor, normalized to :class:`Direction`."""
        return self._direction

    def __len__(self):
        """Returns the width of this port in bits. Equal to :py:`len(self.io)`."""
        return len(self._io)

    def __invert__(self):
        """Returns a new :class:`SingleEndedPort` with the opposite value of ``invert``."""
        return SingleEndedPort(self._io, invert=tuple(not inv for inv in self._invert),
                               direction=self._direction)

    def __getitem__(self, index):
        """Slices the port, returning another :class:`SingleEndedPort` with a subset
        of its bits.

        The index can be a :class:`slice` or :class:`int`. If the index is
        an :class:`int`, the result is a single-bit :class:`SingleEndedPort`."""
        return SingleEndedPort(self._io[index], invert=self._invert[index],
                               direction=self._direction)

    def __add__(self, other):
        """Concatenates two :class:`SingleEndedPort` objects together, returning a new
        :class:`SingleEndedPort` object.

        When the concatenated ports have different directions, the conflict is resolved as follows:

        - If a bidirectional port is concatenated with an input port, the result is an input port.
        - If a bidirectional port is concatenated with an output port, the result is an output port.
        - If an input port is concatenated with an output port, :exc:`ValueError` is raised.
        """
        if not isinstance(other, SingleEndedPort):
            return NotImplemented
        return SingleEndedPort(Cat(self._io, other._io), invert=self._invert + other._invert,
                               direction=self._direction | other._direction)

    def __repr__(self):
        if all(self._invert):
            invert = True
        elif not any(self._invert):
            invert = False
        else:
            invert = self._invert
        return f"SingleEndedPort({self._io!r}, invert={invert!r}, direction={self._direction})"


class DifferentialPort:
    """Represents a differential I/O port with optional inversion.

    Parameters
    ----------
    p : IOValue
        The raw I/O value used as positive (true) half of the port.
    n : IOValue
        The raw I/O value used as negative (complemented) half of the port. Must have the same
        length as ``p``.
    invert : bool or iterable of bool
        If true, the electrical state of the physical pin will be opposite from the Amaranth value
        (the ``*Buffer`` classes will insert inverters on ``o`` and ``i`` pins, as appropriate).

        This can be used for various purposes:

        - Normalizing active-low pins (such as ``CS_B``) to be active-high in Amaranth code
        - Compensating for boards where the P and N pins are swapped (e.g. for easier routing)

        If the value is a simple :class:`bool`, it is used for all bits of this port. If the value
        is an iterable of :class:`bool`, the iterable must have the same length as ``io``, and
        the inversion is specified per-bit.
    direction : Direction or str
        Represents the allowed directions of this port. If equal to :attr:`Direction.Input` or
        :attr:`Direction.Output`, this port can only be used with buffers of matching direction.
        If equal to :attr:`Direction.Bidir`, this port can be used with buffers of any direction.
        If a string is passed, it is cast to :class:`Direction`.
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
        """The ``p`` argument passed to the constructor."""
        return self._p

    @property
    def n(self):
        """The ``n`` argument passed to the constructor."""
        return self._n

    @property
    def invert(self):
        """The ``invert`` argument passed to the constructor, normalized to a :class:`tuple`
        of :class:`bool`."""
        return self._invert

    @property
    def direction(self):
        """The ``direction`` argument passed to the constructor, normalized to :class:`Direction`."""
        return self._direction

    def __len__(self):
        """Returns the width of this port in bits. Equal to :py:`len(self.p)` (and :py:`len(self.n)`)."""
        return len(self._p)

    def __invert__(self):
        """Returns a new :class:`DifferentialPort` with the opposite value of ``invert``."""
        return DifferentialPort(self._p, self._n, invert=tuple(not inv for inv in self._invert),
                               direction=self._direction)

    def __getitem__(self, index):
        """Slices the port, returning another :class:`DifferentialPort` with a subset
        of its bits.

        The index can be a :class:`slice` or :class:`int`. If the index is
        an :class:`int`, the result is a single-bit :class:`DifferentialPort`."""
        return DifferentialPort(self._p[index], self._n[index], invert=self._invert[index],
                               direction=self._direction)

    def __add__(self, other):
        """Concatenates two :class:`DifferentialPort` objects together, returning a new
        :class:`DifferentialPort` object.

        When the concatenated ports have different directions, the conflict is resolved as follows:

        - If a bidirectional port is concatenated with an input port, the result is an input port.
        - If a bidirectional port is concatenated with an output port, the result is an output port.
        - If an input port is concatenated with an output port, :exc:`ValueError` is raised.
        """
        if not isinstance(other, DifferentialPort):
            return NotImplemented
        return DifferentialPort(Cat(self._p, other._p), Cat(self._n, other._n),
                               invert=self._invert + other._invert,
                               direction=self._direction | other._direction)

    def __repr__(self):
        if not any(self._invert):
            invert = False
        elif all(self._invert):
            invert = True
        else:
            invert = self._invert
        return f"DifferentialPort({self._p!r}, {self._n!r}, invert={invert!r}, direction={self._direction})"


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
        Gearbox ratio. If equal to 0, the I/O buffer is combinatorial, and only ``i``/``o``
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

    def __init__(self, width, dir, *, xdr=0, name=None, path=None, src_loc_at=0):
        if name is not None:
            if path is not None:
                raise ValueError("Cannot pass both name and path")
            path = (name,)
        if path is None:
            name = tracer.get_var_name(depth=2 + src_loc_at, default="$pin")
            path = (name,)
        self.path = tuple(path)
        self.name = "__".join(path)
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
