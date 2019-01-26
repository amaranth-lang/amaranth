from collections import OrderedDict, namedtuple
from collections.abc import Iterable
from contextlib import contextmanager
import warnings

from ..tools import flatten, bits_for, deprecated
from .ast import *
from .ir import *
from .xfrm import *


__all__ = ["Module", "SyntaxError", "SyntaxWarning"]


class SyntaxError(Exception):
    pass


class SyntaxWarning(Warning):
    pass


class _ModuleBuilderProxy:
    def __init__(self, builder, depth):
        object.__setattr__(self, "_builder", builder)
        object.__setattr__(self, "_depth", depth)


class _ModuleBuilderDomainExplicit(_ModuleBuilderProxy):
    def __init__(self, builder, depth, domain):
        super().__init__(builder, depth)
        self._domain = domain

    def __iadd__(self, assigns):
        self._builder._add_statement(assigns, domain=self._domain, depth=self._depth)
        return self


class _ModuleBuilderDomainImplicit(_ModuleBuilderProxy):
    def __getattr__(self, name):
        if name == "comb":
            domain = None
        else:
            domain = name
        return _ModuleBuilderDomainExplicit(self._builder, self._depth, domain)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        if name == "_depth":
            object.__setattr__(self, name, value)
        elif not isinstance(value, _ModuleBuilderDomainExplicit):
            raise AttributeError("Cannot assign 'd.{}' attribute; did you mean 'd.{} +='?"
                                 .format(name, name))

    def __setitem__(self, name, value):
        return self.__setattr__(name, value)


class _ModuleBuilderRoot:
    def __init__(self, builder, depth):
        self._builder = builder
        self.domain = self.d = _ModuleBuilderDomainImplicit(builder, depth)

    def __getattr__(self, name):
        if name in ("comb", "sync"):
            raise AttributeError("'{}' object has no attribute '{}'; did you mean 'd.{}'?"
                                 .format(type(self).__name__, name, name))
        raise AttributeError("'{}' object has no attribute '{}'"
                             .format(type(self).__name__, name))


class _ModuleBuilderSubmodules:
    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)

    def __iadd__(self, modules):
        for module in flatten([modules]):
            self._builder._add_submodule(module)
        return self

    def __setattr__(self, name, submodule):
        self._builder._add_submodule(submodule, name)


class _ModuleBuilderDomainSet:
    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)

    def __iadd__(self, domains):
        for domain in flatten([domains]):
            self._builder._add_domain(domain)
        return self

    def __setattr__(self, name, domain):
        self._builder._add_domain(domain)


class FSM:
    def __init__(self, state, encoding, decoding):
        self.state    = state
        self.encoding = encoding
        self.decoding = decoding

    def ongoing(self, name):
        if name not in self.encoding:
            self.encoding[name] = len(self.encoding)
        return self.state == self.encoding[name]


class Module(_ModuleBuilderRoot):
    def __init__(self):
        _ModuleBuilderRoot.__init__(self, self, depth=0)
        self.submodules    = _ModuleBuilderSubmodules(self)
        self.domains       = _ModuleBuilderDomainSet(self)

        self._statements   = Statement.wrap([])
        self._ctrl_context = None
        self._ctrl_stack   = []

        self._driving      = SignalDict()
        self._submodules   = []
        self._domains      = []
        self._generated    = {}

    def _check_context(self, construct, context):
        if self._ctrl_context != context:
            if self._ctrl_context is None:
                raise SyntaxError("{} is not permitted outside of {}"
                                  .format(construct, context))
            else:
                raise SyntaxError("{} is not permitted inside of {}"
                                  .format(construct, self._ctrl_context))

    def _get_ctrl(self, name):
        if self._ctrl_stack:
            top_name, top_data = self._ctrl_stack[-1]
            if top_name == name:
                return top_data

    def _flush_ctrl(self):
        while len(self._ctrl_stack) > self.domain._depth:
            self._pop_ctrl()

    def _set_ctrl(self, name, data):
        self._flush_ctrl()
        self._ctrl_stack.append((name, data))
        return data

    @contextmanager
    def If(self, cond):
        self._check_context("If", context=None)
        if_data = self._set_ctrl("If", {"tests": [], "bodies": []})
        try:
            _outer_case, self._statements = self._statements, []
            self.domain._depth += 1
            yield
            self._flush_ctrl()
            if_data["tests"].append(cond)
            if_data["bodies"].append(self._statements)
        finally:
            self.domain._depth -= 1
            self._statements = _outer_case

    @contextmanager
    def Elif(self, cond):
        self._check_context("Elif", context=None)
        if_data = self._get_ctrl("If")
        if if_data is None:
            raise SyntaxError("Elif without preceding If")
        try:
            _outer_case, self._statements = self._statements, []
            self.domain._depth += 1
            yield
            self._flush_ctrl()
            if_data["tests"].append(cond)
            if_data["bodies"].append(self._statements)
        finally:
            self.domain._depth -= 1
            self._statements = _outer_case

    @contextmanager
    def Else(self):
        self._check_context("Else", context=None)
        if_data = self._get_ctrl("If")
        if if_data is None:
            raise SyntaxError("Else without preceding If/Elif")
        try:
            _outer_case, self._statements = self._statements, []
            self.domain._depth += 1
            yield
            self._flush_ctrl()
            if_data["bodies"].append(self._statements)
        finally:
            self.domain._depth -= 1
            self._statements = _outer_case
        self._pop_ctrl()

    @contextmanager
    def Switch(self, test):
        self._check_context("Switch", context=None)
        switch_data = self._set_ctrl("Switch", {"test": Value.wrap(test), "cases": OrderedDict()})
        try:
            self._ctrl_context = "Switch"
            self.domain._depth += 1
            yield
        finally:
            self.domain._depth -= 1
            self._ctrl_context = None
        self._pop_ctrl()

    @contextmanager
    def Case(self, value=None):
        self._check_context("Case", context="Switch")
        switch_data = self._get_ctrl("Switch")
        if value is None:
            value = "-" * len(switch_data["test"])
        if isinstance(value, str) and len(value) != len(switch_data["test"]):
            raise SyntaxError("Case value '{}' must have the same width as test (which is {})"
                              .format(value, len(switch_data["test"])))
        omit_case = False
        if isinstance(value, int) and bits_for(value) > len(switch_data["test"]):
            warnings.warn("Case value '{:b}' is wider than test (which has width {}); "
                          "comparison will never be true"
                          .format(value, len(switch_data["test"])), SyntaxWarning, stacklevel=3)
            omit_case = True
        try:
            _outer_case, self._statements = self._statements, []
            self._ctrl_context = None
            yield
            self._flush_ctrl()
            if not omit_case:
                switch_data["cases"][value] = self._statements
        finally:
            self._ctrl_context = "Switch"
            self._statements = _outer_case

    @contextmanager
    def FSM(self, reset=None, domain="sync", name="fsm"):
        self._check_context("FSM", context=None)
        fsm_data = self._set_ctrl("FSM", {
            "name":     name,
            "signal":   Signal(name="{}_state".format(name)),
            "reset":    reset,
            "domain":   domain,
            "encoding": OrderedDict(),
            "decoding": OrderedDict(),
            "states":   OrderedDict(),
        })
        self._generated[name] = fsm = \
            FSM(fsm_data["signal"], fsm_data["encoding"], fsm_data["decoding"])
        try:
            self._ctrl_context = "FSM"
            self.domain._depth += 1
            yield fsm
        finally:
            self.domain._depth -= 1
            self._ctrl_context = None
        self._pop_ctrl()

    @contextmanager
    def State(self, name):
        self._check_context("FSM State", context="FSM")
        fsm_data = self._get_ctrl("FSM")
        if name in fsm_data["states"]:
            raise SyntaxError("FSM state '{}' is already defined".format(name))
        if name not in fsm_data["encoding"]:
            fsm_data["encoding"][name] = len(fsm_data["encoding"])
        try:
            _outer_case, self._statements = self._statements, []
            self._ctrl_context = None
            yield
            self._flush_ctrl()
            fsm_data["states"][name] = self._statements
        finally:
            self._ctrl_context = "FSM"
            self._statements = _outer_case

    @property
    def next(self):
        raise SyntaxError("Only assignment to `m.next` is permitted")

    @next.setter
    def next(self, name):
        if self._ctrl_context != "FSM":
            for level, (ctrl_name, ctrl_data) in enumerate(reversed(self._ctrl_stack)):
                if ctrl_name == "FSM":
                    if name not in ctrl_data["encoding"]:
                        ctrl_data["encoding"][name] = len(ctrl_data["encoding"])
                    self._add_statement(
                        assigns=[ctrl_data["signal"].eq(ctrl_data["encoding"][name])],
                        domain=ctrl_data["domain"],
                        depth=len(self._ctrl_stack))
                    return

        raise SyntaxError("`m.next = <...>` is only permitted inside an FSM state")

    def _pop_ctrl(self):
        name, data = self._ctrl_stack.pop()

        if name == "If":
            if_tests, if_bodies = data["tests"], data["bodies"]

            tests, cases = [], OrderedDict()
            for if_test, if_case in zip(if_tests + [None], if_bodies):
                if if_test is not None:
                    if_test = Value.wrap(if_test)
                    if len(if_test) != 1:
                        if_test = if_test.bool()
                    tests.append(if_test)

                if if_test is not None:
                    match = ("1" + "-" * (len(tests) - 1)).rjust(len(if_tests), "-")
                else:
                    match = "-" * len(tests)
                cases[match] = if_case

            self._statements.append(Switch(Cat(tests), cases))

        if name == "Switch":
            switch_test, switch_cases = data["test"], data["cases"]

            self._statements.append(Switch(switch_test, switch_cases))

        if name == "FSM":
            fsm_signal, fsm_reset, fsm_encoding, fsm_decoding, fsm_states = \
                data["signal"], data["reset"], data["encoding"], data["decoding"], data["states"]
            fsm_signal.nbits = bits_for(len(fsm_encoding) - 1)
            if fsm_reset is None:
                fsm_signal.reset = fsm_encoding[next(iter(fsm_states))]
            else:
                fsm_signal.reset = fsm_encoding[fsm_reset]
            # The FSM is encoded such that the state with encoding 0 is always the reset state.
            fsm_decoding.update((n, s) for s, n in fsm_encoding.items())
            fsm_signal.decoder = lambda n: "{}/{}".format(fsm_decoding[n], n)
            self._statements.append(Switch(fsm_signal,
                OrderedDict((fsm_encoding[name], stmts) for name, stmts in fsm_states.items())))

    def _add_statement(self, assigns, domain, depth, compat_mode=False):
        def domain_name(domain):
            if domain is None:
                return "comb"
            else:
                return domain

        while len(self._ctrl_stack) > self.domain._depth:
            self._pop_ctrl()

        for assign in Statement.wrap(assigns):
            if not compat_mode and not isinstance(assign, (Assign, Assert, Assume)):
                raise SyntaxError(
                    "Only assignments, asserts, and assumes may be appended to d.{}"
                    .format(domain_name(domain)))

            assign = SampleDomainInjector(domain)(assign)
            for signal in assign._lhs_signals():
                if signal not in self._driving:
                    self._driving[signal] = domain
                elif self._driving[signal] != domain:
                    cd_curr = self._driving[signal]
                    raise SyntaxError(
                        "Driver-driver conflict: trying to drive {!r} from d.{}, but it is "
                        "already driven from d.{}"
                        .format(signal, domain_name(domain), domain_name(cd_curr)))

            self._statements.append(assign)

    def _add_submodule(self, submodule, name=None):
        if not hasattr(submodule, "elaborate"):
            if hasattr(submodule, "get_fragment"): # :deprecated:
                warnings.warn("Adding '{!r}', which implements .get_fragment() but not "
                              ".elaborate(), as a submodule. .get_fragment() is deprecated, "
                              "and .elaborate() should be provided instead.".format(submodule),
                              DeprecationWarning, stacklevel=2)
            else:
                raise TypeError("Trying to add '{!r}', which does not implement .elaborate(), as "
                                "a submodule".format(submodule))
        self._submodules.append((submodule, name))

    def _add_domain(self, cd):
        self._domains.append(cd)

    def _flush(self):
        while self._ctrl_stack:
            self._pop_ctrl()

    @deprecated("`m.get_fragment(...)` is deprecated; use `m` instead")
    def get_fragment(self, platform): # :deprecated:
        return self.elaborate(platform)

    @deprecated("`m.lower(...)` is deprecated; use `m` instead")
    def lower(self, platform): # :deprecated:
        return self.elaborate(platform)

    def elaborate(self, platform):
        self._flush()

        fragment = Fragment()
        for submodule, name in self._submodules:
            fragment.add_subfragment(Fragment.get(submodule, platform), name)
        statements = SampleDomainInjector("sync")(self._statements)
        fragment.add_statements(statements)
        for signal, domain in self._driving.items():
            fragment.add_driver(signal, domain)
        fragment.add_domains(self._domains)
        fragment.generated.update(self._generated)
        return fragment
