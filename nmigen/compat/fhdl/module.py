from collections import Iterable

from ...tools import flatten, deprecated
from ...fhdl import dsl


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
        self._cm._module._add_statement(assigns, cd_name=None, depth=0, compat_mode=True)
        return self


class _CompatModuleSyncCD:
    def __init__(self, cm, cd):
        self._cm = cm
        self._cd = cd

    @deprecated("instead of `self.sync.<domain> +=`, use `m.d.<domain> +=`")
    def __iadd__(self, assigns):
        self._cm._module._add_statement(assigns, cd_name=self._cd, depth=0, compat_mode=True)
        return self


class _CompatModuleSync(_CompatModuleProxy):
    @deprecated("instead of `self.sync +=`, use `m.d.sync +=`")
    def __iadd__(self, assigns):
        self._cm._module._add_statement(assigns, cd_name="sync", depth=0, compat_mode=True)
        return self

    def __getattr__(self, name):
        return _CompatModuleSyncCD(self._cm, name)

    def __setattr__(self, name, value):
        if not isinstance(value, _ModuleSyncCD):
            raise AttributeError("Attempted to assign sync property - use += instead")


class _CompatModuleForwardAttr:
    @deprecated("TODO")
    def __setattr__(self, name, value):
        self.__iadd__(value)
        setattr(self._cm, name, value)


class _CompatModuleSpecials(_CompatModuleProxy, _CompatModuleForwardAttr):
    @deprecated("TODO")
    def __iadd__(self, other):
        self._cm._fragment.specials |= set(_flat_list(other))
        return self


class _CompatModuleSubmodules(_CompatModuleProxy):
    @deprecated("TODO")
    def __setattr__(self, name, value):
        self._cm._submodules += [(name, e) for e in _flat_list(value)]
        setattr(self._cm, name, value)

    @deprecated("TODO")
    def __iadd__(self, other):
        self._cm._submodules += [(None, e) for e in _flat_list(other)]
        return self


class _CompatModuleClockDomains(_CompatModuleProxy, _CompatModuleForwardAttr):
    @deprecated("TODO")
    def __iadd__(self, other):
        self._cm._fragment.clock_domains += _flat_list(other)
        return self


class CompatModule:
    def get_fragment(self):
        assert not self.get_fragment_called
        self.get_fragment_called = True
        self.finalize()
        return self._fragment

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


Module = CompatModule
