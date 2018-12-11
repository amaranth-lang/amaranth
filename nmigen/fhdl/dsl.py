from collections import OrderedDict

from .ast import *
from .ir import *
from .xfrm import *


__all__ = ["Module"]


class _ModuleBuilderProxy:
    def __init__(self, builder, depth):
        object.__setattr__(self, "_builder", builder)
        object.__setattr__(self, "_depth", depth)


class _ModuleBuilderComb(_ModuleBuilderProxy):
    def __iadd__(self, assigns):
        self._builder._add_statement(assigns, cd=None, depth=self._depth)
        return self


class _ModuleBuilderSyncCD(_ModuleBuilderProxy):
    def __init__(self, builder, depth, cd):
        super().__init__(builder, depth)
        self._cd = cd

    def __iadd__(self, assigns):
        self._builder._add_statement(assigns, cd=self._cd, depth=self._depth)
        return self


class _ModuleBuilderSync(_ModuleBuilderProxy):
    def __iadd__(self, assigns):
        self._builder._add_statement(assigns, cd="sys", depth=self._depth)
        return self

    def __getattr__(self, name):
        return _ModuleBuilderSyncCD(self._builder, self._depth, name)

    def __setattr__(self, name, value):
        if not isinstance(value, _ModuleBuilderSyncCD):
            raise AttributeError("Cannot assign sync.{} attribute - use += instead"
                                 .format(name))


class _ModuleBuilderRoot:
    def __init__(self, builder, depth):
        self._builder = builder
        self.comb = _ModuleBuilderComb(builder, depth)
        self.sync = _ModuleBuilderSync(builder, depth)

    def __setattr__(self, name, value):
        if name == "comb" and not isinstance(value, _ModuleBuilderComb):
            raise AttributeError("Cannot assign comb attribute - use += instead")
        if name == "sync" and not isinstance(value, _ModuleBuilderSync):
            raise AttributeError("Cannot assign sync attribute - use += instead")
        super().__setattr__(name, value)


class _ModuleBuilderIf(_ModuleBuilderRoot):
    def __init__(self, builder, depth, cond):
        super().__init__(builder, depth)
        self._cond = cond

    def __enter__(self):
        self._builder._flush()
        self._builder._stmt_if_cond.append(self._cond)
        self._outer_case = self._builder._statements
        self._builder._statements = []
        return self

    def __exit__(self, *args):
        self._builder._stmt_if_bodies.append(self._builder._statements)
        self._builder._statements = self._outer_case


class _ModuleBuilderElif(_ModuleBuilderRoot):
    def __init__(self, builder, depth, cond):
        super().__init__(builder, depth)
        self._cond = cond

    def __enter__(self):
        if not self._builder._stmt_if_cond:
            raise ValueError("Elif without preceding If")
        self._builder._stmt_if_cond.append(self._cond)
        self._outer_case = self._builder._statements
        self._builder._statements = []
        return self

    def __exit__(self, *args):
        self._builder._stmt_if_bodies.append(self._builder._statements)
        self._builder._statements = self._outer_case


class _ModuleBuilderElse(_ModuleBuilderRoot):
    def __init__(self, builder, depth):
        super().__init__(builder, depth)

    def __enter__(self):
        if not self._builder._stmt_if_cond:
            raise ValueError("Else without preceding If/Elif")
        self._builder._stmt_if_cond.append(1)
        self._outer_case = self._builder._statements
        self._builder._statements = []
        return self

    def __exit__(self, *args):
        self._builder._stmt_if_bodies.append(self._builder._statements)
        self._builder._statements = self._outer_case
        self._builder._flush()


class _ModuleBuilderCase(_ModuleBuilderRoot):
    def __init__(self, builder, depth, test, value):
        super().__init__(builder, depth)
        self._test  = test
        self._value = value

    def __enter__(self):
        if self._value is None:
            self._value = "-" * len(self._test)
        if isinstance(self._value, str) and len(self._test) != len(self._value):
            raise ValueError("Case value {} must have the same width as test {}"
                             .format(self._value, self._test))
        if self._builder._stmt_switch_test != ValueKey(self._test):
            self._builder._flush()
            self._builder._stmt_switch_test = ValueKey(self._test)
        self._outer_case = self._builder._statements
        self._builder._statements = []
        return self

    def __exit__(self, *args):
        self._builder._stmt_switch_cases[self._value] = self._builder._statements
        self._builder._statements = self._outer_case


class _ModuleBuilderSubmodules:
    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)

    def __iadd__(self, submodules):
        for submodule in submodules:
            self._builder._add_submodule(submodule)
        return self

    def __setattr__(self, name, submodule):
        self._builder._add_submodule(submodule, name)


class Module(_ModuleBuilderRoot):
    def __init__(self):
        _ModuleBuilderRoot.__init__(self, self, depth=0)
        self.submodules = _ModuleBuilderSubmodules(self)

        self._submodules        = []
        self._driving           = ValueDict()
        self._statements        = []
        self._stmt_depth        = 0
        self._stmt_if_cond      = []
        self._stmt_if_bodies    = []
        self._stmt_switch_test  = None
        self._stmt_switch_cases = OrderedDict()

    def If(self, cond):
        return _ModuleBuilderIf(self, self._stmt_depth + 1, cond)

    def Elif(self, cond):
        return _ModuleBuilderElif(self, self._stmt_depth + 1, cond)

    def Else(self):
        return _ModuleBuilderElse(self, self._stmt_depth + 1)

    def Case(self, test, value=None):
        return _ModuleBuilderCase(self, self._stmt_depth + 1, test, value)

    def _flush(self):
        if self._stmt_if_cond:
            tests, cases = [], OrderedDict()
            for if_cond, if_case in zip(self._stmt_if_cond, self._stmt_if_bodies):
                if_cond = Value.wrap(if_cond)
                if len(if_cond) != 1:
                    if_cond = if_cond.bool()
                tests.append(if_cond)

                match = ("1" + "-" * (len(tests) - 1)).rjust(len(self._stmt_if_cond), "-")
                cases[match] = if_case
            self._statements.append(Switch(Cat(tests), cases))

        if self._stmt_switch_test:
            self._statements.append(Switch(self._stmt_switch_test.value, self._stmt_switch_cases))

        self._stmt_if_cond      = []
        self._stmt_if_bodies    = []
        self._stmt_switch_test  = None
        self._stmt_switch_cases = OrderedDict()

    def _add_statement(self, assigns, cd, depth):
        def cd_name(cd):
            if cd is None:
                return "comb"
            else:
                return "sync.{}".format(cd)

        if depth < self._stmt_depth:
            self._flush()
        self._stmt_depth = depth

        for assign in Statement.wrap(assigns):
            if not isinstance(assign, Assign):
                raise TypeError("Only assignments can be appended to {}".format(self.cd_name(cd)))

            for signal in assign.lhs._lhs_signals():
                if signal not in self._driving:
                    self._driving[signal] = cd
                elif self._driving[signal] != cd:
                    cd_curr = self._driving[signal]
                    raise ValueError("Driver-driver conflict: trying to drive {!r} from {}, but "
                                     "it is already driven from {}"
                                     .format(signal, self.cd_name(cd), self.cd_name(cd_curr)))

            self._statements.append(assign)

    def _add_submodule(self, submodule, name=None):
        if not hasattr(submodule, "get_fragment"):
            raise TypeError("Trying to add {!r}, which does not have .get_fragment(), as "
                            " a submodule")
        self._submodules.append((submodule, name))

    def lower(self, platform):
        self._flush()

        fragment = Fragment()
        for submodule, name in self._submodules:
            fragment.add_subfragment(submodule.get_fragment(platform), name)
        fragment.add_statements(self._statements)
        for signal, cd_name in self._driving.items():
            for lhs_signal in signal._lhs_signals():
                fragment.drive(lhs_signal, cd_name)
        return fragment
