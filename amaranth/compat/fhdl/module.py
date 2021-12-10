from collections.abc import Iterable

from ..._utils import flatten, deprecated
from ...hdl import dsl, ir


__all__ = ["Module", "FinalizeError"]


def _flat_list(e):
    if isinstance(e, Iterable):
        return list(flatten(e))
    else:
        return [e]


class CompatFinalizeError(Exception):
    pass


FinalizeError = CompatFinalizeError


class _CompatModuleProxy:
    def __init__(self, cm):
        object.__setattr__(self, "_cm", cm)


class _CompatModuleComb(_CompatModuleProxy):
    @deprecated("instead of `self.comb +=`, use `m.d.comb +=`")
    def __iadd__(self, assigns):
        self._cm._module._add_statement(assigns, domain=None, depth=0, compat_mode=True)
        return self


class _CompatModuleSyncCD:
    def __init__(self, cm, cd):
        self._cm = cm
        self._cd = cd

    @deprecated("instead of `self.sync.<domain> +=`, use `m.d.<domain> +=`")
    def __iadd__(self, assigns):
        self._cm._module._add_statement(assigns, domain=self._cd, depth=0, compat_mode=True)
        return self


class _CompatModuleSync(_CompatModuleProxy):
    @deprecated("instead of `self.sync +=`, use `m.d.sync +=`")
    def __iadd__(self, assigns):
        self._cm._module._add_statement(assigns, domain="sync", depth=0, compat_mode=True)
        return self

    def __getattr__(self, name):
        return _CompatModuleSyncCD(self._cm, name)

    def __setattr__(self, name, value):
        if not isinstance(value, _CompatModuleSyncCD):
            raise AttributeError("Attempted to assign sync property - use += instead")


class _CompatModuleSpecials(_CompatModuleProxy):
    @deprecated("instead of `self.specials.<name> =`, use `m.submodules.<name> =`")
    def __setattr__(self, name, value):
        self._cm._submodules.append((name, value))
        setattr(self._cm, name, value)

    @deprecated("instead of `self.specials +=`, use `m.submodules +=`")
    def __iadd__(self, other):
        self._cm._submodules += [(None, e) for e in _flat_list(other)]
        return self


class _CompatModuleSubmodules(_CompatModuleProxy):
    @deprecated("instead of `self.submodules.<name> =`, use `m.submodules.<name> =`")
    def __setattr__(self, name, value):
        self._cm._submodules.append((name, value))
        setattr(self._cm, name, value)

    @deprecated("instead of `self.submodules +=`, use `m.submodules +=`")
    def __iadd__(self, other):
        self._cm._submodules += [(None, e) for e in _flat_list(other)]
        return self


class _CompatModuleClockDomains(_CompatModuleProxy):
    @deprecated("instead of `self.clock_domains.<name> =`, use `m.domains.<name> =`")
    def __setattr__(self, name, value):
        self.__iadd__(value)
        setattr(self._cm, name, value)

    @deprecated("instead of `self.clock_domains +=`, use `m.domains +=`")
    def __iadd__(self, other):
        self._cm._module.domains += _flat_list(other)
        return self


class CompatModule(ir.Elaboratable):
    _MustUse__silence = True

    # Actually returns another Amaranth Elaboratable (amaranth.dsl.Module), not a Fragment.
    def get_fragment(self):
        assert not self.get_fragment_called
        self.get_fragment_called = True
        self.finalize()
        return self._module

    def elaborate(self, platform):
        if not self.get_fragment_called:
            self.get_fragment()
        return self._module

    def __getattr__(self, name):
        if name == "comb":
            return _CompatModuleComb(self)
        elif name == "sync":
            return _CompatModuleSync(self)
        elif name == "specials":
            return _CompatModuleSpecials(self)
        elif name == "submodules":
            return _CompatModuleSubmodules(self)
        elif name == "clock_domains":
            return _CompatModuleClockDomains(self)
        elif name == "finalized":
            self.finalized = False
            return self.finalized
        elif name == "_module":
            self._module = dsl.Module()
            return self._module
        elif name == "_submodules":
            self._submodules = []
            return self._submodules
        elif name == "_clock_domains":
            self._clock_domains = []
            return self._clock_domains
        elif name == "get_fragment_called":
            self.get_fragment_called = False
            return self.get_fragment_called
        else:
            raise AttributeError("'{}' object has no attribute '{}'"
                                 .format(type(self).__name__, name))

    def finalize(self, *args, **kwargs):
        def finalize_submodules():
            for name, submodule in self._submodules:
                if not hasattr(submodule, "finalize"):
                    continue
                if submodule.finalized:
                    continue
                submodule.finalize(*args, **kwargs)

        if not self.finalized:
            self.finalized = True
            finalize_submodules()
            self.do_finalize(*args, **kwargs)
            finalize_submodules()
            for name, submodule in self._submodules:
                self._module._add_submodule(submodule, name)

    def do_finalize(self):
        pass


Module = CompatModule
