from contextlib import contextmanager
import itertools
import re
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


__all__ = ["PySimEngine"]


class _VCDWriter:
    @staticmethod
    def decode_to_vcd(format, value):
        return format.format(value).expandtabs().replace(" ", "_")

    def __init__(self, state, design, *, vcd_file, gtkw_file=None, traces=(), fs_per_delta=0):
        self.state = state
        self.fs_per_delta = fs_per_delta

        # Although pyvcd is a mandatory dependency, be resilient and import it as needed, so that
        # the simulator is still usable if it's not installed for some reason.
        import vcd, vcd.gtkw

        self.close_vcd = False
        self.close_gtkw = False
        if isinstance(vcd_file, str):
            vcd_file = open(vcd_file, "w")
            self.close_vcd = True
        if isinstance(gtkw_file, str):
            gtkw_file = open(gtkw_file, "w")
            self.close_gtkw = True

        self.vcd_signal_vars = SignalDict()
        self.vcd_memory_vars = {}
        self.vcd_file = vcd_file
        self.vcd_writer = vcd_file and vcd.VCDWriter(self.vcd_file,
            timescale="1 fs", comment="Generated by Amaranth")

        self.gtkw_signal_names = SignalDict()
        self.gtkw_memory_names = {}
        self.gtkw_file = gtkw_file
        self.gtkw_save = gtkw_file and vcd.gtkw.GTKWSave(self.gtkw_file)

        self.traces = traces

        signal_names = SignalDict()
        memories = {}
        for fragment, fragment_info in design.fragments.items():
            fragment_name = ("bench", *fragment_info.name)
            for signal, signal_name in fragment_info.signal_names.items():
                if signal not in signal_names:
                    signal_names[signal] = set()
                signal_names[signal].add((*fragment_name, signal_name))
            if isinstance(fragment, MemoryInstance):
                memories[fragment._data] = fragment_name

        trace_names = SignalDict()
        assigned_names = set()
        def traverse_traces(traces):
            if isinstance(traces, ValueLike):
                trace = Value.cast(traces)
                if isinstance(trace, MemoryData._Row):
                    memory = trace._memory
                    if not memory in memories:
                        if memory.name not in assigned_names:
                            name = memory.name
                        else:
                            name = f"{memory.name}${len(assigned_names)}"
                            assert name not in assigned_names
                        memories[memory] = ("bench", name)
                        assigned_names.add(name)
                else:
                    for trace_signal in trace._rhs_signals():
                        if trace_signal not in signal_names:
                            if trace_signal.name not in assigned_names:
                                name = trace_signal.name
                            else:
                                name = f"{trace_signal.name}${len(assigned_names)}"
                                assert name not in assigned_names
                            trace_names[trace_signal] = {("bench", name)}
                            assigned_names.add(name)
            elif isinstance(traces, MemoryData):
                if not traces in memories:
                    if traces.name not in assigned_names:
                        name = traces.name
                    else:
                        name = f"{traces.name}${len(assigned_names)}"
                        assert name not in assigned_names
                    memories[traces] = ("bench", name)
                    assigned_names.add(name)
            elif hasattr(traces, "signature") and isinstance(traces.signature, wiring.Signature):
                for name in traces.signature.members:
                    traverse_traces(getattr(traces, name))
            elif isinstance(traces, list) or isinstance(traces, tuple):
                for trace in traces:
                    traverse_traces(trace)
            elif isinstance(traces, dict):
                for trace in traces.values():
                    traverse_traces(trace)
            else:
                raise TypeError(f"{traces!r} is not a traceable object")
        traverse_traces(traces)

        if self.vcd_writer is None:
            return

        for signal, names in itertools.chain(signal_names.items(), trace_names.items()):
            self.vcd_signal_vars[signal] = []
            self.gtkw_signal_names[signal] = []

            def add_var(path, var_type, var_size, var_init, value):
                vcd_var = None
                for (*var_scope, var_name) in names:
                    if re.search(r"[ \t\r\n]", var_name):
                        raise NameError("Signal '{}.{}' contains a whitespace character"
                                        .format(".".join(var_scope), var_name))

                    field_name = var_name
                    for item in path:
                        if isinstance(item, int):
                            field_name += f"[{item}]"
                        else:
                            field_name += f".{item}"
                    if path:
                        field_name = "\\" + field_name

                    if vcd_var is None:
                        vcd_var = self.vcd_writer.register_var(
                            scope=var_scope, name=field_name,
                            var_type=var_type, size=var_size, init=var_init)
                        if var_size > 1:
                            suffix = f"[{var_size - 1}:0]"
                        else:
                            suffix = ""
                        self.gtkw_signal_names[signal].append(
                            ".".join((*var_scope, field_name)) + suffix)
                    else:
                        self.vcd_writer.register_alias(
                            scope=var_scope, name=field_name,
                            var=vcd_var)

                self.vcd_signal_vars[signal].append((vcd_var, value))

            def add_wire_var(path, value):
                add_var(path, "wire", len(value), eval_value(self.state, value), value)

            def add_format_var(path, fmt):
                add_var(path, "string", 1, eval_format(self.state, fmt), fmt)

            def add_format(path, fmt):
                if isinstance(fmt, Format.Struct):
                    add_wire_var(path, fmt._value)
                    for name, subfmt in fmt._fields.items():
                        add_format(path + (name,), subfmt)
                elif isinstance(fmt, Format.Array):
                    add_wire_var(path, fmt._value)
                    for idx, subfmt in enumerate(fmt._fields):
                        add_format(path + (idx,), subfmt)
                elif (isinstance(fmt, Format) and
                        len(fmt._chunks) == 1 and
                        isinstance(fmt._chunks[0], tuple) and
                        fmt._chunks[0][1] == ""):
                    add_wire_var(path, fmt._chunks[0][0])
                else:
                    add_format_var(path, fmt)

            if signal._decoder is not None and not isinstance(signal._decoder, py_enum.EnumMeta):
                add_var((), "string", 1, signal._decoder(signal._init), signal._decoder)
            else:
                add_format((), signal._format)

        for memory, memory_name in memories.items():
            self.vcd_memory_vars[memory] = vcd_vars = []
            self.gtkw_memory_names[memory] = gtkw_names = []

            for idx, row in enumerate(memory):
                row_vcd_vars = []
                row_gtkw_names = []
                var_scope = memory_name[:-1]

                def add_mem_var(path, var_type, var_size, var_init, value):
                    field_name = "\\" + memory_name[-1] + f"[{idx}]"
                    for item in path:
                        if isinstance(item, int):
                            field_name += f"[{item}]"
                        else:
                            field_name += f".{item}"
                    row_vcd_vars.append((self.vcd_writer.register_var(
                        scope=var_scope, name=field_name, var_type=var_type,
                        size=var_size, init=var_init
                    ), value))
                    if var_size > 1:
                        suffix = f"[{var_size - 1}:0]"
                    else:
                        suffix = ""
                    row_gtkw_names.append(".".join((*var_scope, field_name)) + suffix)

                def add_mem_wire_var(path, value):
                    add_mem_var(path, "wire", len(value), eval_value(self.state, value), value)

                def add_mem_format_var(path, fmt):
                    add_mem_var(path, "string", 1, eval_format(self.state, fmt), fmt)

                def add_mem_format(path, fmt):
                    if isinstance(fmt, Format.Struct):
                        add_mem_wire_var(path, fmt._value)
                        for name, subfmt in fmt._fields.items():
                            add_mem_format(path + (name,), subfmt)
                    elif isinstance(fmt, Format.Array):
                        add_mem_wire_var(path, fmt._value)
                        for idx, subfmt in enumerate(fmt._fields):
                            add_mem_format(path + (idx,), subfmt)
                    elif (isinstance(fmt, Format) and
                            len(fmt._chunks) == 1 and
                            isinstance(fmt._chunks[0], tuple) and
                            fmt._chunks[0][1] == ""):
                        add_mem_wire_var(path, fmt._chunks[0][0])
                    else:
                        add_mem_format_var(path, fmt)

                if isinstance(memory._shape, ShapeCastable):
                    fmt = memory._shape.format(memory._shape(row), "")
                    add_mem_format((), fmt)
                else:
                    add_mem_wire_var((), row)

                vcd_vars.append(row_vcd_vars)
                gtkw_names.append(row_gtkw_names)

    def update_signal(self, timestamp, signal):
        for (vcd_var, repr) in self.vcd_signal_vars.get(signal, ()):
            if isinstance(repr, Value):
                var_value = eval_value(self.state, repr)
            elif isinstance(repr, (Format, Format.Enum)):
                var_value = eval_format(self.state, repr)
            else:
                # decoder
                var_value = repr(eval_value(self.state, signal))
            self.vcd_writer.change(vcd_var, timestamp, var_value)

    def update_memory(self, timestamp, memory, addr):
        if memory not in self.vcd_memory_vars:
            return
        for vcd_var, repr in self.vcd_memory_vars[memory][addr]:
            if isinstance(repr, Value):
                var_value = eval_value(self.state, repr)
            else:
                var_value = eval_format(self.state, repr)
            self.vcd_writer.change(vcd_var, timestamp, var_value)

    def close(self, timestamp):
        if self.vcd_writer is not None:
            self.vcd_writer.close(timestamp)

        if self.gtkw_save is not None:
            self.gtkw_save.dumpfile(self.vcd_file.name)
            self.gtkw_save.dumpfile_size(self.vcd_file.tell())

            self.gtkw_save.treeopen("top")

            def traverse_traces(traces):
                if isinstance(traces, data.View):
                    with self.gtkw_save.group("view"):
                        traverse_traces(Value.cast(traces))
                elif isinstance(traces, ValueLike):
                    trace = Value.cast(traces)
                    if isinstance(traces, MemoryData._Row):
                        for name in self.gtkw_memory_names[traces._memory][traces._index]:
                            self.gtkw_save.trace(name)
                    else:
                        for trace_signal in trace._rhs_signals():
                            for name in self.gtkw_signal_names[trace_signal]:
                                self.gtkw_save.trace(name)
                elif isinstance(traces, MemoryData):
                    for row_names in self.gtkw_memory_names[traces]:
                        for name in row_names:
                            self.gtkw_save.trace(name)
                elif hasattr(traces, "signature") and isinstance(traces.signature, wiring.Signature):
                    with self.gtkw_save.group("interface"):
                        for _, _, member in traces.signature.flatten(traces):
                            traverse_traces(member)
                elif isinstance(traces, list) or isinstance(traces, tuple):
                    for trace in traces:
                        traverse_traces(trace)
                elif isinstance(traces, dict):
                    for name, trace in traces.items():
                        with self.gtkw_save.group(name):
                            traverse_traces(trace)
                else:
                    assert False # :nocov:
            traverse_traces(self.traces)

        if self.close_vcd:
            self.vcd_file.close()
        if self.close_gtkw:
            self.gtkw_file.close()


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
        self._vcd_writers = []
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
            changed = set() if self._vcd_writers else None

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

            for vcd_writer in self._vcd_writers:
                now_plus_deltas = self._now_plus_deltas(vcd_writer.fs_per_delta)
                for change in changed:
                    if type(change) is _PySignalState:
                        signal_state = change
                        vcd_writer.update_signal(now_plus_deltas,
                            signal_state.signal)
                    elif type(change) is _PyMemoryChange:
                        vcd_writer.update_memory(now_plus_deltas, change.state.memory,
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
    def write_vcd(self, *, vcd_file, gtkw_file, traces, fs_per_delta):
        vcd_writer = _VCDWriter(self._state, self._design,
            vcd_file=vcd_file, gtkw_file=gtkw_file, traces=traces, fs_per_delta=fs_per_delta)
        try:
            self._vcd_writers.append(vcd_writer)
            yield
        finally:
            vcd_writer.close(self._now_plus_deltas(vcd_writer.fs_per_delta))
            self._vcd_writers.remove(vcd_writer)
