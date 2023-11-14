import inspect
import warnings

from .._utils import deprecated
from ..hdl.cd import *
from ..hdl.ir import *
from ._base import BaseEngine


__all__ = ["Settle", "Delay", "Tick", "Passive", "Active", "Simulator"]


class Command:
    pass


class Settle(Command):
    def __repr__(self):
        return "(settle)"


class Delay(Command):
    def __init__(self, interval=None):
        self.interval = None if interval is None else float(interval)

    def __repr__(self):
        if self.interval is None:
            return "(delay ε)"
        else:
            return f"(delay {self.interval * 1e6:.3}us)"


class Tick(Command):
    def __init__(self, domain="sync"):
        if not isinstance(domain, (str, ClockDomain)):
            raise TypeError("Domain must be a string or a ClockDomain instance, not {!r}"
                            .format(domain))
        assert domain != "comb"
        self.domain = domain

    def __repr__(self):
        return f"(tick {self.domain})"


class Passive(Command):
    def __repr__(self):
        return "(passive)"


class Active(Command):
    def __repr__(self):
        return "(active)"


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

        self._fragment = Fragment.get(fragment, platform=None).prepare()
        self._engine   = engine(self._fragment)
        self._clocked  = set()

    def _check_process(self, process):
        if not (inspect.isgeneratorfunction(process) or inspect.iscoroutinefunction(process)):
            raise TypeError("Cannot add a process {!r} because it is not a generator function"
                            .format(process))
        return process

    def add_process(self, process):
        process = self._check_process(process)
        def wrapper():
            # Only start a bench process after comb settling, so that the reset values are correct.
            yield Settle()
            yield from process()
        self._engine.add_coroutine_process(wrapper, default_cmd=None)

    def add_sync_process(self, process, *, domain="sync"):
        process = self._check_process(process)
        def wrapper():
            # Only start a sync process after the first clock edge (or reset edge, if the domain
            # uses an asynchronous reset). This matches the behavior of synchronous FFs.
            yield Tick(domain)
            yield from process()
        self._engine.add_coroutine_process(wrapper, default_cmd=Tick(domain))

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
            if (domain.name in self._fragment.domains and
                    domain is not self._fragment.domains[domain.name]):
                warnings.warn("Adding a clock process that drives a clock domain object "
                              "named {!r}, which is distinct from an identically named domain "
                              "in the simulated design"
                              .format(domain.name),
                              UserWarning, stacklevel=2)
        elif domain in self._fragment.domains:
            domain = self._fragment.domains[domain]
        elif if_exists:
            return
        else:
            raise ValueError("Domain {!r} is not present in simulation"
                             .format(domain))
        if domain in self._clocked:
            raise ValueError("Domain {!r} already has a clock driving it"
                             .format(domain.name))
        
        # We represent times internally in 1 ps units, but users supply float quantities of seconds
        period = int(period * 1e12)

        if phase is None:
            # By default, delay the first edge by half period. This causes any synchronous activity
            # to happen at a non-zero time, distinguishing it from the reset values in the waveform
            # viewer.
            phase = period // 2
        else:
            phase = int(phase * 1e12) + period // 2
        self._engine.add_clock_process(domain.clk, phase=phase, period=period)
        self._clocked.add(domain)

    def reset(self):
        """Reset the simulation.

        Assign the reset value to every signal in the simulation, and restart every user process.
        """
        self._engine.reset()

    def advance(self):
        """Advance the simulation.

        Run every process and commit changes until a fixed point is reached, then advance time
        to the closest deadline (if any). If there is an unstable combinatorial loop,
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
        # Convert deadline in seconds into internal 1 ps units
        deadline = deadline * 1e12
        assert self._engine.now <= deadline
        while (self.advance() or run_passive) and self._engine.now < deadline:
            pass

    def write_vcd(self, vcd_file, gtkw_file=None, *, traces=()):
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

        return self._engine.write_vcd(vcd_file=vcd_file, gtkw_file=gtkw_file, traces=traces)
