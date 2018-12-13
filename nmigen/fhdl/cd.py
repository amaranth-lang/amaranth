from .. import tracer
from .ast import Signal


__all__ = ["ClockDomain"]


class ClockDomain:
    """Synchronous domain.

    Parameters
    ----------
    name : str or None
        Domain name. If ``None`` (the default) the name is inferred from the variable name this
        ``ClockDomain`` is assigned to (stripping any `"cd_"` prefix).
    reset_less : bool
        If ``True``, the domain does not use a reset signal. Registers within this domain are
        still all initialized to their reset state once, e.g. through Verilog `"initial"`
        statements.
    async_reset : bool
        If ``True``, the domain uses an asynchronous reset, and registers within this domain
        are initialized to their reset state when reset level changes. Otherwise, registers
        are initialized to reset state at the next clock cycle when reset is asserted.

    Attributes
    ----------
    clk : Signal, inout
        The clock for this domain. Can be driven or used to drive other signals (preferably
        in combinatorial context).
    rst : Signal or None, inout
        Reset signal for this domain. Can be driven or used to drive.
    """
    def __init__(self, name=None, reset_less=False, async_reset=False):
        if name is None:
            try:
                name = tracer.get_var_name()
            except tracer.NameNotFound:
                raise ValueError("Clock domain name must be specified explicitly")
        if name.startswith("cd_"):
            name = name[3:]
        self.name = name

        self.clk = Signal(name=self.name + "_clk", src_loc_at=1)
        if reset_less:
            self.rst = None
        else:
            self.rst = Signal(name=self.name + "_rst", src_loc_at=1)

        self.async_reset = async_reset
