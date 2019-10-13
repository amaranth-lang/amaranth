from .._utils import deprecated
from .. import *


__all__ = ["FFSynchronizer", "ResetSynchronizer"]
# TODO(nmigen-0.2): remove this
__all__ += ["MultiReg"]


def _check_stages(stages):
    if not isinstance(stages, int) or stages < 1:
        raise TypeError("Synchronization stage count must be a positive integer, not {!r}"
                        .format(stages))
    if stages < 2:
        raise ValueError("Synchronization stage count may not safely be less than 2")


class FFSynchronizer(Elaboratable):
    """Resynchronise a signal to a different clock domain.

    Consists of a chain of flip-flops. Eliminates metastabilities at the output, but provides
    no other guarantee as to the safe domain-crossing of a signal.

    Parameters
    ----------
    i : Signal(n), in
        Signal to be resynchronised.
    o : Signal(n), out
        Signal connected to synchroniser output.
    o_domain : str
        Name of output clock domain.
    reset : int
        Reset value of the flip-flops. On FPGAs, even if ``reset_less`` is True,
        the :class:`FFSynchronizer` is still set to this value during initialization.
    reset_less : bool
        If ``True`` (the default), this :class:`FFSynchronizer` is unaffected by ``o_domain``
        reset. See "Note on Reset" below.
    stages : int
        Number of synchronization stages between input and output. The lowest safe number is 2,
        with higher numbers reducing MTBF further, at the cost of increased latency.
    max_input_delay : None or float
        Maximum delay from the input signal's clock to the first synchronization stage, in seconds.
        If specified and the platform does not support it, elaboration will fail.

    Platform override
    -----------------
    Define the ``get_ff_sync`` platform method to override the implementation of
    :class:`FFSynchronizer`, e.g. to instantiate library cells directly.

    Note on Reset
    -------------
    :class:`FFSynchronizer` is non-resettable by default. Usually this is the safest option;
    on FPGAs the :class:`FFSynchronizer` will still be initialized to its ``reset`` value when
    the FPGA loads its configuration.

    However, in designs where the value of the :class:`FFSynchronizer` must be valid immediately
    after reset, consider setting ``reset_less`` to False if any of the following is true:

    - You are targeting an ASIC, or an FPGA that does not allow arbitrary initial flip-flop states;
    - Your design features warm (non-power-on) resets of ``o_domain``, so the one-time
      initialization at power on is insufficient;
    - Your design features a sequenced reset, and the :class:`FFSynchronizer` must maintain
      its reset value until ``o_domain`` reset specifically is deasserted.

    :class:`FFSynchronizer` is reset by the ``o_domain`` reset only.
    """
    def __init__(self, i, o, *, o_domain="sync", reset=0, reset_less=True, stages=2,
                 max_input_delay=None):
        _check_stages(stages)

        self.i = i
        self.o = o

        self._reset      = reset
        self._reset_less = reset_less
        self._o_domain   = o_domain
        self._stages     = stages

        self._max_input_delay = max_input_delay

    def elaborate(self, platform):
        if hasattr(platform, "get_ff_sync"):
            return platform.get_ff_sync(self)

        if self._max_input_delay is not None:
            raise NotImplementedError("Platform '{}' does not support constraining input delay "
                                      "for FFSynchronizer"
                                      .format(type(platform).__name__))

        m = Module()
        flops = [Signal(self.i.shape(), name="stage{}".format(index),
                        reset=self._reset, reset_less=self._reset_less)
                 for index in range(self._stages)]
        for i, o in zip((self.i, *flops), flops):
            m.d[self._o_domain] += o.eq(i)
        m.d.comb += self.o.eq(flops[-1])
        return m


# TODO(nmigen-0.2): remove this
MultiReg = deprecated("instead of `MultiReg`, use `FFSynchronizer`")(FFSynchronizer)


class ResetSynchronizer(Elaboratable):
    """Synchronize deassertion of a clock domain reset.

    The reset of the clock domain driven by the :class:`ResetSynchronizer` is asserted
    asynchronously and deasserted synchronously, eliminating metastability during deassertion.

    The driven clock domain could use a reset that is asserted either synchronously or
    asynchronously; a reset is always deasserted synchronously. A domain with an asynchronously
    asserted reset is useful if the clock of the domain may be gated, yet the domain still
    needs to be reset promptly; otherwise, synchronously asserted reset (the default) should
    be used.

    Parameters
    ----------
    arst : Signal(1), out
        Asynchronous reset signal, to be synchronized.
    domain : str
        Name of clock domain to reset.
    stages : int, >=2
        Number of synchronization stages between input and output. The lowest safe number is 2,
        with higher numbers reducing MTBF further, at the cost of increased deassertion latency.
    max_input_delay : None or float
        Maximum delay from the input signal's clock to the first synchronization stage, in seconds.
        If specified and the platform does not support it, elaboration will fail.

    Platform override
    -----------------
    Define the ``get_reset_sync`` platform method to override the implementation of
    :class:`ResetSynchronizer`, e.g. to instantiate library cells directly.
    """
    def __init__(self, arst, *, domain="sync", stages=2, max_input_delay=None):
        _check_stages(stages)

        self.arst = arst

        self._domain = domain
        self._stages = stages

        self._max_input_delay = None

    def elaborate(self, platform):
        if hasattr(platform, "get_reset_sync"):
            return platform.get_reset_sync(self)

        if self._max_input_delay is not None:
            raise NotImplementedError("Platform '{}' does not support constraining input delay "
                                      "for ResetSynchronizer"
                                      .format(type(platform).__name__))

        m = Module()
        m.domains += ClockDomain("reset_sync", async_reset=True, local=True)
        flops = [Signal(1, name="stage{}".format(index), reset=1)
                 for index in range(self._stages)]
        for i, o in zip((0, *flops), flops):
            m.d.reset_sync += o.eq(i)
        m.d.comb += [
            ClockSignal("reset_sync").eq(ClockSignal(self._domain)),
            ResetSignal("reset_sync").eq(self.arst),
            ResetSignal(self._domain).eq(flops[-1])
        ]
        return m
