from .. import tracer
from ._ast import Signal


__all__ = ["ClockDomain", "DomainError"]


class DomainError(Exception):
    pass


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
    clk_edge : str
        The edge of the clock signal on which signals are sampled. Must be one of "pos" or "neg".
    async_reset : bool
        If ``True``, the domain uses an asynchronous reset, and registers within this domain
        are initialized to their reset state when reset level changes. Otherwise, registers
        are initialized to reset state at the next clock cycle when reset is asserted.
    local : bool
        If ``True``, the domain will propagate only downwards in the design hierarchy. Otherwise,
        the domain will propagate everywhere.

    Attributes
    ----------
    clk : Signal, inout
        The clock for this domain. Can be driven or used to drive other signals (preferably
        in combinational context).
    rst : Signal or None, inout
        Reset signal for this domain. Can be driven or used to drive.
    """

    @staticmethod
    def _name_for(domain_name, signal_name):
        if domain_name == "sync":
            return signal_name
        else:
            return f"{domain_name}_{signal_name}"

    def __init__(self, name=None, *, clk_edge="pos", reset_less=False, async_reset=False,
                 local=False):
        if name is None:
            try:
                name = tracer.get_var_name()
            except tracer.NameNotFound:
                raise ValueError("Clock domain name must be specified explicitly")
        if name.startswith("cd_"):
            name = name[3:]
        if name == "comb":
            raise ValueError(f"Domain '{name}' may not be clocked")

        if clk_edge not in ("pos", "neg"):
            raise ValueError("Domain clock edge must be one of 'pos' or 'neg', not {!r}"
                             .format(clk_edge))

        self.name = name

        self.clk = Signal(name=self._name_for(name, "clk"), src_loc_at=1)
        self.clk_edge = clk_edge

        if reset_less:
            self.rst = None
        else:
            self.rst = Signal(name=self._name_for(name, "rst"), src_loc_at=1)

        self.async_reset = async_reset

        self.local = local

    def rename(self, new_name):
        self.name = new_name
        self.clk.name = self._name_for(new_name, "clk")
        if self.rst is not None:
            self.rst.name = self._name_for(new_name, "rst")
