from ...hdl.ast import *
from ...hdl.xfrm import ResetInserter as NativeResetInserter
from ...hdl.xfrm import EnableInserter as NativeEnableInserter
from ...hdl.xfrm import DomainRenamer as NativeDomainRenamer


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


class CompatResetInserter(_CompatControlInserter):
    _control_name = "reset"
    _native_inserter = NativeResetInserter


class CompatCEInserter(_CompatControlInserter):
    _control_name = "ce"
    _native_inserter = NativeEnableInserter


ResetInserter = CompatResetInserter
CEInserter = CompatCEInserter
ClockDomainsRenamer = NativeDomainRenamer
