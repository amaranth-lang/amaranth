"""
Utilities for computing cyclic redundancy checks (CRCs) in software and in
hardware.

CRCs are specified using the :py:class:`Algorithm` class, which contains
settings for CRC width, polynomial, initial value, input/output reflection, and
output XOR. Many commonly used CRC algorithms are available in the
:py:mod:`~amaranth.lib.crc.catalog` module, while most other CRC designs can be
accommodated by manually constructing :py:class:`Algorithm`.

Call the :py:class:`Algorithm` with a ``data_width`` to obtain a
:py:class:`Parameters` class, which fully defines a CRC computation. The
:py:class:`Parameters` class provides the :py:meth:`~Parameters.compute` method
to perform software computations, and the :py:meth:`~Parameters.create` method
to create a hardware CRC module, :py:class:`Processor`.

.. code-block::

    # Create a predefined CRC16-CCITT hardware module, using the default
    # 8-bit data width (in other words, bytes).
    from amaranth.lib.crc.catalog import CRC16_CCITT
    crc = m.submodules.crc = CRC16_CCITT().create()

    # Create a custom CRC algorithm, specify the data width explicitly,
    # and use it to compute a CRC value in software.
    from amaranth.lib.crc import Algorithm
    algo = Algorithm(crc_width=16, polynomial=0x1021, initial_crc=0xffff,
                     reflect_input=False, reflect_output=False,
                     xor_output=0x0000)
    assert algo(data_width=8).compute(b"123456789") == 0x29b1
"""

from ... import *

__all__ = ["Algorithm", "Parameters", "Processor", "catalog"]


class Algorithm:
    """
    Settings for a CRC algorithm, excluding data width.

    The parameter set is based on the Williams model from
    "A Painless Guide to CRC Error Detection Algorithms":
    http://www.ross.net/crc/download/crc_v3.txt

    For a reference of standard CRC parameter sets, refer to:

    * `reveng`_'s catalogue, which uses an identical parameterisation,
    * `crcmod`_'s list of predefined functions, but remove the leading '1'
      from the polynominal, XOR the "Init-value" with "XOR-out" to obtain
      ``initial_crc``, and where "Reversed" is True, set both ``reflect_input``
      and ``reflect_output`` to True,
    * `CRC Zoo`_, which contains only polynomials; use the "explicit +1"
      form of polynomial but remove the leading '1'.

    .. _reveng: https://reveng.sourceforge.io/crc-catalogue/all.htm
    .. _crcmod: http://crcmod.sourceforge.net/crcmod.predefined.html
    .. _CRC Zoo: https://users.ece.cmu.edu/~koopman/crc/

    Many commonly used CRC algorithms are available in the
    :py:mod:`~amaranth.lib.crc.catalog` module, which includes
    all entries in the `reveng`_ catalogue.

    To create a :py:class:`Parameters` instance, call the :py:class:`Algorithm`
    object with the required data width, which defaults to 8 bits.

    Parameters
    ----------
    crc_width : int
        Bit width of CRC word. Also known as "width" in the Williams model.
    polynomial : int
        CRC polynomial to use, ``crc_width`` bits long, without the implicit
        ``x**crc_width`` term. Polynomial is always specified with the highest
        order terms in the most significant bit positions; use
        ``reflect_input`` and ``reflect_output`` to perform a least
        significant bit first computation.
    initial_crc : int
        Initial value of CRC register at reset. Most significant bit always
        corresponds to the highest order term in the CRC register.
    reflect_input : bool
        If True, the input data words are bit-reflected, so that they are
        processed least significant bit first.
    reflect_output : bool
        If True, the output CRC is bit-reflected, so the least-significant bit
        of the output is the highest-order bit of the CRC register.
        Note that this reflection is performed over the entire CRC register;
        for transmission you may want to treat the output as a little-endian
        multi-word value, so for example the reflected 16-bit output 0x4E4C
        would be transmitted as the two octets 0x4C 0x4E, each transmitted
        least significant bit first.
    xor_output : int
        The output CRC will be the CRC register XOR'd with this value, applied
        after any output bit-reflection.
    """
    def __init__(self, *, crc_width, polynomial, initial_crc, reflect_input,
                 reflect_output, xor_output):
        self.crc_width = int(crc_width)
        self.polynomial = int(polynomial)
        self.initial_crc = int(initial_crc)
        self.reflect_input = bool(reflect_input)
        self.reflect_output = bool(reflect_output)
        self.xor_output = int(xor_output)

        if self.crc_width <= 0:
            raise ValueError("crc_width must be greater than 0")
        if not 0 <= self.polynomial < 2 ** self.crc_width:
            raise ValueError("polynomial must be between 0 and 2**crc_width - 1")
        if not 0 <= self.initial_crc < 2 ** self.crc_width:
            raise ValueError("initial_crc must be between 0 and 2**crc_width - 1")
        if not 0 <= self.xor_output < 2 ** self.crc_width:
            raise ValueError("xor_output must be between 0 and 2**crc_width - 1")

    def __call__(self, data_width=8):
        """
        Constructs a :py:class:`Parameters` instance from this
        :py:class:`Algorithm` with the specified ``data_width``.

        Parameters
        ----------
        data_width : int
            Bit width of data words, default 8.
        """
        return Parameters(self, data_width)

    def __repr__(self):
        return f"Algorithm(crc_width={self.crc_width}," \
               f" polynomial=0x{self.polynomial:0{self.crc_width//4}x}," \
               f" initial_crc=0x{self.initial_crc:0{self.crc_width//4}x}," \
               f" reflect_input={self.reflect_input}," \
               f" reflect_output={self.reflect_output}," \
               f" xor_output=0x{self.xor_output:0{self.crc_width//4}x})"


class Parameters:
    """
    Full set of parameters for a CRC computation.

    Contains the settings from :py:class:`Algorithm` and additionally
    ``data_width``. Refer to :py:class:`Algorithm` for details of what each
    parameter means and how to construct them.

    From this class, you can directly compute CRCs with the
    :py:meth:`~Parameters.compute` method, or construct a hardware module with
    the :py:meth:`~Parameters.create` method.

    Parameters
    ----------
    algorithm : Algorithm
        CRC algorithm to use. Specifies the CRC width, polynomial,
        initial value, whether to reflect the input or output words,
        and any output XOR.
    data_width : int
        Bit width of data words.
    """
    def __init__(self, algorithm, data_width=8):
        self._crc_width = algorithm.crc_width
        self._polynomial = algorithm.polynomial
        self._initial_crc = algorithm.initial_crc
        self._reflect_input = algorithm.reflect_input
        self._reflect_output = algorithm.reflect_output
        self._xor_output = algorithm.xor_output
        self._data_width = int(data_width)
        if self._data_width <= 0:
            raise ValueError("data_width must be greater than 0")

    @property
    def algorithm(self):
        """
        Returns an :py:class:`Algorithm` with the CRC settings from this
        instance.
        """
        return Algorithm(
            crc_width=self._crc_width,
            polynomial=self._polynomial,
            initial_crc=self._initial_crc,
            reflect_input=self._reflect_input,
            reflect_output=self._reflect_output,
            xor_output=self._xor_output)

    def residue(self):
        """
        Compute the residue value for this CRC, which is the value left in the
        CRC register after processing any valid codeword.
        """
        # Residue is computed by initialising to (possibly reflected)
        # xor_output, feeding crc_width worth of 0 bits, then taking
        # the (possibly reflected) output without any XOR.
        if self._reflect_output:
            init = self._reflect(self._xor_output, self._crc_width)
        else:
            init = self._xor_output
        algo = self.algorithm
        algo.initial_crc = init
        algo.reflect_input = False
        algo.xor_output = 0
        return algo(data_width=self._crc_width).compute([0])

    def create(self):
        """
        Returns a ``Processor`` configured with these parameters.
        """
        return Processor(self)

    def compute(self, data):
        """
        Computes and returns the CRC of all data words in ``data``.

        Parameters
        ----------
        data : iterable of integers
            The CRC is computed over this complete set of data.
            Each item is an integer of bitwidth equal to ``data_width``.
        """
        # Precompute some constants we use every iteration.
        word_max = (1 << self._data_width) - 1
        top_bit = 1 << (self._crc_width + self._data_width - 1)
        crc_mask = (1 << (self._crc_width + self._data_width)) - 1
        poly_shifted = self._polynomial << self._data_width

        # Implementation notes:
        # We always compute most-significant bit first, which means the
        # polynomial and initial value may be used as-is, and the reflect_in
        # and reflect_out values have their usual sense.
        # However, when computing word-at-a-time and MSbit-first, we must align
        # the input word so its MSbit lines up with the MSbit of the previous
        # CRC value. When the CRC width is smaller than the word width, this
        # would normally truncate data bits.
        # Instead, we shift the initial CRC left by the data width, and the
        # data word left by the crc width, lining up their MSbits no matter
        # the relation between the two widths.
        # The new CRC is then shifted right by the data width before output.

        crc = self._initial_crc << self._data_width
        for word in data:
            if not 0 <= word <= word_max:
                raise ValueError(f"data word must be between 0 and {word_max - 1}")

            if self._reflect_input:
                word = self._reflect(word, self._data_width)

            crc ^= word << self._crc_width
            for _ in range(self._data_width):
                if crc & top_bit:
                    crc = (crc << 1) ^ poly_shifted
                else:
                    crc <<= 1
            crc &= crc_mask

        crc >>= self._data_width
        if self._reflect_output:
            crc = self._reflect(crc, self._crc_width)

        crc ^= self._xor_output
        return crc

    @staticmethod
    def _reflect(word, n):
        """
        Bitwise-reflects an n-bit word ``word``.
        """
        return int(f"{word:0{n}b}"[::-1], 2)

    def _matrices(self):
        """
        Computes the F and G matrices for parallel CRC computation, treating
        the CRC as a linear time-invariant system described by the state
        relation x(t+1) = F.x(i) + G.u(i), where x(i) and u(i) are column
        vectors of the bits of the CRC register and input word, F is the n-by-n
        matrix relating the old state to the new state, and G is the n-by-m
        matrix relating the new data to the new state, where n is the CRC
        width and m is the data word width.

        The matrices are ordered least-significant-bit first; in other words
        the first entry, with index (0, 0), corresponds to the effect of the
        least-significant bit of the input on the least-significant bit of the
        output.

        For convenience of implementation, both matrices are returned
        transposed: the first index is the input bit, and the second index is
        the corresponding output bit.

        The matrices are used to select which bits are XORd together to compute
        each bit i of the new state: if F[j][i] is set then bit j of the old
        state is included in the XOR, and if G[j][i] is set then bit j of the
        new data is included.

        These matrices are not affected by ``initial_crc``, ``reflect_input``,
        ``reflect_output``, or ``xor_output``.
        """
        f = []
        g = []
        algo = self.algorithm
        algo.reflect_input = algo.reflect_output = False
        algo.xor_output = 0
        crc = Parameters(algo, self._data_width)
        for i in range(self._crc_width):
            crc._initial_crc = 2 ** i
            w = crc.compute([0])
            f.append([int(x) for x in reversed(f"{w:0{self._crc_width}b}")])
        for i in range(self._data_width):
            crc._initial_crc = 0
            w = crc.compute([2 ** i])
            g.append([int(x) for x in reversed(f"{w:0{self._crc_width}b}")])
        return f, g

    def __repr__(self):
        return f"Parameters({self.algorithm!r}, data_width={self._data_width})"


class Processor(Elaboratable):
    """
    Cyclic redundancy check (CRC) processor module.

    This module generates CRCs from an input data stream, which can be used
    to validate an existing CRC or generate a new CRC. It is configured by
    the :py:class:`Parameters` class, which can handle most forms of CRCs.
    Refer to that class's documentation for a description of the parameters.

    The CRC value is updated on any clock cycle where ``valid`` is asserted,
    with the updated value available on the ``crc`` output on the subsequent
    clock cycle. The latency is therefore one clock cycle, and the throughput
    is one data word per clock cycle.

    The CRC is reset to its initial value whenever ``start`` is asserted.
    ``start`` and ``valid`` may be asserted on the same clock cycle, in which
    case a new CRC computation is started with the current value of ``data``.

    With ``data_width=1``, a classic bit-serial CRC is implemented for the
    given polynomial in a Galois-type shift register. For larger values of
    ``data_width``, a similar architecture computes every new bit of the
    CRC in parallel.

    The ``match_detected`` output may be used to validate data with a trailing
    CRC (also known as a codeword). If the most recently processed word(s) form
    the valid CRC of all the previous data since ``start`` was asserted, the
    CRC register will always take on a fixed value known as the residue.  The
    ``match_detected`` output indicates whether the CRC register currently
    contains this residue.

    Parameters
    ----------
    parameters : Parameters
        CRC parameters.

    Attributes
    ----------
    start : Signal(), in
        Assert to indicate the start of a CRC computation, re-initialising
        the CRC register to the initial value. May be asserted simultaneously
        with ``valid`` or by itself.
    data : Signal(data_width), in
        Data word to add to CRC when ``valid`` is asserted.
    valid : Signal(), in
        Assert when ``data`` is valid to add the data word to the CRC.
    crc : Signal(crc_width), out
        Registered CRC output value, updated one clock cycle after ``valid``
        becomes asserted.
    match_detected : Signal(), out
        Asserted if the current CRC value indicates a valid codeword has been
        received.
    """
    def __init__(self, parameters):
        if not isinstance(parameters, Parameters):
            raise TypeError("Algorithmn parameters must be of type Parameters, "
                            "not {!r}"
                            .format(parameters))
        self._crc_width = parameters._crc_width
        self._data_width = parameters._data_width
        self._polynomial = parameters._polynomial
        self._initial_crc = Const(parameters._initial_crc, self._crc_width)
        self._reflect_input = parameters._reflect_input
        self._reflect_output = parameters._reflect_output
        self._xor_output = parameters._xor_output
        self._matrix_f, self._matrix_g = parameters._matrices()
        self._residue = parameters.residue()

        self.start = Signal()
        self.data = Signal(self._data_width)
        self.valid = Signal()
        self.crc = Signal(self._crc_width)
        self.match_detected = Signal()

    def elaborate(self, platform):
        m = Module()

        crc_reg = Signal(self._crc_width, reset=self._initial_crc.value)
        data_in = Signal(self._data_width)

        # Optionally bit-reflect input words.
        if self._reflect_input:
            m.d.comb += data_in.eq(self.data[::-1])
        else:
            m.d.comb += data_in.eq(self.data)

        # Optionally bit-reflect and then XOR the output.
        if self._reflect_output:
            m.d.comb += self.crc.eq(crc_reg[::-1] ^ self._xor_output)
        else:
            m.d.comb += self.crc.eq(crc_reg ^ self._xor_output)

        # Compute next CRC state.
        source = Mux(self.start, self._initial_crc, crc_reg)
        with m.If(self.valid):
            for i in range(self._crc_width):
                bit = 0
                for j in range(self._crc_width):
                    if self._matrix_f[j][i]:
                        bit ^= source[j]
                for j in range(self._data_width):
                    if self._matrix_g[j][i]:
                        bit ^= data_in[j]
                m.d.sync += crc_reg[i].eq(bit)
        with m.Elif(self.start):
            m.d.sync += crc_reg.eq(self._initial_crc)

        # Check for residue match, indicating a valid codeword.
        if self._reflect_output:
            m.d.comb += self.match_detected.eq(crc_reg[::-1] == self._residue)
        else:
            m.d.comb += self.match_detected.eq(crc_reg == self._residue)

        return m


# Imported after Algorithm is defined to prevent circular imports.
from . import catalog
