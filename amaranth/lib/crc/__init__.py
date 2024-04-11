import operator
from ... import *


__all__ = ["Algorithm", "Parameters", "Processor", "catalog"]


class Algorithm:
    """Essential parameters for cyclic redundancy check computation.

    The parameter set is based on the Williams model from `"A Painless Guide to CRC Error Detection
    Algorithms" <http://www.ross.net/crc/download/crc_v3.txt>`_.

    For a reference of standard CRC parameter sets, refer to:

    * `reveng`_'s catalogue, which uses an identical parameterisation;
    * `crcmod`_'s list of predefined functions, but remove the leading '1' from the polynominal,
      XOR the "Init-value" with "XOR-out" to obtain :py:`initial_crc`, and where "Reversed" is
      :py:`True`, set both :py:`reflect_input` and :py:`reflect_output` to :py:`True`;
    * `CRC Zoo`_, which contains only polynomials; use the "explicit +1" form of polynomial but
      remove the leading '1'.

    .. _reveng: https://reveng.sourceforge.io/crc-catalogue/all.htm
    .. _crcmod: https://crcmod.sourceforge.net/crcmod.predefined.html
    .. _CRC Zoo: https://users.ece.cmu.edu/~koopman/crc/

    Many commonly used CRC algorithms are available in the :py:mod:`~amaranth.lib.crc.catalog`
    module, which includes all entries in the `reveng catalogue <reveng_>`_.

    The essential parameters on their own cannot be used to perform CRC computation, and must be
    combined with a specific data word width. This can be done using :py:`algo(data_width)`, which
    returns a :class:`Parameters` object.

    Parameters
    ----------
    crc_width : :class:`int`
        Bit width of CRC word. Also known as "width" in the Williams model.
    polynomial : :class:`int`
        CRC polynomial to use, :py:`crc_width` bits long, without the implicit :py:`x ** crc_width`
        term. Polynomial is always specified with the highest order terms in the most significant
        bit positions; use :py:`reflect_input` and :py:`reflect_output` to perform a least
        significant bit first computation.
    initial_crc : :class:`int`
        Initial value of CRC register at reset. Most significant bit always corresponds to
        the highest order term in the CRC register.
    reflect_input : :class:`bool`
        If :py:`True`, the input data words are bit-reflected, so that they are processed least
        significant bit first.
    reflect_output : :class:`bool`
        If :py:`True`, the output CRC is bit-reflected, so that the least-significant bit of
        the output is the highest-order bit of the CRC register. Note that this reflection is
        performed over the entire CRC register; for transmission you may want to treat the output
        as a little-endian multi-word value, so for example the reflected 16-bit output :py:`0x4E4C`
        would be transmitted as the two octets :py:`0x4C, 0x4E`, each transmitted least significant
        bit first.
    xor_output : :class:`int`
        The output CRC will be the CRC register XOR'd with this value, applied after any output
        bit-reflection.
    """
    def __init__(self, *, crc_width, polynomial, initial_crc, reflect_input,
                 reflect_output, xor_output):
        self.crc_width = operator.index(crc_width)
        self.polynomial = operator.index(polynomial)
        self.initial_crc = operator.index(initial_crc)
        self.reflect_input = bool(reflect_input)
        self.reflect_output = bool(reflect_output)
        self.xor_output = operator.index(xor_output)

        if not self.crc_width > 0:
            raise ValueError("CRC width must be greater than 0")
        if self.polynomial not in range(2 ** self.crc_width):
            raise ValueError("Polynomial must be between 0 and (2 ** crc_width - 1)")
        if self.initial_crc not in range(2 ** self.crc_width):
            raise ValueError("Initial CRC must be between 0 and (2 ** crc_width - 1)")
        if self.xor_output not in range(2 ** self.crc_width):
            raise ValueError("XOR output must be between 0 and (2 ** crc_width - 1)")

    def __call__(self, data_width=8):
        """Combine these essential parameters with a data word width to form complete parameters.

        Returns
        -------
        :class:`Parameters`
            :py:`Parameters(self, data_width)`
        """
        return Parameters(self, data_width)

    def __repr__(self):
        return (f"Algorithm(crc_width={self.crc_width}, "
            f"polynomial=0x{self.polynomial:0{self.crc_width // 4}x}, "
            f"initial_crc=0x{self.initial_crc:0{self.crc_width // 4}x}, "
            f"reflect_input={self.reflect_input}, "
            f"reflect_output={self.reflect_output}, "
            f"xor_output=0x{self.xor_output:0{self.crc_width // 4}x})")


class Parameters:
    """Complete parameters for cyclic redundancy check computation.

    Contains the essential :class:`Algorithm` parameters, plus the data word width.

    A :class:`Parameters` object can be used to directly compute CRCs using
    the :meth:`~Parameters.compute` method, or to construct a hardware module using
    the :meth:`~Parameters.create` method.

    Parameters
    ----------
    algorithm : :class:`Algorithm`
        CRC algorithm to use. Specifies the CRC width, polynomial, initial value, whether to
        reflect the input or output words, and any output XOR.
    data_width : :class:`int`
        Bit width of data words.
    """
    def __init__(self, algorithm, data_width=8):
        self._crc_width = algorithm.crc_width
        self._polynomial = algorithm.polynomial
        self._initial_crc = algorithm.initial_crc
        self._reflect_input = algorithm.reflect_input
        self._reflect_output = algorithm.reflect_output
        self._xor_output = algorithm.xor_output
        self.data_width = operator.index(data_width)
        if not self.data_width > 0:
            raise ValueError("Data width must be greater than 0")

    @property
    def algorithm(self):
        return Algorithm(
            crc_width=self._crc_width,
            polynomial=self._polynomial,
            initial_crc=self._initial_crc,
            reflect_input=self._reflect_input,
            reflect_output=self._reflect_output,
            xor_output=self._xor_output)

    def residue(self):
        """Obtain the residual value left in the CRC register after processing a valid trailing CRC."""
        # Residue is computed by initialising to (possibly reflected) xor_output, feeding crc_width
        # worth of 0 bits, then taking the (possibly reflected) output without any XOR.
        if self._reflect_output:
            init = self._reflect(self._xor_output, self._crc_width)
        else:
            init = self._xor_output
        algo = self.algorithm
        algo.initial_crc = init
        algo.reflect_input = False
        algo.xor_output = 0
        return algo(self._crc_width).compute([0])

    def compute(self, data):
        """Compute the CRC of all data words in :py:`data`.

        Parameters
        ----------
        data : iterable of :class:`int`
            Data words, each of which is :py:`data_width` bits wide.
        """
        # Precompute some constants we use every iteration.
        word_max = (1 << self.data_width) - 1
        top_bit = 1 << (self._crc_width + self.data_width - 1)
        crc_mask = (1 << (self._crc_width + self.data_width)) - 1
        poly_shifted = self._polynomial << self.data_width

        # Implementation notes:
        # We always compute most-significant bit first, which means the polynomial and initial
        # value may be used as-is, and the reflect_in and reflect_out values have their usual sense.
        # However, when computing word-at-a-time and MSbit-first, we must align the input word so
        # its MSbit lines up with the MSbit of the previous CRC value. When the CRC width is smaller
        # than the word width, this would normally truncate data bits. Instead, we shift the initial
        # CRC left by the data width, and the data word left by the crc width, lining up their
        # MSbits no matter the relation between the two widths. The new CRC is then shifted right by
        # the data width before output.

        crc = self._initial_crc << self.data_width
        for word in data:
            if not 0 <= word <= word_max:
                raise ValueError(f"data word must be between 0 and {word_max - 1}")

            if self._reflect_input:
                word = self._reflect(word, self.data_width)

            crc ^= word << self._crc_width
            for _ in range(self.data_width):
                if crc & top_bit:
                    crc = (crc << 1) ^ poly_shifted
                else:
                    crc <<= 1
            crc &= crc_mask

        crc >>= self.data_width
        if self._reflect_output:
            crc = self._reflect(crc, self._crc_width)

        crc ^= self._xor_output
        return crc

    def create(self):
        """Create a hardware CRC generator with these parameters.

        Returns
        -------
        :class:`Processor`
            :py:`Processor(self)`
        """
        return Processor(self)

    @staticmethod
    def _reflect(word, n):
        """Bitwise-reflect an :py:`n`-bit word :py:`word`."""
        return int(f"{word:0{n}b}"[::-1], 2)

    def _matrices(self):
        """Compute the F and G matrices for parallel CRC computation.

        Computes the F and G matrices for parallel CRC computation, treating the CRC as a linear
        time-invariant system described by the state relation x(t+1) = F.x(i) + G.u(i), where x(i)
        and u(i) are column vectors of the bits of the CRC register and input word, F is the n-by-n
        matrix relating the old state to the new state, and G is the n-by-m matrix relating the new
        data to the new state, where n is the CRC width and m is the data word width.

        The matrices are ordered least-significant-bit first; in other words the first entry, with
        index (0, 0), corresponds to the effect of the least-significant bit of the input on
        the least-significant bit of the output.

        For convenience of implementation, both matrices are returned transposed: the first index
        is the input bit, and the second index is the corresponding output bit.

        The matrices are used to select which bits are XORd together to compute each bit i of
        the new state: if F[j][i] is set then bit j of the old state is included in the XOR, and
        if G[j][i] is set then bit j of the new data is included.

        These matrices are not affected by :py:`initial_crc`, :py:`reflect_input`,
        :py:`reflect_output`, or :py:`xor_output`.
        """
        f = []
        g = []
        algo = self.algorithm
        algo.reflect_input = algo.reflect_output = False
        algo.xor_output = 0
        crc = Parameters(algo, self.data_width)
        for i in range(self._crc_width):
            crc._initial_crc = 2 ** i
            w = crc.compute([0])
            f.append([int(x) for x in reversed(f"{w:0{self._crc_width}b}")])
        for i in range(self.data_width):
            crc._initial_crc = 0
            w = crc.compute([2 ** i])
            g.append([int(x) for x in reversed(f"{w:0{self._crc_width}b}")])
        return f, g

    def __repr__(self):
        return f"Parameters({self.algorithm!r}, data_width={self.data_width})"


class Processor(Elaboratable):
    """Hardware cyclic redundancy check generator.

    This module generates CRCs from an input data stream, which can be used to validate an existing
    CRC or generate a new CRC. It is configured by the :class:`Parameters` class, which can handle
    most types of CRCs.

    The CRC value is updated on any clock cycle where :py:`valid` is asserted, with the updated
    value available on the :py:`crc` output on the subsequent clock cycle. The latency is therefore
    one clock cycle, and the throughput is one data word per clock cycle.

    The CRC is reset to its initial value whenever :py:`start` is asserted. :py:`start` and
    :py:`valid` may be asserted on the same clock cycle, in which case a new CRC computation is
    started with the current value of `data`.

    When :py:`data_width` is 1, a classic bit-serial CRC is implemented for the given polynomial
    in a Galois-type shift register. For larger values of :py:`data_width`, a similar architecture
    computes every new bit of the CRC in parallel.

    The :py:`match_detected` output may be used to validate data with a trailing CRC (also known as
    a codeword in coding theory). If the most recently processed data word(s) form the valid CRC of
    all the previous data words since :py:`start` was asserted, the CRC register will always take on
    a fixed value known as the :meth:`residue <Parameters.residue>`. The :py:`match_detected` output
    indicates whether the CRC register currently contains this residue.

    Parameters
    ----------
    parameters : :class:`Parameters`
        Parameters used for computation.

    Attributes
    ----------
    start : Signal(), in
        Assert to indicate the start of a CRC computation, re-initialising the CRC register to
        the initial value. May be asserted simultaneously with :py:`valid` or by itself.
    data : Signal(data_width), in
        Data word to add to CRC when :py:`valid` is asserted.
    valid : Signal(), in
        Assert when :py:`data` is valid to add the data word to the CRC.
    crc : Signal(crc_width), out
        Registered CRC output value, updated one clock cycle after :py:`valid` becomes asserted.
    match_detected : Signal(), out
        Asserted if the current CRC value indicates a valid codeword has been received.
    """
    def __init__(self, parameters):
        if not isinstance(parameters, Parameters):
            raise TypeError("Algorithm parameters must be of a Parameters instance, "
                            "not {!r}"
                            .format(parameters))
        self._crc_width = parameters._crc_width
        self._data_width = parameters.data_width
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

        crc_reg = Signal(self._crc_width, init=self._initial_crc.value)
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
