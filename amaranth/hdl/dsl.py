from collections import OrderedDict
from contextlib import contextmanager, _GeneratorContextManager
from functools import wraps
from enum import Enum
import warnings
import sys

from .._utils import flatten, bits_for
from .. import tracer
from .ast import *
from .ir import *
from .cd import *
from .xfrm import *


__all__ = ["SyntaxError", "SyntaxWarning", "Module"]


class SyntaxError(Exception):
    pass


class SyntaxWarning(Warning):
    pass


class _ModuleBuilderProxy:
    def __init__(self, builder, depth):
        object.__setattr__(self, "_builder", builder)
        object.__setattr__(self, "_depth", depth)


class _ModuleBuilderDomain(_ModuleBuilderProxy):
    def __init__(self, builder, depth, domain):
        super().__init__(builder, depth)
        self._domain = domain

    def __iadd__(self, assigns):
        self._builder._add_statement(assigns, domain=self._domain, depth=self._depth)
        return self


class _ModuleBuilderDomains(_ModuleBuilderProxy):
    def __getattr__(self, name):
        if name == "submodules":
            warnings.warn("Using '<module>.d.{}' would add statements to clock domain {!r}; "
                          "did you mean <module>.{} instead?"
                          .format(name, name, name),
                          SyntaxWarning, stacklevel=2)
        if name == "comb":
            domain = None
        else:
            domain = name
        return _ModuleBuilderDomain(self._builder, self._depth, domain)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        if name == "_depth":
            object.__setattr__(self, name, value)
        elif not isinstance(value, _ModuleBuilderDomain):
            raise AttributeError("Cannot assign 'd.{}' attribute; did you mean 'd.{} +='?"
                                 .format(name, name))

    def __setitem__(self, name, value):
        return self.__setattr__(name, value)


class _ModuleBuilderRoot:
    def __init__(self, builder, depth):
        self._builder = builder
        self.domain = self.d = _ModuleBuilderDomains(builder, depth)

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

    def __setitem__(self, name, value):
        return self.__setattr__(name, value)

    def __getattr__(self, name):
        return self._builder._get_submodule(name)

    def __getitem__(self, name):
        return self.__getattr__(name)


class _ModuleBuilderDomainSet:
    def __init__(self, builder):
        object.__setattr__(self, "_builder", builder)

    def __iadd__(self, domains):
        for domain in flatten([domains]):
            if not isinstance(domain, ClockDomain):
                raise TypeError("Only clock domains may be added to `m.domains`, not {!r}"
                                .format(domain))
            self._builder._add_domain(domain)
        return self

    def __setattr__(self, name, domain):
        if not isinstance(domain, ClockDomain):
            raise TypeError("Only clock domains may be added to `m.domains`, not {!r}"
                            .format(domain))
        if domain.name != name:
            raise NameError("Clock domain name {!r} must match name in `m.domains.{} += ...` "
                            "syntax"
                            .format(domain.name, name))
        self._builder._add_domain(domain)


# It's not particularly clean to depend on an internal interface, but, unfortunately, __bool__
# must be defined on a class to be called during implicit conversion.
class _GuardedContextManager(_GeneratorContextManager):
    def __init__(self, keyword, func, args, kwds):
        self.keyword = keyword
        return super().__init__(func, args, kwds)

    def __bool__(self):
        raise SyntaxError("`if m.{kw}(...):` does not work; use `with m.{kw}(...)`"
                          .format(kw=self.keyword))


def _guardedcontextmanager(keyword):
    def decorator(func):
        @wraps(func)
        def helper(*args, **kwds):
            return _GuardedContextManager(keyword, func, args, kwds)
        return helper
    return decorator


class FSM:
    def __init__(self, state, encoding, decoding):
        self.state    = state
        self.encoding = encoding
        self.decoding = decoding

    def ongoing(self, name):
        if name not in self.encoding:
            self.encoding[name] = len(self.encoding)
        return Operator("==", [self.state, self.encoding[name]], src_loc_at=0)


class Module(_ModuleBuilderRoot, Elaboratable):
    @classmethod
    def __init_subclass__(cls):
        raise SyntaxError("Instead of inheriting from `Module`, inherit from `Elaboratable` "
                          "and return a `Module` from the `elaborate(self, platform)` method")

    def __init__(self):
        _ModuleBuilderRoot.__init__(self, self, depth=0)
        self.submodules    = _ModuleBuilderSubmodules(self)
        self.domains       = _ModuleBuilderDomainSet(self)

        self._statements   = Statement.cast([])
        self._ctrl_context = None
        self._ctrl_stack   = []

        self._driving      = SignalDict()
        self._named_submodules = {}
        self._anon_submodules  = []
        self._domains      = {}
        self._generated    = {}

    def _check_context(self, construct, context):
        if self._ctrl_context != context:
            if self._ctrl_context is None:
                raise SyntaxError("{} is not permitted outside of {}"
                                  .format(construct, context))
            else:
                if self._ctrl_context == "Switch":
                    secondary_context = "Case"
                if self._ctrl_context == "FSM":
                    secondary_context = "State"
                raise SyntaxError("{} is not permitted directly inside of {}; it is permitted "
                                  "inside of {} {}"
                                  .format(construct, self._ctrl_context,
                                          self._ctrl_context, secondary_context))

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

    def _check_signed_cond(self, cond):
        cond = Value.cast(cond)
        if sys.version_info < (3, 12, 0) and cond.shape().signed:
            # TODO(py3.11): remove; ~True is a warning in 3.12+, finally!
            warnings.warn("Signed values in If/Elif conditions usually result from inverting "
                          "Python booleans with ~, which leads to unexpected results. "
                          "Replace `~flag` with `not flag`. (If this is a false positive, "
                          "silence this warning with `m.If(x)` → `m.If(x.bool())`.)",
                          SyntaxWarning, stacklevel=4)
        return cond

    @_guardedcontextmanager("If")
    def If(self, cond):
        self._check_context("If", context=None)
        cond = self._check_signed_cond(cond)
        src_loc = tracer.get_src_loc(src_loc_at=1)
        if_data = self._set_ctrl("If", {
            "depth":    self.domain._depth,
            "tests":    [],
            "bodies":   [],
            "src_loc":  src_loc,
            "src_locs": [],
        })
        try:
            _outer_case, self._statements = self._statements, []
            self.domain._depth += 1
            yield
            self._flush_ctrl()
            if_data["tests"].append(cond)
            if_data["bodies"].append(self._statements)
            if_data["src_locs"].append(src_loc)
        finally:
            self.domain._depth -= 1
            self._statements = _outer_case

    @_guardedcontextmanager("Elif")
    def Elif(self, cond):
        self._check_context("Elif", context=None)
        cond = self._check_signed_cond(cond)
        src_loc = tracer.get_src_loc(src_loc_at=1)
        if_data = self._get_ctrl("If")
        if if_data is None or if_data["depth"] != self.domain._depth:
            raise SyntaxError("Elif without preceding If")
        try:
            _outer_case, self._statements = self._statements, []
            self.domain._depth += 1
            yield
            self._flush_ctrl()
            if_data["tests"].append(cond)
            if_data["bodies"].append(self._statements)
            if_data["src_locs"].append(src_loc)
        finally:
            self.domain._depth -= 1
            self._statements = _outer_case

    @_guardedcontextmanager("Else")
    def Else(self):
        self._check_context("Else", context=None)
        src_loc = tracer.get_src_loc(src_loc_at=1)
        if_data = self._get_ctrl("If")
        if if_data is None or if_data["depth"] != self.domain._depth:
            raise SyntaxError("Else without preceding If/Elif")
        try:
            _outer_case, self._statements = self._statements, []
            self.domain._depth += 1
            yield
            self._flush_ctrl()
            if_data["bodies"].append(self._statements)
            if_data["src_locs"].append(src_loc)
        finally:
            self.domain._depth -= 1
            self._statements = _outer_case
        self._pop_ctrl()

    @contextmanager
    def Switch(self, test):
        self._check_context("Switch", context=None)
        switch_data = self._set_ctrl("Switch", {
            "test":    Value.cast(test),
            "cases":   OrderedDict(),
            "src_loc": tracer.get_src_loc(src_loc_at=1),
            "case_src_locs": {},
        })
        try:
            self._ctrl_context = "Switch"
            self.domain._depth += 1
            yield
        finally:
            self.domain._depth -= 1
            self._ctrl_context = None
        self._pop_ctrl()

    @contextmanager
    def Case(self, *patterns):
        self._check_context("Case", context="Switch")
        src_loc = tracer.get_src_loc(src_loc_at=1)
        switch_data = self._get_ctrl("Switch")
        new_patterns = ()
        # This code should accept exactly the same patterns as `v.matches(...)`.
        for pattern in patterns:
            if isinstance(pattern, str) and any(bit not in "01- \t" for bit in pattern):
                raise SyntaxError("Case pattern '{}' must consist of 0, 1, and - (don't care) "
                                  "bits, and may include whitespace"
                                  .format(pattern))
            if (isinstance(pattern, str) and
                    len("".join(pattern.split())) != len(switch_data["test"])):
                raise SyntaxError("Case pattern '{}' must have the same width as switch value "
                                  "(which is {})"
                                  .format(pattern, len(switch_data["test"])))
            if isinstance(pattern, str):
                new_patterns = (*new_patterns, pattern)
            else:
                try:
                    orig_pattern, pattern = pattern, Const.cast(pattern)
                except TypeError as e:
                    raise SyntaxError("Case pattern must be a string or a constant-castable "
                                      "expression, not {!r}"
                                      .format(pattern)) from e
                pattern_len = bits_for(pattern.value)
                if pattern_len > len(switch_data["test"]):
                    warnings.warn("Case pattern '{!r}' ({}'{:b}) is wider than switch value "
                                  "(which has width {}); comparison will never be true"
                                  .format(orig_pattern, pattern_len, pattern.value,
                                          len(switch_data["test"])),
                                  SyntaxWarning, stacklevel=3)
                    continue
                new_patterns = (*new_patterns, pattern.value)
        try:
            _outer_case, self._statements = self._statements, []
            self._ctrl_context = None
            yield
            self._flush_ctrl()
            # If none of the provided cases can possibly be true, omit this branch completely.
            # This needs to be differentiated from no cases being provided in the first place,
            # which means the branch will always match.
            if not (patterns and not new_patterns):
                switch_data["cases"][new_patterns] = self._statements
                switch_data["case_src_locs"][new_patterns] = src_loc
        finally:
            self._ctrl_context = "Switch"
            self._statements = _outer_case

    def Default(self):
        return self.Case()

    @contextmanager
    def FSM(self, reset=None, domain="sync", name="fsm"):
        self._check_context("FSM", context=None)
        if domain == "comb":
            raise ValueError(f"FSM may not be driven by the '{domain}' domain")
        fsm_data = self._set_ctrl("FSM", {
            "name":     name,
            "signal":   Signal(name=f"{name}_state", src_loc_at=2),
            "reset":    reset,
            "domain":   domain,
            "encoding": OrderedDict(),
            "decoding": OrderedDict(),
            "states":   OrderedDict(),
            "src_loc":  tracer.get_src_loc(src_loc_at=1),
            "state_src_locs": {},
        })
        self._generated[name] = fsm = \
            FSM(fsm_data["signal"], fsm_data["encoding"], fsm_data["decoding"])
        try:
            self._ctrl_context = "FSM"
            self.domain._depth += 1
            yield fsm
            for state_name in fsm_data["encoding"]:
                if state_name not in fsm_data["states"]:
                    raise NameError("FSM state '{}' is referenced but not defined"
                                    .format(state_name))
        finally:
            self.domain._depth -= 1
            self._ctrl_context = None
        self._pop_ctrl()

    @contextmanager
    def State(self, name):
        self._check_context("FSM State", context="FSM")
        src_loc = tracer.get_src_loc(src_loc_at=1)
        fsm_data = self._get_ctrl("FSM")
        if name in fsm_data["states"]:
            raise NameError(f"FSM state '{name}' is already defined")
        if name not in fsm_data["encoding"]:
            fsm_data["encoding"][name] = len(fsm_data["encoding"])
        try:
            _outer_case, self._statements = self._statements, []
            self._ctrl_context = None
            yield
            self._flush_ctrl()
            fsm_data["states"][name] = self._statements
            fsm_data["state_src_locs"][name] = src_loc
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
        src_loc = data["src_loc"]

        if name == "If":
            if_tests, if_bodies = data["tests"], data["bodies"]
            if_src_locs = data["src_locs"]

            tests, cases = [], OrderedDict()
            for if_test, if_case in zip(if_tests + [None], if_bodies):
                if if_test is not None:
                    if len(if_test) != 1:
                        if_test = if_test.bool()
                    tests.append(if_test)

                if if_test is not None:
                    match = ("1" + "-" * (len(tests) - 1)).rjust(len(if_tests), "-")
                else:
                    match = None
                cases[match] = if_case

            self._statements.append(Switch(Cat(tests), cases,
                src_loc=src_loc, case_src_locs=dict(zip(cases, if_src_locs))))

        if name == "Switch":
            switch_test, switch_cases = data["test"], data["cases"]
            switch_case_src_locs = data["case_src_locs"]

            self._statements.append(Switch(switch_test, switch_cases,
                src_loc=src_loc, case_src_locs=switch_case_src_locs))

        if name == "FSM":
            fsm_signal, fsm_reset, fsm_encoding, fsm_decoding, fsm_states = \
                data["signal"], data["reset"], data["encoding"], data["decoding"], data["states"]
            fsm_state_src_locs = data["state_src_locs"]
            if not fsm_states:
                return
            fsm_signal.width = bits_for(len(fsm_encoding) - 1)
            if fsm_reset is None:
                fsm_signal.reset = fsm_encoding[next(iter(fsm_states))]
            else:
                fsm_signal.reset = fsm_encoding[fsm_reset]
            # The FSM is encoded such that the state with encoding 0 is always the reset state.
            fsm_decoding.update((n, s) for s, n in fsm_encoding.items())
            fsm_signal.decoder = lambda n: f"{fsm_decoding[n]}/{n}"
            self._statements.append(Switch(fsm_signal,
                OrderedDict((fsm_encoding[name], stmts) for name, stmts in fsm_states.items()),
                src_loc=src_loc, case_src_locs={fsm_encoding[name]: fsm_state_src_locs[name]
                                                for name in fsm_states}))

    def _add_statement(self, assigns, domain, depth, compat_mode=False):
        def domain_name(domain):
            if domain is None:
                return "comb"
            else:
                return domain

        while len(self._ctrl_stack) > self.domain._depth:
            self._pop_ctrl()

        for stmt in Statement.cast(assigns):
            if not compat_mode and not isinstance(stmt, (Assign, Assert, Assume, Cover)):
                raise SyntaxError(
                    "Only assignments and property checks may be appended to d.{}"
                    .format(domain_name(domain)))

            stmt._MustUse__used = True
            stmt = SampleDomainInjector(domain)(stmt)

            for signal in stmt._lhs_signals():
                if signal not in self._driving:
                    self._driving[signal] = domain
                elif self._driving[signal] != domain:
                    cd_curr = self._driving[signal]
                    raise SyntaxError(
                        "Driver-driver conflict: trying to drive {!r} from d.{}, but it is "
                        "already driven from d.{}"
                        .format(signal, domain_name(domain), domain_name(cd_curr)))

            self._statements.append(stmt)

    def _add_submodule(self, submodule, name=None):
        if not hasattr(submodule, "elaborate"):
            raise TypeError("Trying to add {!r}, which does not implement .elaborate(), as "
                            "a submodule".format(submodule))
        if name == None:
            self._anon_submodules.append(submodule)
        else:
            if name in self._named_submodules:
                raise NameError(f"Submodule named '{name}' already exists")
            self._named_submodules[name] = submodule

    def _get_submodule(self, name):
        if name in self._named_submodules:
            return self._named_submodules[name]
        else:
            raise AttributeError(f"No submodule named '{name}' exists")

    def _add_domain(self, cd):
        if cd.name in self._domains:
            raise NameError(f"Clock domain named '{cd.name}' already exists")
        self._domains[cd.name] = cd

    def _flush(self):
        while self._ctrl_stack:
            self._pop_ctrl()

    def elaborate(self, platform):
        self._flush()

        fragment = Fragment()
        for name in self._named_submodules:
            fragment.add_subfragment(Fragment.get(self._named_submodules[name], platform), name)
        for submodule in self._anon_submodules:
            fragment.add_subfragment(Fragment.get(submodule, platform), None)
        statements = SampleDomainInjector("sync")(self._statements)
        fragment.add_statements(statements)
        for signal, domain in self._driving.items():
            fragment.add_driver(signal, domain)
        fragment.add_domains(self._domains.values())
        fragment.generated.update(self._generated)
        return fragment
