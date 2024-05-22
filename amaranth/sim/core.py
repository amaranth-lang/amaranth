import inspect
import warnings

from .._utils import deprecated
from ..hdl._cd import *
from ..hdl._ir import *
from ..hdl._ast import Value, ValueLike
from ..hdl._mem import MemoryData
from ._base import BaseEngine
from ._async import DomainReset, BrokenTrigger
from ._pycoro import Tick, Settle, Delay, Passive, Active, coro_wrapper


__all__ = [
    "DomainReset", "BrokenTrigger",
    "Simulator",
    # deprecated
    "Settle", "Delay", "Tick", "Passive", "Active",
]


class Simulator:
    def __init__(self, fragment, *, engine="pysim"):
        if isinstance(engine, type) and issubclass(engine, BaseEngine):
            pass
        elif engine == "pysim":
            from .pysim import PySimEngine
            engine = PySimEngine
        else:
            raise TypeError("Value '{!r}' is not a simulation engine class or "
                            "a simulation engine name"
                            .format(engine))

        self._design   = Fragment.get(fragment, platform=None).prepare()
        self._engine   = engine(self._design)
        self._clocked  = set()

    def _check_process(self, process):
        if not (inspect.isgeneratorfunction(process) or inspect.iscoroutinefunction(process)):
            raise TypeError("Cannot add a process {!r} because it is not a generator function"
                            .format(process))
        return process

    def add_process(self, process):
        process = self._check_process(process)
        if inspect.iscoroutinefunction(process):
            self._engine.add_async_process(self, process)
        else:
            def wrapper():
                # Only start a bench process after comb settling, so that the initial values are correct.
                yield Active()
                yield object.__new__(Settle)
                yield from process()
            wrap_process = coro_wrapper(wrapper, testbench=False)
            self._engine.add_async_process(self, wrap_process)

    def add_testbench(self, process, *, background=False):
        if inspect.iscoroutinefunction(process):
            self._engine.add_async_testbench(self, process, background=background)
        else:
            process = coro_wrapper(process, testbench=True)
            self._engine.add_async_testbench(self, process, background=background)

    @deprecated("The `add_sync_process` method is deprecated per RFC 27. Use `add_process` or `add_testbench` instead.")
    def add_sync_process(self, process, *, domain="sync"):
        process = self._check_process(process)
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

    def add_clock(self, period, *, phase=None, domain="sync", if_exists=False):
        """Add a clock process.

        Adds a process that drives the clock signal of ``domain`` at a 50% duty cycle.

        Arguments
        ---------
        period : float
            Clock period. The process will toggle the ``domain`` clock signal every ``period / 2``
            seconds.
        phase : None or float
            Clock phase. The process will wait ``phase`` seconds before the first clock transition.
            If not specified, defaults to ``period / 2``.
        domain : str or ClockDomain
            Driven clock domain. If specified as a string, the domain with that name is looked up
            in the root fragment of the simulation.
        if_exists : bool
            If ``False`` (the default), raise an error if the driven domain is specified as
            a string and the root fragment does not have such a domain. If ``True``, do nothing
            in this case.
        """
        if isinstance(domain, ClockDomain):
            if (domain.name in self._design.fragment.domains and
                    domain is not self._design.fragment.domains[domain.name]):
                warnings.warn("Adding a clock process that drives a clock domain object "
                              "named {!r}, which is distinct from an identically named domain "
                              "in the simulated design"
                              .format(domain.name),
                              UserWarning, stacklevel=2)
        elif domain in self._design.fragment.domains:
            domain = self._design.fragment.domains[domain]
        elif if_exists:
            return
        else:
            raise ValueError("Domain {!r} is not present in simulation"
                             .format(domain))
        if domain in self._clocked:
            raise ValueError("Domain {!r} already has a clock driving it"
                             .format(domain.name))

        # We represent times internally in 1 fs units, but users supply float quantities of seconds
        period = int(period * 1e15)

        if phase is None:
            # By default, delay the first edge by half period. This causes any synchronous activity
            # to happen at a non-zero time, distinguishing it from the initial values in the waveform
            # viewer.
            phase = period // 2
        else:
            phase = int(phase * 1e15) + period // 2
        self._engine.add_clock_process(domain.clk, phase=phase, period=period)
        self._clocked.add(domain)

    def reset(self):
        """Reset the simulation.

        Assign the initial value to every signal and memory in the simulation, and restart every user process.
        """
        self._engine.reset()

    def advance(self):
        """Advance the simulation.

        Run every process and commit changes until a fixed point is reached, then advance time
        to the closest deadline (if any). If there is an unstable combinational loop,
        this function will never return.

        Returns ``True`` if there are any active processes, ``False`` otherwise.
        """
        return self._engine.advance()

    def run(self):
        """Run the simulation while any processes are active.

        Processes added with :meth:`add_process` and :meth:`add_sync_process` are initially active,
        and may change their status using the ``yield Passive()`` and ``yield Active()`` commands.
        Processes compiled from HDL and added with :meth:`add_clock` are always passive.
        """
        while self.advance():
            pass

    def run_until(self, deadline, *, run_passive=False):
        """Run the simulation until it advances to ``deadline``.

        If ``run_passive`` is ``False``, the simulation also stops when there are no active
        processes, similar to :meth:`run`. Otherwise, the simulation will stop only after it
        advances to or past ``deadline``.

        If the simulation stops advancing, this function will never return.
        """
        # Convert deadline in seconds into internal 1 fs units
        deadline = deadline * 1e15
        assert self._engine.now <= deadline
        while (self.advance() or run_passive) and self._engine.now < deadline:
            pass

    def write_vcd(self, vcd_file, gtkw_file=None, *, traces=(), fs_per_delta=0):
        """Write waveforms to a Value Change Dump file, optionally populating a GTKWave save file.

        This method returns a context manager. It can be used as: ::

            sim = Simulator(frag)
            sim.add_clock(1e-6)
            with sim.write_vcd("dump.vcd", "dump.gtkw"):
                sim.run_until(1e-3)

        Arguments
        ---------
        vcd_file : str or file-like object
            Verilog Value Change Dump file or filename.
        gtkw_file : str or file-like object
            GTKWave save file or filename.
        traces : iterable of Signal
            Signals to display traces for.
        """
        if self._engine.now != 0:
            for file in (vcd_file, gtkw_file):
                if hasattr(file, "close"):
                    file.close()
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
                            raise TypeError(f"Cannot trace signal with private name (within {traces!r})")
            elif isinstance(traces, (list, tuple)):
                for trace in traces:
                    traverse_traces(trace)
            elif isinstance(traces, dict):
                for trace in traces.values():
                    traverse_traces(trace)

        traverse_traces(traces)

        return self._engine.write_vcd(vcd_file=vcd_file, gtkw_file=gtkw_file,
                                      traces=traces, fs_per_delta=fs_per_delta)
