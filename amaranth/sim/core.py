import inspect
import warnings

from .._utils import deprecated
from ..hdl import Value, ValueLike, MemoryData, ClockDomain, Fragment
from ..hdl._ir import DriverConflict
from ._base import BaseEngine
from ._async import DomainReset, BrokenTrigger
from ._pycoro import Tick, Settle, Delay, Passive, Active, coro_wrapper


__all__ = [
    "DomainReset", "BrokenTrigger",
    "Simulator",
    # deprecated
    "Settle", "Delay", "Tick", "Passive", "Active",
]


def _seconds_to_femtos(delay: float):
    return int(delay * 1e15) # seconds to femtoseconds


class Simulator:
    # Simulator engines aren't yet a part of the public API.
    """Simulator(toplevel)

    Simulator for Amaranth designs.

    The simulator accepts a *top-level design* (an :ref:`elaboratable <lang-elaboration>`),
    *processes* that replace circuits with behavioral code, *clocks* that drive clock domains, and
    *testbenches* that exercise the circuits and verify that they work correctly.

    The simulator lifecycle consists of four stages:

    1. The simulator is created: ::

        sim = Simulator(design)

    2. Processes, clocks, and testbenches are added as necessary: ::

        sim.add_clock(1e-6)
        sim.add_clock(1e-7, domain="fast")
        sim.add_process(process_instr_decoder)
        sim.add_testbench(testbench_cpu_execute)

    3. The simulation is run: ::

        with sim.write_vcd("waveform.vcd"):
            sim.run()

    4. (Optional) The simulator is reset: ::

        sim.reset()

    After the simulator is reset, it may be reused to run the simulation again.

    .. note::

        Resetting the simulator can also be used to amortize the startup cost of repeatedly
        simulating a large design.

    Arguments
    ---------
    toplevel : :class:`~amaranth.hdl.Elaboratable`
        Simulated design.
    """
    def __init__(self, toplevel, *, engine="pysim"):
        if isinstance(engine, type) and issubclass(engine, BaseEngine):
            pass
        elif engine == "pysim":
            from .pysim import PySimEngine
            engine = PySimEngine
        else:
            raise TypeError(
                f"Value {engine!r} is not a simulation engine class or a simulation engine name")

        self._design  = Fragment.get(toplevel, platform=None).prepare()
        self._engine  = engine(self._design)
        self._clocked = set()
        self._running = False

    def add_clock(self, period, *, phase=None, domain="sync", if_exists=False):
        """Add a clock to the simulation.

        Adds a stimulus that toggles the clock signal of :py:`domain` at a 50% duty cycle.

        The driven clock signal will toggle every half-:py:`period` seconds starting at :py:`phase`
        seconds after the beginning of the simulation; if not specified, :py:`phase` defaults to
        half-:py:`period` to avoid coinciding the first active edge with the beginning of
        the simulation.

        The clock domain to drive is selected by the :py:`domain` argument, which may be
        a :class:`~amaranth.hdl.ClockDomain` object or a :class:`str`. If it is a string,
        the clock domain with that name is retrieved from the :py:`toplevel` elaboratable.

        Raises
        ------
        :exc:`NameError`
            If :py:`domain` is a :class:`str`, the :py:`toplevel` elaboratable does not have
            a clock domain with that name, and :py:`if_exists` is :py:`False`.
        :exc:`~amaranth.hdl.DriverConflict`
            If :py:`domain` already has a clock driving it.
        :exc:`RuntimeError`
            If the simulation has been advanced since its creation or last reset.
        """
        if self._running:
            raise RuntimeError(r"Cannot add a clock to a running simulation")
        if isinstance(domain, ClockDomain):
            if (domain.name in self._design.fragment.domains and
                    domain is not self._design.fragment.domains[domain.name]):
                warnings.warn(
                    f"Adding a clock that drives a clock domain object named {domain.name!r}, "
                    f"which is distinct from an identically named domain in the simulated design",
                    UserWarning, stacklevel=2)
        elif domain in self._design.fragment.domains:
            domain = self._design.fragment.domains[domain]
        elif if_exists:
            return
        else:
            raise NameError(f"Domain {domain!r} is not present in simulation")
        if domain in self._clocked:
            raise DriverConflict(f"Domain {domain.name!r} already has a clock driving it")

        period_fs = _seconds_to_femtos(period)
        if phase is None:
            phase_fs = _seconds_to_femtos(period / 2)
        else:
            phase_fs = _seconds_to_femtos(phase)
        self._engine.add_clock_process(domain.clk, phase=phase_fs, period=period_fs)
        self._clocked.add(domain)

    @staticmethod
    def _check_function(function, *, kind):
        if inspect.isasyncgenfunction(function):
            raise TypeError(
                f"Cannot add a {kind} {function!r} because it is an async generator function "
                f"(there is likely a stray `yield` in the function)")
        if inspect.iscoroutine(function):
            raise TypeError(
                f"Cannot add a {kind} {function!r} because it is a coroutine object instead "
                f"of a function (pass the function itself instead of calling it)")
        if inspect.isgenerator(function) or inspect.isasyncgen(function):
            raise TypeError(
                f"Cannot add a {kind} {function!r} because it is a generator object instead "
                f"of a function (pass the function itself instead of calling it)")
        if not (inspect.isgeneratorfunction(function) or inspect.iscoroutinefunction(function)):
            raise TypeError(
                f"Cannot add a {kind} {function!r} because it is not an async function or "
                f"generator function")
        return function

    def add_testbench(self, constructor, *, background=False):
        """Add a testbench to the simulation.

        Adds a testbench that runs concurrently with the :py:`toplevel` elaboratable and is able to
        manipulate its inputs, outputs, and state.

        The behavior of the testbench is defined by its *constructor function*, which is
        an :py:`async` function that takes a single argument, the :class:`SimulatorContext`: ::

            async def testbench(ctx):
                ...
                await ctx.tick()
                ...

            sim.add_testbench(testbench)

        This method does not accept coroutines. Rather, the provided :py:`constructor` coroutine
        function is called immediately when the testbench is added to create a coroutine, as well as
        by the :meth:`reset` method.

        The testbench can be *critical* (the default) or *background* (if the :py:`background=True`
        argument is specified). The :meth:`run` method will continue advancing the simulation while
        any critical testbenches or processes are running, and will exit when only background
        testbenches or processes remain. A background testbench can temporarily become critical
        using the :meth:`~SimulatorContext.critical` context manager.

        At each point in time, all of the non-waiting testbenches are executed in the order in
        which they were added. If two testbenches share state, or must manipulate the design in
        a coordinated way, they may rely on this execution order for correctness.

        Raises
        ------
        :exc:`RuntimeError`
            If the simulation has been advanced since its creation or last reset.
        """
        if self._running:
            raise RuntimeError(r"Cannot add a testbench to a running simulation")
        constructor = self._check_function(constructor, kind="testbench")
        if inspect.iscoroutinefunction(constructor):
            self._engine.add_async_testbench(self, constructor, background=background)
        else:
            # TODO(amaranth-0.6): remove
            warnings.warn(
                f"Generator-based testbenches are deprecated per RFC 36. Use async "
                f"testbenches instead.",
                DeprecationWarning, stacklevel=1)
            constructor = coro_wrapper(constructor, testbench=True)
            self._engine.add_async_testbench(self, constructor, background=background)

    def add_process(self, process):
        """Add a process to the simulation.

        Adds a process that is evaluated as a part of the :py:`toplevel` elaboratable and is able to
        replace circuits with Python code.

        The behavior of the process is defined by its *constructor function*, which is
        an :py:`async` function that takes a single argument, the :class:`SimulatorContext`: ::

            async def process(ctx):
                async for clk_edge, rst, ... in ctx.tick().sample(...):
                    ...

            sim.add_process(process)

        This method does not accept coroutines. Rather, the provided :py:`constructor` coroutine
        function is called immediately when the procss is added to create a coroutine, as well as
        by the :meth:`reset` method.

        Processes can be *critical* or *background*, and are always background when added.
        The :meth:`run` method will continue advancing the simulation while any critical testbenches
        or processes are running, and will exit when only background testbenches or processes
        remain. A background process can temporarily become critical using
        the :meth:`~SimulatorContext.critical` context manager.

        At each point in time, all of the non-waiting processes are executed in an arbitrary order
        that may be different between individual simulation runs.

        .. warning::

            If two processes share state, they must do so in a way that does not rely on
            a particular order of execution for correctness.

            Preferably, the shared state would be stored in :class:`~amaranth.hdl.Signal`\\ s (even
            if it is not intended to be a part of a circuit), with access to it synchronized using
            :py:`await ctx.tick().sample(...)`. Such state is visible in a waveform viewer,
            simplifying debugging.

        Raises
        ------
        :exc:`RuntimeError`
            If the simulation has been advanced since its creation or last reset.
        """
        if self._running:
            raise RuntimeError(r"Cannot add a process to a running simulation")
        process = self._check_function(process, kind="process")
        if inspect.iscoroutinefunction(process):
            self._engine.add_async_process(self, process)
        else:
            def wrapper():
                # Only start a process after comb settling, so that the initial values are correct.
                yield Active()
                yield object.__new__(Settle)
                yield from process()
            # TODO(amaranth-0.6): remove
            warnings.warn(
                f"Generator-based processes are deprecated per RFC 36. Use async "
                f"processes instead.",
                DeprecationWarning, stacklevel=1)
            wrap_process = coro_wrapper(wrapper, testbench=False)
            self._engine.add_async_process(self, wrap_process)

    @deprecated("The `add_sync_process` method is deprecated per RFC 27. Use `add_process` or "
                "`add_testbench` instead.")
    def add_sync_process(self, process, *, domain="sync"):
        process = self._check_function(process, kind="process")
        def wrapper():
            # Only start a sync process after the first clock edge (or reset edge, if the domain
            # uses an asynchronous reset). This matches the behavior of synchronous FFs.
            generator = process()
            result = None
            exception = None
            yield Active()
            yield Tick(domain)
            while True:
                try:
                    if exception is None:
                        command = generator.send(result)
                    else:
                        command = generator.throw(exception)
                except StopIteration:
                    break
                try:
                    result = yield command
                    exception = None
                except Exception as e:
                    result = None
                    exception = e
        wrap_process = coro_wrapper(wrapper, testbench=False, default_cmd=Tick(domain))
        self._engine.add_async_process(self, wrap_process)

    def run(self):
        """Run the simulation indefinitely.

        This method advances the simulation while any critical testbenches or processes continue
        executing. It is equivalent to::

            while self.advance():
                pass
        """
        while self.advance():
            pass

    def run_until(self, deadline, *, run_passive=None):
        """run_until(deadline)

        Run the simulation until a specific point in time.

        This method advances the simulation until the simulation time reaches :py:`deadline`,
        without regard for whether there are critical testbenches or processes executing.

        ..
            This should show the code like in :meth:`run` once the code is not horrible.
        """
        if run_passive is not None:
            # TODO(amaranth-0.6): remove
            warnings.warn(
                f"The `run_passive` argument of `run_until()` has been removed as a part of "
                f"transition to RFC 36.",
                DeprecationWarning, stacklevel=1)
        deadline_fs = _seconds_to_femtos(deadline)
        assert self._engine.now <= deadline_fs
        while self._engine.now < deadline_fs:
            self.advance()

    def advance(self):
        """Advance the simulation.

        This method advances the simulation by one time step. After this method completes, all of
        the events scheduled for the current point in time will have taken effect, and the current
        point in time was advanced to the closest point in the future for which any events are
        scheduled (which may be the same point in time).

        The non-waiting testbenches are executed in the order they were added, and the processes
        are executed as necessary.

        Returns :py:`True` if the simulation contains any critical testbenches or processes, and
        :py:`False` otherwise.
        """
        self._running = True
        return self._engine.advance()

    def write_vcd(self, vcd_file, gtkw_file=None, *, traces=(), fs_per_delta=0):
        # `fs_per_delta`` is not currently documented; it is not clear if we want to expose
        # the concept of "delta cycles" in the surface API. Something like `fs_per_step` might be
        # more appropriate.
        """write_vcd(vcd_file, gtkw_file=None, *, traces=())

        Capture waveforms to a file.

        This context manager captures waveforms for each signal and memory that is referenced from
        :py:`toplevel`, as well as any additional signals or memories specified in :py:`traces`,
        and saves them to :py:`vcd_file`. If :py:`gtkw_file` is provided, it is populated with
        a GTKWave save file displaying :py:`traces` when opened.

        Use this context manager to wrap a call to :meth:`run` or :meth:`run_until`: ::

            with sim.write_vcd("simulation.vcd"):
                sim.run()

        The :py:`vcd_file` and :py:`gtkw_file` arguments accept either a :term:`python:file object`
        or a filename. If a file object is provided, it is closed when exiting the context manager
        (once the simulation completes or encounters an error).

        The :py:`traces` argument accepts a *trace specification*, which can be one of:

        * A :class:`~amaranth.hdl.ValueLike` object, such as a :class:`~amaranth.hdl.Signal`;
        * A :class:`~amaranth.hdl.MemoryData` object or an individual row retrieved from one;
        * A :class:`tuple` or :class:`list` containing trace specifications;
        * A :class:`dict` associating :class:`str` names to trace specifications;
        * An :ref:`interface object <wiring>`.

        Raises
        ------
        :exc:`TypeError`
            If a trace specification refers to a signal with a private name.
        """
        if self._engine.now != 0:
            for file in (vcd_file, gtkw_file):
                if hasattr(file, "close"):
                    file.close()

            # FIXME: can this restriction be lifted?
            raise ValueError("Cannot start writing waveforms after advancing simulation time")

        def traverse_traces(traces):
            if isinstance(traces, ValueLike):
                trace_cast = Value.cast(traces)
                if isinstance(trace_cast, MemoryData._Row):
                    return
                for trace_signal in trace_cast._rhs_signals():
                    if trace_signal.name == "":
                        if trace_signal is traces:
                            raise TypeError("Cannot trace signal with private name")
                        else:
                            raise TypeError(
                                f"Cannot trace signal with private name (within {traces!r})")
            elif isinstance(traces, (list, tuple)):
                for trace in traces:
                    traverse_traces(trace)
            elif isinstance(traces, dict):
                for trace in traces.values():
                    traverse_traces(trace)

        traverse_traces(traces)

        return self._engine.write_vcd(
            vcd_file=vcd_file, gtkw_file=gtkw_file, traces=traces, fs_per_delta=fs_per_delta)

    def reset(self):
        """Reset the simulation.

        This method reverts the simulation to its initial state:

        * The value of each signal is changed to its initial value;
        * The contents of each memory is changed to its initial contents;
        * Each clock, testbench, and process is restarted.
        """
        self._engine.reset()
        self._running = False
