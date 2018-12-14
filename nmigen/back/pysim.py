import math
import inspect
from contextlib import contextmanager
from vcd import VCDWriter
from vcd.gtkw import GTKWSave

from ..tools import flatten
from ..fhdl.ast import *
from ..fhdl.xfrm import ValueTransformer, StatementTransformer


__all__ = ["Simulator", "Delay", "Tick", "Passive", "DeadlineError"]


class DeadlineError(Exception):
    pass


class _State:
    __slots__ = ("curr", "curr_dirty", "next", "next_dirty")

    def __init__(self):
        self.curr = ValueDict()
        self.next = ValueDict()
        self.curr_dirty = ValueSet()
        self.next_dirty = ValueSet()

    def set(self, signal, value):
        assert isinstance(value, int)
        if self.next[signal] != value:
            self.next_dirty.add(signal)
            self.next[signal] = value

    def commit(self, signal):
        old_value = self.curr[signal]
        if self.curr[signal] != self.next[signal]:
            self.next_dirty.remove(signal)
            self.curr_dirty.add(signal)
            self.curr[signal] = self.next[signal]
        new_value = self.curr[signal]
        return old_value, new_value


normalize = Const.normalize


class _RHSValueCompiler(ValueTransformer):
    def __init__(self, sensitivity=None):
        self.sensitivity = sensitivity

    def on_Const(self, value):
        return lambda state: value.value

    def on_Signal(self, value):
        if self.sensitivity is not None:
            self.sensitivity.add(value)
        return lambda state: state.curr[value]

    def on_ClockSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_ResetSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_Operator(self, value):
        shape = value.shape()
        if len(value.operands) == 1:
            arg, = map(self, value.operands)
            if value.op == "~":
                return lambda state: normalize(~arg(state), shape)
            if value.op == "-":
                return lambda state: normalize(-arg(state), shape)
            if value.op == "b":
                return lambda state: normalize(bool(arg(state)), shape)
        elif len(value.operands) == 2:
            lhs, rhs = map(self, value.operands)
            if value.op == "+":
                return lambda state: normalize(lhs(state) + rhs(state), shape)
            if value.op == "-":
                return lambda state: normalize(lhs(state) - rhs(state), shape)
            if value.op == "&":
                return lambda state: normalize(lhs(state) & rhs(state), shape)
            if value.op == "|":
                return lambda state: normalize(lhs(state) | rhs(state), shape)
            if value.op == "^":
                return lambda state: normalize(lhs(state) ^ rhs(state), shape)
            if value.op == "==":
                return lambda state: normalize(lhs(state) == rhs(state), shape)
            if value.op == "!=":
                return lambda state: normalize(lhs(state) != rhs(state), shape)
            if value.op == "<":
                return lambda state: normalize(lhs(state) <  rhs(state), shape)
            if value.op == "<=":
                return lambda state: normalize(lhs(state) <= rhs(state), shape)
            if value.op == ">":
                return lambda state: normalize(lhs(state) >  rhs(state), shape)
            if value.op == ">=":
                return lambda state: normalize(lhs(state) >= rhs(state), shape)
        elif len(value.operands) == 3:
            if value.op == "m":
                sel, val1, val0 = map(self, value.operands)
                return lambda state: val1(state) if sel(state) else val0(state)
        raise NotImplementedError("Operator '{!r}' not implemented".format(value.op)) # :nocov:

    def on_Slice(self, value):
        shape = value.shape()
        arg   = self(value.value)
        shift = value.start
        mask  = (1 << (value.end - value.start)) - 1
        return lambda state: normalize((arg(state) >> shift) & mask, shape)

    def on_Part(self, value):
        raise NotImplementedError

    def on_Cat(self, value):
        shape  = value.shape()
        parts  = []
        offset = 0
        for opnd in value.operands:
            parts.append((offset, (1 << len(opnd)) - 1, self(opnd)))
            offset += len(opnd)
        def eval(state):
            result = 0
            for offset, mask, opnd in parts:
                result |= (opnd(state) & mask) << offset
            return normalize(result, shape)
        return eval

    def on_Repl(self, value):
        shape  = value.shape()
        offset = len(value.value)
        mask   = (1 << len(value.value)) - 1
        count  = value.count
        opnd   = self(value.value)
        def eval(state):
            result = 0
            for _ in range(count):
                result <<= offset
                result  |= opnd(state)
            return normalize(result, shape)
        return eval


class _StatementCompiler(StatementTransformer):
    def __init__(self):
        self.sensitivity  = ValueSet()
        self.rhs_compiler = _RHSValueCompiler(self.sensitivity)

    def lhs_compiler(self, value):
        # TODO
        return lambda state, arg: state.set(value, arg)

    def on_Assign(self, stmt):
        assert isinstance(stmt.lhs, Signal)
        shape = stmt.lhs.shape()
        lhs   = self.lhs_compiler(stmt.lhs)
        rhs   = self.rhs_compiler(stmt.rhs)
        def run(state):
            lhs(state, normalize(rhs(state), shape))
        return run

    def on_Switch(self, stmt):
        test  = self.rhs_compiler(stmt.test)
        cases = []
        for value, stmts in stmt.cases.items():
            if "-" in value:
                mask  = "".join("0" if b == "-" else "1" for b in value)
                value = "".join("0" if b == "-" else  b  for b in value)
            else:
                mask  = "1" * len(value)
            mask  = int(mask,  2)
            value = int(value, 2)
            def make_test(mask, value):
                return lambda test: test & mask == value
            cases.append((make_test(mask, value), self.on_statements(stmts)))
        def run(state):
            test_value = test(state)
            for check, body in cases:
                if check(test_value):
                    body(state)
                    return
        return run

    def on_statements(self, stmts):
        stmts = [self.on_statement(stmt) for stmt in stmts]
        def run(state):
            for stmt in stmts:
                stmt(state)
        return run


class Simulator:
    def __init__(self, fragment, vcd_file=None, gtkw_file=None, traces=()):
        self._fragment        = fragment

        self._domains         = {}            # str/domain -> ClockDomain
        self._domain_triggers = ValueDict()   # Signal -> str/domain
        self._domain_signals  = {}            # str/domain -> {Signal}

        self._signals         = ValueSet()    # {Signal}
        self._comb_signals    = ValueSet()    # {Signal}
        self._sync_signals    = ValueSet()    # {Signal}
        self._user_signals    = ValueSet()    # {Signal}

        self._started         = False
        self._timestamp       = 0.
        self._epsilon         = 1e-10
        self._fastest_clock   = self._epsilon
        self._state           = _State()

        self._processes       = set()         # {process}
        self._passive         = set()         # {process}
        self._suspended       = set()         # {process}
        self._wait_deadline   = {}            # process -> float/timestamp
        self._wait_tick       = {}            # process -> str/domain

        self._funclets        = ValueDict()   # Signal -> set(lambda)

        self._vcd_file        = vcd_file
        self._vcd_writer      = None
        self._vcd_signals     = ValueDict()   # signal -> set(vcd_signal)
        self._vcd_names       = ValueDict()   # signal -> str/name
        self._gtkw_file       = gtkw_file
        self._traces          = traces

    def _check_process(self, process):
        if inspect.isgeneratorfunction(process):
            process = process()
        if not inspect.isgenerator(process):
            raise TypeError("Cannot add a process '{!r}' because it is not a generator or"
                            "a generator function"
                            .format(process))
        return process

    def add_process(self, process):
        process = self._check_process(process)
        self._processes.add(process)

    def add_sync_process(self, process, domain="sync"):
        process = self._check_process(process)
        def sync_process():
            try:
                result = None
                while True:
                    if result is None:
                        result = Tick(domain)
                    result = process.send((yield result))
            except StopIteration:
                pass
        self.add_process(sync_process())

    def add_clock(self, period, phase=None, domain="sync"):
        if self._fastest_clock == self._epsilon or period < self._fastest_clock:
            self._fastest_clock = period

        half_period = period / 2
        if phase is None:
            phase = half_period
        clk = self._domains[domain].clk
        def clk_process():
            yield Passive()
            yield Delay(phase)
            while True:
                yield clk.eq(1)
                yield Delay(half_period)
                yield clk.eq(0)
                yield Delay(half_period)
        self.add_process(clk_process())

    def __enter__(self):
        if self._vcd_file:
            self._vcd_writer = VCDWriter(self._vcd_file, timescale="100 ps",
                                         comment="Generated by nMigen")

        root_fragment = self._fragment.prepare()

        self._domains = root_fragment.domains
        for domain, cd in self._domains.items():
            self._domain_triggers[cd.clk] = domain
            if cd.rst is not None:
                self._domain_triggers[cd.rst] = domain
            self._domain_signals[domain] = ValueSet()

        hierarchy = {}
        def add_fragment(fragment, scope=()):
            hierarchy[fragment] = scope
            for subfragment, name in fragment.subfragments:
                add_fragment(subfragment, (*scope, name))
        add_fragment(root_fragment)

        for fragment, fragment_name in hierarchy.items():
            for signal in fragment.iter_signals():
                self._signals.add(signal)

                self._state.curr[signal] = self._state.next[signal] = \
                    normalize(signal.reset, signal.shape())
                self._state.curr_dirty.add(signal)

                if not self._vcd_writer:
                    continue

                if signal not in self._vcd_signals:
                    self._vcd_signals[signal] = set()

                for subfragment, name in fragment.subfragments:
                    if signal in subfragment.ports:
                        var_name = "{}_{}".format(name, signal.name)
                        break
                else:
                    var_name = signal.name

                if signal.decoder:
                    var_type = "string"
                    var_size = 1
                    var_init = signal.decoder(signal.reset).replace(" ", "_")
                else:
                    var_type = "wire"
                    var_size = signal.nbits
                    var_init = signal.reset

                suffix = None
                while True:
                    try:
                        if suffix is None:
                            var_name_suffix = var_name
                        else:
                            var_name_suffix = "{}${}".format(var_name, suffix)
                        self._vcd_signals[signal].add(self._vcd_writer.register_var(
                            scope=".".join(fragment_name), name=var_name_suffix,
                            var_type=var_type, size=var_size, init=var_init))
                        if signal not in self._vcd_names:
                            self._vcd_names[signal] = ".".join(fragment_name + (var_name_suffix,))
                        break
                    except KeyError:
                        suffix = (suffix or 0) + 1

            for domain, signals in fragment.drivers.items():
                if domain is None:
                    self._comb_signals.update(signals)
                else:
                    self._sync_signals.update(signals)
                    self._domain_signals[domain].update(signals)

            statements = []
            for signal in fragment.iter_comb():
                statements.append(signal.eq(signal.reset))
            for domain, signal in fragment.iter_sync():
                statements.append(signal.eq(signal))
            statements += fragment.statements

            compiler = _StatementCompiler()
            funclet = compiler(statements)

            def add_funclet(signal, funclet):
                if signal not in self._funclets:
                    self._funclets[signal] = set()
                self._funclets[signal].add(funclet)

            for signal in compiler.sensitivity:
                add_funclet(signal, funclet)
            for domain, cd in fragment.domains.items():
                add_funclet(cd.clk, funclet)
                if cd.rst is not None:
                    add_funclet(cd.rst, funclet)

        self._user_signals = self._signals - self._comb_signals - self._sync_signals

        return self

    def _update_dirty_signals(self):
        """Perform the statement part of IR processes (aka RTLIL case)."""
        # First, for all dirty signals, use sensitivity lists to determine the set of fragments
        # that need their statements to be reevaluated because the signals changed at the previous
        # delta cycle.
        funclets = set()
        while self._state.curr_dirty:
            signal = self._state.curr_dirty.pop()
            if signal in self._funclets:
                funclets.update(self._funclets[signal])

        # Second, compute the values of all signals at the start of the next delta cycle, by
        # running precompiled statements.
        for funclet in funclets:
            funclet(self._state)

    def _commit_signal(self, signal, domains):
        """Perform the driver part of IR processes (aka RTLIL sync), for individual signals."""
        # Take the computed value (at the start of this delta cycle) of a signal (that could have
        # come from an IR process that ran earlier, or modified by a simulator process) and update
        # the value for this delta cycle.
        old, new = self._state.commit(signal)

        # If the signal is a clock that triggers synchronous logic, record that fact.
        if (old, new) == (0, 1) and signal in self._domain_triggers:
            domains.add(self._domain_triggers[signal])

        if self._vcd_writer and old != new:
            # Finally, dump the new value to the VCD file.
            for vcd_signal in self._vcd_signals[signal]:
                if signal.decoder:
                    var_value = signal.decoder(new).replace(" ", "_")
                else:
                    var_value = new
                self._vcd_writer.change(vcd_signal, self._timestamp / self._epsilon, var_value)

    def _commit_comb_signals(self, domains):
        """Perform the comb part of IR processes (aka RTLIL always)."""
        # Take the computed value (at the start of this delta cycle) of every comb signal and
        # update the value for this delta cycle.
        for signal in self._state.next_dirty:
            if signal in self._comb_signals or signal in self._user_signals:
                self._commit_signal(signal, domains)

    def _commit_sync_signals(self, domains):
        """Perform the sync part of IR processes (aka RTLIL posedge)."""
        # At entry, `domains` contains a list of every simultaneously triggered sync update.
        while domains:
            # Advance the timeline a bit (purely for observational purposes) and commit all of them
            # at the same timestamp.
            self._timestamp += self._epsilon
            curr_domains, domains = domains, set()

            while curr_domains:
                domain = curr_domains.pop()

                # Take the computed value (at the start of this delta cycle) of every sync signal
                # in this domain and update the value for this delta cycle. This can trigger more
                # synchronous logic, so record that.
                for signal in self._state.next_dirty:
                    if signal in self._domain_signals[domain]:
                        self._commit_signal(signal, domains)

                # Wake up any simulator processes that wait for a domain tick.
                for process, wait_domain in list(self._wait_tick.items()):
                    if domain == wait_domain:
                        del self._wait_tick[process]
                        self._suspended.remove(process)

            # Unless handling synchronous logic above has triggered more synchronous logic (which
            # can happen e.g. if a domain is clocked off a clock divisor in fabric), we're done.
            # Otherwise, do one more round of updates.

    def _run_process(self, process):
        def format_process(process):
            frame = process.gi_frame
            return "{}:{}".format(inspect.getfile(frame), inspect.getlineno(frame))

        try:
            cmd = process.send(None)
            while True:
                if isinstance(cmd, Delay):
                    if cmd.interval is None:
                        interval = self._epsilon
                    else:
                        interval = cmd.interval
                    self._wait_deadline[process] = self._timestamp + interval
                    self._suspended.add(process)

                elif isinstance(cmd, Tick):
                    self._wait_tick[process] = cmd.domain
                    self._suspended.add(process)

                elif isinstance(cmd, Passive):
                    self._passive.add(process)

                elif isinstance(cmd, Value):
                    compiler = _RHSValueCompiler()
                    funclet = compiler(cmd)
                    cmd = process.send(funclet(self._state))
                    continue

                elif isinstance(cmd, Assign):
                    lhs_signals = cmd.lhs._lhs_signals()
                    for signal in lhs_signals:
                        if not signal in self._signals:
                            raise ValueError("Process '{}' sent a request to set signal '{!r}', "
                                             "which is not a part of simulation"
                                             .format(format_process(process), signal))
                        if signal in self._comb_signals:
                            raise ValueError("Process '{}' sent a request to set signal '{!r}', "
                                             "which is a part of combinatorial assignment in "
                                             "simulation"
                                             .format(format_process(process), signal))

                    compiler = _StatementCompiler()
                    funclet = compiler(cmd)
                    funclet(self._state)

                    domains = set()
                    for signal in lhs_signals:
                        self._commit_signal(signal, domains)
                    self._commit_sync_signals(domains)

                else:
                    raise TypeError("Received unsupported command '{!r}' from process '{}'"
                                    .format(cmd, format_process(process)))

                break

        except StopIteration:
            self._processes.remove(process)
            self._passive.discard(process)

        except Exception as e:
            process.throw(e)

    def step(self, run_passive=False):
        deadline = None
        if self._wait_deadline:
            # We might run some delta cycles, and we have simulator processes waiting on
            # a deadline. Take care to not exceed the closest deadline.
            deadline = min(self._wait_deadline.values())

        # Are there any delta cycles we should run?
        while self._state.curr_dirty:
            self._timestamp += self._epsilon
            if deadline is not None and self._timestamp >= deadline:
                # Oops, we blew the deadline. We *could* run the processes now, but this is
                # virtually certainly a logic loop and a design bug, so bail out instead.d
                raise DeadlineError("Delta cycles exceeded process deadline; combinatorial loop?")

            domains = set()
            self._update_dirty_signals()
            self._commit_comb_signals(domains)
            self._commit_sync_signals(domains)

        # Are there any processes that haven't had a chance to run yet?
        if len(self._processes) > len(self._suspended):
            # Schedule an arbitrary one.
            process = (self._processes - set(self._suspended)).pop()
            self._run_process(process)
            return True

        # All processes are suspended. Are any of them active?
        if len(self._processes) > len(self._passive) or run_passive:
            # Are any of them suspended before a deadline?
            if self._wait_deadline:
                # Schedule the one with the lowest deadline.
                process, deadline = min(self._wait_deadline.items(), key=lambda x: x[1])
                del self._wait_deadline[process]
                self._suspended.remove(process)
                self._timestamp = deadline
                self._run_process(process)
                return True

        # No processes, or all processes are passive. Nothing to do!
        return False

    def run(self):
        while self.step():
            pass

    def run_until(self, deadline, run_passive=False):
        while self._timestamp < deadline:
            if not self.step(run_passive):
                return False

        return True

    def __exit__(self, *args):
        if self._vcd_writer:
            self._vcd_writer.close(self._timestamp / self._epsilon)

        if self._vcd_file and self._gtkw_file:
            gtkw_save = GTKWSave(self._gtkw_file)
            if hasattr(self._vcd_file, "name"):
                gtkw_save.dumpfile(self._vcd_file.name)
            if hasattr(self._vcd_file, "tell"):
                gtkw_save.dumpfile_size(self._vcd_file.tell())

            gtkw_save.treeopen("top")
            gtkw_save.zoom_markers(math.log(self._epsilon / self._fastest_clock) - 14)

            def add_trace(signal, **kwargs):
                if signal in self._vcd_names:
                    if len(signal) > 1:
                        suffix = "[{}:0]".format(len(signal) - 1)
                    else:
                        suffix = ""
                    gtkw_save.trace(self._vcd_names[signal] + suffix, **kwargs)

            for domain, cd in self._domains.items():
                with gtkw_save.group("d.{}".format(domain)):
                    if cd.rst is not None:
                        add_trace(cd.rst)
                    add_trace(cd.clk)

            for signal in self._traces:
                add_trace(signal)

        if self._vcd_file:
            self._vcd_file.close()
        if self._gtkw_file:
            self._gtkw_file.close()
