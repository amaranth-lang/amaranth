from nmigen import *


def get_ineg(m, i, invert):
    """A utility method that can invert a signal after the input buffers without using specific primitives."""

    if not any(invert):
        return i
    else:
        i_n = Signal.like(i, name_suffix="_n")
        m.d.comb += i.eq(i_n ^ (int("".join(str(int(x)) for x in invert), 2)))
        return i_n


def get_oneg(m, o, invert):
    """A utility method that can invert a signal after the output buffers without using specific primitives."""

    if not any(invert):
        return o
    else:
        o_n = Signal.like(o, name_suffix="_n")
        m.d.comb += o_n.eq(o ^ (int("".join(str(int(x)) for x in invert), 2)))
        return o_n