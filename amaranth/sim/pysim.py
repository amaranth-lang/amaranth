from contextlib import contextmanager, closing
import itertools
import re
import os.path
import enum as py_enum

from ..hdl import *
from ..hdl._mem import MemoryInstance
from ..hdl._ast import SignalDict
from ..lib import data, wiring
from ._base import *
from ._async import *
from ._pyeval import eval_format, eval_value, eval_assign
from ._pyrtl import _FragmentCompiler
from ._pyclock import PyClockProcess
from ._vcdwriter import _VCDWriter

__all__ = ["PySimEngine"]


class _PyTimeline:
    def __init__(self):
        self.now = 0
        self.wakers = {}

    def reset(self):
        self.now = 0
        self.wakers.clear()

    def set_waker(self, interval, waker):
        self.wakers[waker] = self.now + interval

    def advance(self):
        nearest_wakers = set()
        nearest_deadline = None
        for waker, deadline in self.wakers.items():
            if nearest_deadline is None or deadline <= nearest_deadline:
                assert deadline >= self.now
                if nearest_deadline is not None and deadline < nearest_deadline:
                    nearest_wakers.clear()
                nearest_wakers.add(waker)
                nearest_deadline = deadline

        if not nearest_wakers:
            return False

        for waker in nearest_wakers:
            waker()
            del self.wakers[waker]

        self.now = nearest_deadline
        return True


def _run_wakers(wakers: list, *args):
    # Python doesn't have `.retain()` :(
    index = 0
    for waker in wakers:
        if waker(*args):
            wakers[index] = waker
            index += 1
    del wakers[index:]


class _PySignalState(BaseSignalState):
    __slots__ = ("signal", "is_comb", "curr", "next", "wakers", "pending")

    def __init__(self, signal, pending):
        self.signal  = signal
        self.is_comb = False
        self.pending = pending
        self.wakers  = list()
        self.reset()

    def reset(self):
        self.curr = self.next = self.signal.init

    def add_waker(self, waker):
        assert waker not in self.wakers
        self.wakers.append(waker)

    def update(self, value, mask=~0):
        value = (self.next & ~mask) | (value & mask)
        if self.next != value:
            self.next = value
            self.pending.add(self)

    def commit(self):
        if self.curr == self.next:
            return False

        _run_wakers(self.wakers, self.curr, self.next)

        self.curr = self.next
        return True


class _PyMemoryChange:
    __slots__ = ("state", "addr")

    def __init__(self, state, addr):
        self.state = state
        self.addr  = addr


class _PyMemoryState(BaseMemoryState):
    __slots__ = ("memory", "shape", "data", "write_queue", "wakers", "pending")

    def __init__(self, memory, pending):
        self.memory  = memory
        self.shape   = Shape.cast(memory.shape)
        self.pending = pending
        self.wakers  = list()
        self.reset()

    def reset(self):
        self.data = list(self.memory._init._raw)
        self.write_queue = {}

    def add_waker(self, waker):
        assert waker not in self.wakers
        self.wakers.append(waker)

    def read(self, addr):
        if addr in range(self.memory.depth):
            return self.data[addr]
        return 0

    def write(self, addr, value, mask=None):
        if addr in range(self.memory.depth):
            if addr not in self.write_queue:
                self.write_queue[addr] = self.data[addr]
            if mask is not None:
                value = (value & mask) | (self.write_queue[addr] & ~mask)
            if self.shape.signed:
                if value & (1 << (self.shape.width - 1)):
                    value |= -1 << (self.shape.width)
                else:
                    value &= (1 << (self.shape.width)) - 1
            self.write_queue[addr] = value
            self.pending.add(self)

    def commit(self):
        assert self.write_queue # `commit()` is only called if `self` is pending

        _run_wakers(self.wakers)

        changed = False
        for addr, value in self.write_queue.items():
            if self.data[addr] != value:
                self.data[addr] = value
                changed = True
        self.write_queue.clear()
        return changed


class _PyEngineState(BaseEngineState):
    def __init__(self):
        self.timeline = _PyTimeline()
        self.signals  = SignalDict()
        self.memories = dict()
        self.slots    = list()
        self.pending  = set()

    def reset(self):
        self.timeline.reset()
        for state in self.slots:
            state.reset()
        self.pending.clear()

    def get_signal(self, signal):
        try:
            return self.signals[signal]
        except KeyError:
            index = len(self.slots)
            self.slots.append(_PySignalState(signal, self.pending))
            self.signals[signal] = index
            return index

    def get_memory(self, memory):
        try:
            return self.memories[memory]
        except KeyError:
            index = len(self.slots)
            self.slots.append(_PyMemoryState(memory, self.pending))
            self.memories[memory] = index
            return index

    def set_delay_waker(self, interval, waker):
        self.timeline.set_waker(interval, waker)

    def add_signal_waker(self, signal, waker):
        self.slots[self.get_signal(signal)].add_waker(waker)

    def add_memory_waker(self, memory, waker):
        self.slots[self.get_memory(memory)].add_waker(waker)

    def commit(self, changed=None):
        converged = True
        for state in self.pending:
            if changed is not None:
                if isinstance(state, _PyMemoryState):
                    for addr in state.write_queue:
                        changed.add(_PyMemoryChange(state, addr))
                elif isinstance(state, _PySignalState):
                    changed.add(state)
                else:
                    assert False # :nocov:
            if state.commit():
                converged = False
        self.pending.clear()
        return converged


class _PyTriggerState:
    def __init__(self, engine, combination, pending, *, oneshot):
        self._engine = engine
        self._combination = combination
        self._active = pending
        self._oneshot = oneshot

        self._result = None
        self._broken = False
        self._triggers_hit = set()
        self._delay_wakers = dict()

        for trigger in combination._triggers:
            if isinstance(trigger, SampleTrigger):
                pass # does not cause a wakeup
            elif isinstance(trigger, ChangedTrigger):
                self.add_changed_waker(trigger)
            elif isinstance(trigger, EdgeTrigger):
                self.add_edge_waker(trigger)
            elif isinstance(trigger, DelayTrigger):
                self.add_delay_waker(trigger)
            else:
                assert False # :nocov:

    def add_changed_waker(self, trigger):
        def waker(curr, next):
            if self._broken:
                return False
            self.activate()
            return not self._oneshot
        self._engine.state.add_signal_waker(trigger.signal, waker)

    def add_edge_waker(self, trigger):
        def waker(curr, next):
            if self._broken:
                return False
            curr_bit = (curr >> trigger.bit) & 1
            next_bit = (next >> trigger.bit) & 1
            if curr_bit == next_bit or next_bit != trigger.polarity:
                return True # wait until next edge
            self._triggers_hit.add(trigger)
            self.activate()
            return not self._oneshot
        self._engine.state.add_signal_waker(trigger.signal, waker)

    def add_delay_waker(self, trigger):
        def waker():
            if self._broken:
                return
            self._triggers_hit.add(trigger)
            self.activate()
        self._engine.state.set_delay_waker(trigger.interval.femtoseconds, waker)
        self._delay_wakers[waker] = trigger.interval.femtoseconds

    def activate(self):
        if self._combination._process.waits_on is self:
            self._active.add(self)
        else:
            self._broken = True

    def compute_result(self):
        result = []
        for trigger in self._combination._triggers:
            if isinstance(trigger, (SampleTrigger, ChangedTrigger)):
                value = self._engine.get_value(trigger.value)
                if isinstance(trigger.shape, ShapeCastable):
                    result.append(trigger.shape.from_bits(value))
                else:
                    result.append(value)
            elif isinstance(trigger, (EdgeTrigger, DelayTrigger)):
                result.append(trigger in self._triggers_hit)
            else:
                assert False # :nocov:
        self._result = tuple(result)

    def run(self):
        self.compute_result()
        self._combination._process.runnable = True
        self._combination._process.waits_on = None
        self._triggers_hit.clear()
        for waker, interval_fs in self._delay_wakers.items():
            self._engine.state.set_delay_waker(interval_fs, waker)

    def initial_eligible(self):
        return not self._oneshot and any(
            isinstance(trigger, ChangedTrigger)
            for trigger in self._combination._triggers
        )

    def __await__(self):
        self._result = None
        if self._broken:
            raise BrokenTrigger
        yield self
        if self._broken:
            raise BrokenTrigger
        return self._result


class PySimEngine(BaseEngine):
    def __init__(self, design):
        self._design = design

        self._state = _PyEngineState()
        self._processes = _FragmentCompiler(self._state)(self._design.fragment)
        self._testbenches = []
        self._delta_cycles = 0
        self._observers = []
        self._active_triggers = set()

    @property
    def state(self) -> BaseEngineState:
        return self._state

    @property
    def now(self):
        return self._state.timeline.now

    def _now_plus_deltas(self, fs_per_delta):
        return self._state.timeline.now + self._delta_cycles * fs_per_delta

    def reset(self):
        self._state.reset()
        for process in self._processes:
            process.reset()
        for testbench in self._testbenches:
            testbench.reset()

    def add_clock_process(self, clock, *, phase, period):
        slot = self.state.get_signal(clock)
        if self.state.slots[slot].is_comb:
            raise DriverConflict("Clock signal is already driven by combinational logic")

        self._processes.add(PyClockProcess(self._state, clock,
                                           phase=phase, period=period))

    def add_async_process(self, simulator, process):
        self._processes.add(AsyncProcess(self._design, self, process,
                                         testbench=False, background=True))

    def add_async_testbench(self, simulator, process, *, background):
        self._testbenches.append(AsyncProcess(self._design, self, process,
                                              testbench=True, background=background))

    def add_trigger_combination(self, combination, *, oneshot):
        return _PyTriggerState(self, combination, self._active_triggers, oneshot=oneshot)

    def get_value(self, expr):
        return eval_value(self._state, Value.cast(expr))

    def set_value(self, expr, value):
        assert isinstance(value, int)
        return eval_assign(self._state, Value.cast(expr), value)

    def step_design(self):
        # Performs the three phases of a delta cycle in a loop:
        converged = False
        while not converged:
            changed = set() if self._observers else None

            # 1a. trigger: run every active trigger, sampling values and waking up processes;
            for trigger_state in self._active_triggers:
                trigger_state.run()
            self._active_triggers.clear()

            # 1b. eval: run every runnable processes once, queueing signal changes;
            for process in self._processes:
                if process.runnable:
                    process.runnable = False
                    process.run()
                    if type(process) is AsyncProcess and process.waits_on is not None:
                        assert type(process.waits_on) is _PyTriggerState, \
                            "Async processes may only await simulation triggers"

            # 2. commit: apply queued signal changes, activating any awaited triggers.
            converged = self._state.commit(changed)

            for observer in self._observers:
                now_plus_deltas = self._now_plus_deltas(observer.fs_per_delta)
                for change in changed:
                    if type(change) is _PySignalState:
                        signal_state = change
                        observer.update_signal(now_plus_deltas,
                            signal_state.signal)
                    elif type(change) is _PyMemoryChange:
                        observer.update_memory(now_plus_deltas, change.state.memory,
                            change.addr)
                    else:
                        assert False # :nocov:

            self._delta_cycles += 1

    def advance(self):
        # Run triggers and processes until the simulation converges.
        self.step_design()

        # Run testbenches that have been awoken in `step_design()` by active triggers.
        converged = False
        while not converged:
            converged = True
            # Schedule testbenches in a deterministic order (the one in which they were added).
            for testbench in self._testbenches:
                if testbench.runnable:
                    testbench.runnable = False
                    testbench.run()
                    if type(testbench) is AsyncProcess and testbench.waits_on is not None:
                        assert type(testbench.waits_on) is _PyTriggerState, \
                            "Async testbenches may only await simulation triggers"
                    converged = False

        # Now that the simulation has converged for the current time, advance the timeline.
        self._state.timeline.advance()

        # Check if the simulation has any critical processes or testbenches.
        for runnables in (self._processes, self._testbenches):
            for runnable in runnables:
                if runnable.critical:
                    return True
        return False

    @contextmanager
    def observe(self, observer: Observer):
        try:
            self._observers.append(observer)
            yield
        finally:
            observer.close(self._now_plus_deltas(observer.fs_per_delta))
            self._observers.remove(observer)

    @contextmanager
    def write_vcd(self, *, vcd_file, gtkw_file, traces, fs_per_delta):
        observer  = _VCDWriter(self._state, self._design, vcd_file=vcd_file, gtkw_file=gtkw_file,
                                traces=traces, fs_per_delta=fs_per_delta)
        with self.observe(observer):
            yield
