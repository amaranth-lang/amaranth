from amaranth import *
from amaranth.lib.wiring import Component, In, Out, Signature
from amaranth.utils import bits_for

import math

# The Strobe Generator classes generate a pulse train on the sync
# domain at given frequency which is not necessarily a divider of the
# sync domain clock.

# Theory of operation:
#
# The pulse generation uses an incremental error algorithm inspired of
# the bresenham line-drawing algorithm.
#
# Calling the sync domain frequency bf (base frequency) and the strobe
# frequency sf, the base methodology is to have an accumulator and run
# on each sync:
#   accumulator += sf
#   if sf >= bf:
#       accumulator -= bf
#       emit 1
#   else:
#       emit 0
#
# Since sf < bf, the accumulator stays between 0 and bf-1. After k
# ticks of the base clock, the accumulator will have been incremented
# by k*sf.  That means the if will have triggered int(k*sf/bf) times.
# At the limit, that makes the strobe generation ratio sf/bf, which is
# exactly what is wanted.
#
# Merging the additions: having two adders can be avoided.  It
# suffices to rewrite the sync update as:
#   if previous emit == 1:
#       accumulator += sf - bf
#   else:
#       accumulator += sf
#   if sf >= bf:
#       emit 1
#   else:
#       emit 0
#
# That way there's only one addition per cycle, with a mux to select
# between two possible values.
#
# Removing the comparator: inequality comparisons are costly to
# implement.  But a simple offsetting can change that.  With the
# single-adder version of the algorithm, the accumulator is in one of
# two ranges:
#  [0,  bs-1]    when a 0 was just emitted
#  [bs, bs+sf-1] when a 1 was just emitted
#
# Now let's take m=2**n such that m >= bs.  If we offset the value of
# the accumulator by m-bs, we end up with:
#  [m-bs, m-1]   when a 0 was just emitted
#  [m, m+sf-1]   when a 1 was just emitted
#
# and the comparison is done with m, a power of two.  Since m+sf-1 <
# m+bf-1 < 2m we can implement that with a n-bits-wide accumulator and
# emit the carry bit of the adder.
#
# So the final algorithm ends up being:
#   (carry, accumulator) = accumulator + Mux(previous carry, sf-bf, sf)
#   emit carry
#
# Some additional details:

# - the reset value of the accumulator must be in the valid range
#   [m-bs, m-1] if the initial value of carry is 0, or [0, sf-1] if
#   the initial value is 1.  We opted for all-ones, e.g. m-1.
#
# - when the frequencies are fixed, they can be reduced by their
#   greatest common denominator to reduce the number of bits needed in
#   the accumulator
#
# - for a variable frequency generator, the value delta = sf-bf must
#   be computed somewhere.  That adds an adder in the component.
#   Alternatively, assuming the input frequency is set by something
#   which already has a full-width adder, the delta value can be
#   made programmable too.

class FixedStrobeGenerator(Component):
    """
    This component generates a train of pulses at a mean frequency of
    strobe_frequency assuming the sync domain runs as base_frequency.

    strobe_frequency must be strictly less than base_frequency.

    Output:
        strobe: the generated pulses.
    """
    
    strobe: Out(1)

    def __init__(self, base_frequency, strobe_frequency):
        super().__init__()
        self.base_frequency = base_frequency
        self.strobe_frequency = strobe_frequency
        
        gcd = math.gcd(base_frequency, strobe_frequency)

        self.reduced_strobe_frequency = strobe_frequency // gcd
        self.reduced_base_frequency = base_frequency // gcd
        self.width = bits_for(self.reduced_base_frequency - 1)

        self.accumulator = Signal(unsigned(self.width), reset = -1)
        self.delta = (1 << self.width) - self.reduced_base_frequency + self.reduced_strobe_frequency

    def elaborate(self, platform):
        m = Module()

        if self.delta == self.reduced_strobe_frequency:
            m.d.sync += Cat(self.accumulator, self.strobe).eq(self.accumulator + self.reduced_strobe_frequency)
        else:
            m.d.sync += Cat(self.accumulator, self.strobe).eq(self.accumulator + Mux(self.strobe, self.delta, self.reduced_strobe_frequency))
            
        return m


class VariableStrobeGenerator(Elaboratable):
    """
    This component generates a train of pulses at a mean frequency of
    strobe_frequency assuming the sync domain runs as base_frequency.

    Input:
        strobe_frequency: the target frequency (must be stricly less
        than base_frequency).
        
    Output:
        strobe: the generated pulses.
    """
    def __init__(self, base_frequency):
        self.base_frequency = base_frequency
        self.width = bits_for(base_frequency - 1)

        self.signature = Signature({
            "strobe": Out(1),
            "strobe_frequency": In(self.width)
            })
            
        self.accumulator = Signal(unsigned(self.width), reset = -1)
        self.delta = Signal(unsigned(self.width))
        
        self.__dict__.update(self.signature.members.create())


    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.delta.eq(self.strobe_frequency - self.base_frequency)
        m.d.sync += Cat(self.accumulator, self.strobe).eq(self.accumulator + Mux(self.strobe, self.delta, self.strobe_frequency))
            
        return m



class VariableSimplifiedStrobeGenerator(Elaboratable):
    """
    This component generates a train of pulses at a mean frequency of
    strobe_frequency assuming the sync domain runs as base_frequency.
    base_frequency-1 must fit in width bits.

    This variant externalizes the computation of delta to, for
    instance, a cpu core in order to remove a barely-used adder.
    
    Input:
        strobe_frequency: the target frequency (must be stricly less
        than base_frequency).
        delta: result of the computation of strobe_frequency - base_frequency.

    Output:
        strobe: the generated pulses.
    """

    def __init__(self, width):        
        self.width = width

        self.signature = Signature({
            "strobe": Out(1),
            "strobe_frequency": In(self.width),
            "delta": In(self.width)
            })
            
        self.accumulator = Signal(unsigned(self.width), reset = -1)
        
        self.__dict__.update(self.signature.members.create())


    def elaborate(self, platform):
        m = Module()

        m.d.sync += Cat(self.accumulator, self.strobe).eq(self.accumulator + Mux(self.strobe, self.delta, self.strobe_frequency))
            
        return m
