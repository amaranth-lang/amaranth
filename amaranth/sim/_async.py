import typing
import operator
from contextlib import contextmanager

from ..hdl import *
from ..hdl._ast import Slice
from ._base import BaseProcess, BaseEngine


__all__ = [
    "DomainReset", "BrokenTrigger",
    "SampleTrigger", "ChangedTrigger", "EdgeTrigger", "DelayTrigger",
    "TriggerCombination", "TickTrigger",
    "SimulatorContext", "ProcessContext", "TestbenchContext", "AsyncProcess",
]


class DomainReset(Exception):
    """Exception raised when the domain of a a tick trigger that is repeatedly awaited has its
    reset asserted."""


class BrokenTrigger(Exception):
    """Exception raised when a trigger that is repeatedly awaited in an `async for` loop has
    a matching event occur while the body of the `async for` loop is executing."""


class SampleTrigger:
    def __init__(self, value):
        self.value = Value.cast(value)
        if isinstance(value, ValueCastable):
            self.shape = value.shape()
        else:
            self.shape = self.value.shape()


class ChangedTrigger:
    def __init__(self, signal):
        cast_signal = Value.cast(signal)
        if not isinstance(cast_signal, Signal):
            raise TypeError(f"Change trigger can only be used with a signal, not {signal!r}")
        self.shape = signal.shape()
        self.signal = cast_signal

    @property
    def value(self):
        return self.signal


class EdgeTrigger:
    def __init__(self, signal, polarity):
        cast_signal = Value.cast(signal)
        if isinstance(cast_signal, Signal) and len(cast_signal) == 1:
            self.signal, self.bit = cast_signal, 0
        elif (isinstance(cast_signal, Slice) and
                len(cast_signal) == 1 and
                isinstance(cast_signal.value, Signal)):
            self.signal, self.bit = cast_signal.value, cast_signal.start
        else:
            raise TypeError(f"Edge trigger can only be used with a single-bit signal or "
                            f"a single-bit slice of a signal, not {signal!r}")
        if polarity not in (0, 1):
            raise ValueError(f"Edge trigger polarity must be 0 or 1, not {polarity!r}")
        self.polarity = polarity


class DelayTrigger:
    def __init__(self, interval):
        self.interval_fs = round(float(interval) * 1e15)


class TriggerCombination:
    def __init__(self, engine: BaseEngine, process: BaseProcess, *,
            triggers: 'tuple[DelayTrigger|ChangedTrigger|SampleTrigger|EdgeTrigger, ...]' = ()):
        self._engine   = engine
        self._process  = process  # private but used by engines
        self._triggers = triggers # private but used by engines

    def sample(self, *values) -> 'TriggerCombination':
        return TriggerCombination(self._engine, self._process, triggers=self._triggers +
            tuple(SampleTrigger(value) for value in values))

    def changed(self, *signals) -> 'TriggerCombination':
        return TriggerCombination(self._engine, self._process, triggers=self._triggers +
            tuple(ChangedTrigger(signal) for signal in signals))

    def edge(self, signal, polarity) -> 'TriggerCombination':
        return TriggerCombination(self._engine, self._process, triggers=self._triggers +
            (EdgeTrigger(signal, polarity),))

    def posedge(self, signal) -> 'TriggerCombination':
        return self.edge(signal, 1)

    def negedge(self, signal) -> 'TriggerCombination':
        return self.edge(signal, 0)

    def delay(self, interval) -> 'TriggerCombination':
        return TriggerCombination(self._engine, self._process, triggers=self._triggers +
            (DelayTrigger(interval),))

    def __await__(self):
        trigger = self._engine.add_trigger_combination(self, oneshot=True)
        return trigger.__await__()

    async def __aiter__(self):
        trigger = self._engine.add_trigger_combination(self, oneshot=False)
        while True:
            yield await trigger


class TickTrigger:
    def __init__(self, engine: BaseEngine, process: BaseProcess, *,
            domain: ClockDomain, sampled: 'tuple[ValueLike]' = ()):
        self._engine  = engine
        self._process = process
        self._domain  = domain
        self._sampled = sampled

    def sample(self, *values: ValueLike) -> 'TickTrigger':
        return TickTrigger(self._engine, self._process,
                           domain=self._domain, sampled=(*self._sampled, *values))

    async def until(self, condition: ValueLike):
        if not isinstance(condition, ValueLike):
            raise TypeError(f"Condition must be a value-like object, not {condition!r}")
        tick = self.sample(condition).__aiter__()
        done = False
        while not done:
            clk, rst, *values, done = await tick.__anext__()
            if rst:
                raise DomainReset
        return tuple(values)

    async def repeat(self, count: int):
        count = operator.index(count)
        if count <= 0:
            raise ValueError(f"Repeat count must be a positive integer, not {count!r}")
        tick = self.__aiter__()
        for _ in range(count):
            clk, rst, *values = await tick.__anext__()
            if rst:
                raise DomainReset
        return tuple(values)

    def _collect_trigger(self):
        clk_polarity = (1 if self._domain.clk_edge == "pos" else 0)
        if self._domain.async_reset and self._domain.rst is not None:
            return (TriggerCombination(self._engine, self._process)
                .edge(self._domain.clk, clk_polarity)
                .edge(self._domain.rst, 1)
                .sample(self._domain.rst)
                .sample(*self._sampled))
        else:
            return (TriggerCombination(self._engine, self._process)
                .edge(self._domain.clk, clk_polarity)
                .sample(Const(0))
                .sample(Const(0) if self._domain.rst is None else self._domain.rst)
                .sample(*self._sampled))

    def __await__(self):
        trigger = self._engine.add_trigger_combination(self._collect_trigger(), oneshot=True)
        clk_edge, rst_edge, rst_sample, *values = yield from trigger.__await__()
        return (clk_edge, bool(rst_edge or rst_sample), *values)

    async def __aiter__(self):
        trigger = self._engine.add_trigger_combination(self._collect_trigger(), oneshot=False)
        while True:
            clk_edge, rst_edge, rst_sample, *values = await trigger
            yield (clk_edge, bool(rst_edge or rst_sample), *values)


class SimulatorContext:
    def __init__(self, design, engine: BaseEngine, process: BaseProcess):
        self._design  = design
        self._engine  = engine
        self._process = process

    def delay(self, interval) -> TriggerCombination:
        return TriggerCombination(self._engine, self._process).delay(interval)

    def changed(self, *signals) -> TriggerCombination:
        return TriggerCombination(self._engine, self._process).changed(*signals)

    def edge(self, signal, polarity) -> TriggerCombination:
        return TriggerCombination(self._engine, self._process).edge(signal, polarity)

    def posedge(self, signal) -> TriggerCombination:
        return TriggerCombination(self._engine, self._process).posedge(signal)

    def negedge(self, signal) -> TriggerCombination:
        return TriggerCombination(self._engine, self._process).negedge(signal)

    @typing.overload
    def tick(self, domain: str, *, context: Elaboratable = None) -> TickTrigger: ... # :nocov:

    @typing.overload
    def tick(self, domain: ClockDomain) -> TickTrigger: ... # :nocov:

    def tick(self, domain="sync", *, context=None):
        if domain == "comb":
            raise ValueError("Combinational domain does not have a clock")
        if isinstance(domain, ClockDomain):
            if context is not None:
                raise ValueError("Context cannot be provided if a clock domain is specified "
                                 "directly")
        else:
            domain = self._design.lookup_domain(domain, context)
        return TickTrigger(self._engine, self._process, domain=domain)

    @contextmanager
    def critical(self):
        try:
            old_critical, self._process.critical = self._process.critical, True
            yield
        finally:
            self._process.critical = old_critical


class ProcessContext(SimulatorContext):
    def get(self, expr: ValueLike) -> 'typing.Never':
        raise TypeError("`.get()` cannot be used to sample values in simulator processes; use "
                        "`.sample()` on a trigger object instead")

    @typing.overload
    def set(self, expr: Value, value: int) -> None: ... # :nocov:

    @typing.overload
    def set(self, expr: ValueCastable, value: typing.Any) -> None: ... # :nocov:

    def set(self, expr, value):
        if isinstance(expr, ValueCastable):
            shape = expr.shape()
            if isinstance(shape, ShapeCastable):
                value = shape.const(value)
        value = Const.cast(value).value
        self._engine.set_value(expr, value)


class TestbenchContext(SimulatorContext):
    @typing.overload
    def get(self, expr: Value) -> int: ... # :nocov:

    @typing.overload
    def get(self, expr: ValueCastable) -> typing.Any: ... # :nocov:

    def get(self, expr):
        value = self._engine.get_value(expr)
        if isinstance(expr, ValueCastable):
            shape = expr.shape()
            if isinstance(shape, ShapeCastable):
                return shape.from_bits(value)
        return value

    @typing.overload
    def set(self, expr: Value, value: int) -> None: ... # :nocov:

    @typing.overload
    def set(self, expr: ValueCastable, value: typing.Any) -> None: ... # :nocov:

    def set(self, expr, value):
        if isinstance(expr, ValueCastable):
            shape = expr.shape()
            if isinstance(shape, ShapeCastable):
                value = shape.const(value)
        value = Const.cast(value).value
        self._engine.set_value(expr, value)
        self._engine.step_design()


class AsyncProcess(BaseProcess):
    def __init__(self, design, engine, constructor, *, testbench, background):
        self.constructor = constructor
        if testbench:
            self.context = TestbenchContext(design, engine, self)
        else:
            self.context = ProcessContext(design, engine, self)
        self.background = background

        self.reset()

    def reset(self):
        self.runnable = True
        self.critical = not self.background
        self.waits_on = None
        self.coroutine = self.constructor(self.context)

    def run(self):
        try:
            self.waits_on = self.coroutine.send(None)
        except StopIteration:
            self.critical = False
            self.waits_on = None
            self.coroutine = None
