from ...hdl.ast import *
from ...hdl.xfrm import ResetInserter as NativeResetInserter
from ...hdl.xfrm import EnableInserter as NativeEnableInserter
from ...hdl.xfrm import DomainRenamer as NativeDomainRenamer
from ..._utils import deprecated


__all__ = ["ResetInserter", "CEInserter", "ClockDomainsRenamer"]


class _CompatControlInserter:
    _control_name = None
    _native_inserter = None

    def __init__(self, clock_domains=None):
        self.clock_domains = clock_domains

    def __call__(self, module):
        if self.clock_domains is None:
            signals = {self._control_name: ("sync", Signal(name=self._control_name))}
        else:
            def name(cd):
                return self._control_name + "_" + cd
            signals = {name(cd): (cd, Signal(name=name(cd))) for cd in self.clock_domains}
        for name, (cd, signal) in signals.items():
            setattr(module, name, signal)
        return self._native_inserter(dict(signals.values()))(module)


@deprecated("instead of `migen.fhdl.decorators.ResetInserter`, "
            "use `amaranth.hdl.xfrm.ResetInserter`; note that Amaranth ResetInserter accepts "
            "a dict of reset signals (or a single reset signal) as an argument, not "
            "a set of clock domain names (or a single clock domain name)")
class CompatResetInserter(_CompatControlInserter):
    _control_name = "reset"
    _native_inserter = NativeResetInserter


@deprecated("instead of `migen.fhdl.decorators.CEInserter`, "
            "use `amaranth.hdl.xfrm.EnableInserter`; note that Amaranth EnableInserter accepts "
            "a dict of enable signals (or a single enable signal) as an argument, not "
            "a set of clock domain names (or a single clock domain name)")
class CompatCEInserter(_CompatControlInserter):
    _control_name = "ce"
    _native_inserter = NativeEnableInserter


class CompatClockDomainsRenamer(NativeDomainRenamer):
    def __init__(self, cd_remapping):
        super().__init__(cd_remapping)


ResetInserter = CompatResetInserter
CEInserter = CompatCEInserter
ClockDomainsRenamer = CompatClockDomainsRenamer
