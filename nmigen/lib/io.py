from .. import *
from ..hdl.rec import *


__all__ = ["pin_layout", "Pin"]


def pin_layout(width, dir, xdr=0):
    """
    Layout of the platform interface of a pin or several pins, which may be used inside
    user-defined records.

    See :class:`Pin` for details.
    """
    if not isinstance(width, int) or width < 1:
        raise TypeError("Width must be a positive integer, not {!r}"
                        .format(width))
    if dir not in ("i", "o", "oe", "io"):
        raise TypeError("Direction must be one of \"i\", \"o\", \"io\", or \"oe\", not {!r}"""
                        .format(dir))
    if not isinstance(xdr, int) or xdr < 0:
        raise TypeError("Gearing ratio must be a non-negative integer, not {!r}"
                        .format(xdr))

    fields = []
    if dir in ("i", "io"):
        if xdr > 0:
            fields.append(("i_clk", 1))
        if xdr > 2:
            fields.append(("i_fclk", 1))
        if xdr in (0, 1):
            fields.append(("i", width))
        else:
            for n in range(xdr):
                fields.append(("i{}".format(n), width))
    if dir in ("o", "oe", "io"):
        if xdr > 0:
            fields.append(("o_clk", 1))
        if xdr > 2:
            fields.append(("o_fclk", 1))
        if xdr in (0, 1):
            fields.append(("o", width))
        else:
            for n in range(xdr):
                fields.append(("o{}".format(n), width))
    if dir in ("oe", "io"):
        fields.append(("oe", 1))
    return Layout(fields)


class Pin(Record):
    """
    An interface to an I/O buffer or a group of them that provides uniform access to input, output,
    or tristate buffers that may include a 1:n gearbox. (A 1:2 gearbox is typically called "DDR".)

    A :class:`Pin` is identical to a :class:`Record` that uses the corresponding :meth:`pin_layout`
    except that it allos accessing the parameters like ``width`` as attributes. It is legal to use
    a plain :class:`Record` anywhere a :class:`Pin` is used, provided that these attributes are
    not necessary.

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
    name : str
        Name of the underlying record.

    Attributes
    ----------
    i_clk:
        I/O buffer input clock. Synchronizes `i*`. Present if ``xdr`` is nonzero.
    i_fclk:
        I/O buffer input fast clock. Synchronizes `i*` on higer gearbox ratios. Present if ``xdr``
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
    def __init__(self, width, dir, *, xdr=0, name=None, src_loc_at=0):
        self.width = width
        self.dir   = dir
        self.xdr   = xdr

        super().__init__(pin_layout(self.width, self.dir, self.xdr),
                         name=name, src_loc_at=src_loc_at + 1)
