import warnings

warnings.warn("the `amaranth.lib.coding` module will be removed without a replacement; "
              "copy the module into your project to continue using it",
              DeprecationWarning, stacklevel=2)


from .. import *


__all__ = [
    "Encoder", "Decoder",
    "PriorityEncoder", "PriorityDecoder",
    "GrayEncoder", "GrayDecoder",
]


class Encoder(Elaboratable):
    """Encode one-hot to binary.

    If one bit in ``i`` is asserted, ``n`` is low and ``o`` indicates the asserted bit.
    Otherwise, ``n`` is high and ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the input

    Attributes
    ----------
    i : Signal(width), in
        One-hot input.
    o : Signal(range(width)), out
        Encoded natural binary.
    n : Signal, out
        Invalid: either none or multiple input bits are asserted.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(range(width))
        self.n = Signal()

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.i):
            for j in range(self.width):
                with m.Case(1 << j):
                    m.d.comb += self.o.eq(j)
            with m.Default():
                m.d.comb += self.n.eq(1)
        return m


class PriorityEncoder(Elaboratable):
    """Priority encode requests to binary.

    If any bit in ``i`` is asserted, ``n`` is low and ``o`` indicates the least significant
    asserted bit.
    Otherwise, ``n`` is high and ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the input.

    Attributes
    ----------
    i : Signal(width), in
        Input requests.
    o : Signal(range(width)), out
        Encoded natural binary.
    n : Signal, out
        Invalid: no input bits are asserted.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(range(width))
        self.n = Signal()

    def elaborate(self, platform):
        m = Module()
        for j in reversed(range(self.width)):
            with m.If(self.i[j]):
                m.d.comb += self.o.eq(j)
        m.d.comb += self.n.eq(self.i == 0)
        return m


class Decoder(Elaboratable):
    """Decode binary to one-hot.

    If ``n`` is low, only the ``i``-th bit in ``o`` is asserted.
    If ``n`` is high, ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the output.

    Attributes
    ----------
    i : Signal(range(width)), in
        Input binary.
    o : Signal(width), out
        Decoded one-hot.
    n : Signal, in
        Invalid, no output bits are to be asserted.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(range(width))
        self.n = Signal()
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.i):
            for j in range(len(self.o)):
                with m.Case(j):
                    m.d.comb += self.o.eq(1 << j)
        with m.If(self.n):
            m.d.comb += self.o.eq(0)
        return m


class PriorityDecoder(Decoder):
    """Decode binary to priority request.

    Identical to :class:`Decoder`.
    """


class GrayEncoder(Elaboratable):
    """Encode binary to Gray code.

    Parameters
    ----------
    width : int
        Bit width.

    Attributes
    ----------
    i : Signal(width), in
        Natural binary input.
    o : Signal(width), out
        Encoded Gray code.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.i ^ self.i[1:])
        return m


class GrayDecoder(Elaboratable):
    """Decode Gray code to binary.

    Parameters
    ----------
    width : int
        Bit width.

    Attributes
    ----------
    i : Signal(width), in
        Gray code input.
    o : Signal(width), out
        Decoded natural binary.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()
        rhs = Const(0)
        for i in reversed(range(self.width)):
            rhs = rhs ^ self.i[i]
            m.d.comb += self.o[i].eq(rhs)
        return m
