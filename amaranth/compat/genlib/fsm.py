from collections import OrderedDict

from ..._utils import deprecated, _ignore_deprecated
from ...hdl.xfrm import ValueTransformer, StatementTransformer
from ...hdl.ast import *
from ...hdl.ast import Signal as NativeSignal
from ..fhdl.module import CompatModule, CompatFinalizeError
from ..fhdl.structure import Signal, If, Case


__all__ = ["AnonymousState", "NextState", "NextValue", "FSM"]


class AnonymousState:
    pass


class NextState(Statement):
    def __init__(self, state):
        super().__init__()
        self.state = state


class NextValue(Statement):
    def __init__(self, target, value):
        super().__init__()
        self.target = target
        self.value = value


def _target_eq(a, b):
    if type(a) != type(b):
        return False
    ty = type(a)
    if ty == Const:
        return a.value == b.value
    elif ty == NativeSignal or ty == Signal:
        return a is b
    elif ty == Cat:
        return all(_target_eq(x, y) for x, y in zip(a.l, b.l))
    elif ty == Slice:
        return (_target_eq(a.value, b.value)
                    and a.start == b.start
                    and a.stop == b.stop)
    elif ty == Part:
        return (_target_eq(a.value, b.value)
                    and _target_eq(a.offset == b.offset)
                    and a.width == b.width)
    elif ty == ArrayProxy:
        return (all(_target_eq(x, y) for x, y in zip(a.choices, b.choices))
                    and _target_eq(a.key, b.key))
    else:
        raise ValueError("NextValue cannot be used with target type '{}'"
                         .format(ty))


class _LowerNext(ValueTransformer, StatementTransformer):
    def __init__(self, next_state_signal, encoding, aliases):
        self.next_state_signal = next_state_signal
        self.encoding = encoding
        self.aliases = aliases
        # (target, next_value_ce, next_value)
        self.registers = []

    def _get_register_control(self, target):
        for x in self.registers:
            if _target_eq(target, x[0]):
                return x[1], x[2]
        raise KeyError

    def on_unknown_statement(self, node):
        if isinstance(node, NextState):
            try:
                actual_state = self.aliases[node.state]
            except KeyError:
                actual_state = node.state
            return self.next_state_signal.eq(self.encoding[actual_state])
        elif isinstance(node, NextValue):
            try:
                next_value_ce, next_value = self._get_register_control(node.target)
            except KeyError:
                related = node.target if isinstance(node.target, Signal) else None
                next_value = Signal(node.target.shape(),
                    name=None if related is None else f"{related.name}_fsm_next")
                next_value_ce = Signal(
                    name=None if related is None else f"{related.name}_fsm_next_ce")
                self.registers.append((node.target, next_value_ce, next_value))
            return next_value.eq(node.value), next_value_ce.eq(1)
        else:
            return node


@deprecated("instead of `migen.genlib.fsm.FSM()`, use `with m.FSM():`; note that there is no "
            "replacement for `{before,after}_{entering,leaving}` and `delayed_enter` methods")
class FSM(CompatModule):
    def __init__(self, reset_state=None):
        self.actions = OrderedDict()
        self.state_aliases = dict()
        self.reset_state = reset_state

        self.before_entering_signals = OrderedDict()
        self.before_leaving_signals = OrderedDict()
        self.after_entering_signals = OrderedDict()
        self.after_leaving_signals = OrderedDict()

    def act(self, state, *statements):
        if self.finalized:
            raise CompatFinalizeError
        if self.reset_state is None:
            self.reset_state = state
        if state not in self.actions:
            self.actions[state] = []
        self.actions[state] += statements

    def delayed_enter(self, name, target, delay):
        if self.finalized:
            raise CompatFinalizeError
        if delay > 0:
            state = name
            for i in range(delay):
                if i == delay - 1:
                    next_state = target
                else:
                    next_state = AnonymousState()
                self.act(state, NextState(next_state))
                state = next_state
        else:
            self.state_aliases[name] = target

    def ongoing(self, state):
        is_ongoing = Signal()
        self.act(state, is_ongoing.eq(1))
        return is_ongoing

    def _get_signal(self, d, state):
        if state not in self.actions:
            self.actions[state] = []
        try:
            return d[state]
        except KeyError:
            is_el = Signal()
            d[state] = is_el
            return is_el

    def before_entering(self, state):
        return self._get_signal(self.before_entering_signals, state)

    def before_leaving(self, state):
        return self._get_signal(self.before_leaving_signals, state)

    def after_entering(self, state):
        signal = self._get_signal(self.after_entering_signals, state)
        self.sync += signal.eq(self.before_entering(state))
        return signal

    def after_leaving(self, state):
        signal = self._get_signal(self.after_leaving_signals, state)
        self.sync += signal.eq(self.before_leaving(state))
        return signal

    @_ignore_deprecated
    def do_finalize(self):
        nstates = len(self.actions)
        self.encoding = {s: n for n, s in enumerate(self.actions.keys())}
        self.decoding = {n: s for s, n in self.encoding.items()}

        decoder = lambda n: f"{self.decoding[n]}/{n}"
        self.state = Signal(range(nstates), reset=self.encoding[self.reset_state], decoder=decoder)
        self.next_state = Signal.like(self.state)

        for state, signal in self.before_leaving_signals.items():
            encoded = self.encoding[state]
            self.comb += signal.eq((self.state == encoded) & ~(self.next_state == encoded))
        if self.reset_state in self.after_entering_signals:
            self.after_entering_signals[self.reset_state].reset = 1
        for state, signal in self.before_entering_signals.items():
            encoded = self.encoding[state]
            self.comb += signal.eq(~(self.state == encoded) & (self.next_state == encoded))

        self._finalize_sync(self._lower_controls())

    def _lower_controls(self):
        return _LowerNext(self.next_state, self.encoding, self.state_aliases)

    def _finalize_sync(self, ls):
        cases = {self.encoding[k]: ls.on_statement(v) for k, v in self.actions.items() if v}
        self.comb += [
            self.next_state.eq(self.state),
            Case(self.state, cases).makedefault(self.encoding[self.reset_state])
        ]
        self.sync += self.state.eq(self.next_state)
        for register, next_value_ce, next_value in ls.registers:
            self.sync += If(next_value_ce, register.eq(next_value))
