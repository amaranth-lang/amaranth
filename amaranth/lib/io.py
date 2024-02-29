from .. import *
from ..lib import wiring
from ..lib.wiring import In, Out
from .. import tracer


__all__ = ["Pin"]


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
