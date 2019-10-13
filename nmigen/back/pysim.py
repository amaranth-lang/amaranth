import math
import inspect
import warnings
from contextlib import contextmanager
from bitarray import bitarray
from vcd import VCDWriter
from vcd.gtkw import GTKWSave

from .._utils import flatten
from ..hdl.ast import *
from ..hdl.ir import *
from ..hdl.xfrm import ValueVisitor, StatementVisitor


__all__ = ["Simulator", "Delay", "Tick", "Passive", "DeadlineError"]


class DeadlineError(Exception):
    pass


class _State:
    __slots__ = ("curr", "curr_dirty", "next", "next_dirty")

    def __init__(self):
        self.curr = []
        self.next = []
        self.curr_dirty = bitarray()
        self.next_dirty = bitarray()

    def add(self, value):
        slot = len(self.curr)
        self.curr.append(value)
        self.next.append(value)
        self.curr_dirty.append(True)
        self.next_dirty.append(False)
        return slot

    def set(self, slot, value):
        if self.next[slot] != value:
            self.next_dirty[slot] = True
            self.next[slot] = value

    def commit(self, slot):
        old_value = self.curr[slot]
        new_value = self.next[slot]
        if old_value != new_value:
            self.next_dirty[slot] = False
            self.curr_dirty[slot] = True
            self.curr[slot] = new_value
        return old_value, new_value

    def flush_curr_dirty(self):
        while True:
            try:
                slot = self.curr_dirty.index(True)
            except ValueError:
                break
            self.curr_dirty[slot] = False
            yield slot

    def iter_next_dirty(self):
        start = 0
        while True:
            try:
                slot  = self.next_dirty.index(True, start)
                start = slot + 1
            except ValueError:
                break
            yield slot


normalize = Const.normalize


class _ValueCompiler(ValueVisitor):
    def on_AnyConst(self, value):
        raise NotImplementedError # :nocov:

    def on_AnySeq(self, value):
        raise NotImplementedError # :nocov:

    def on_Sample(self, value):
        raise NotImplementedError # :nocov:

    def on_Initial(self, value):
        raise NotImplementedError # :nocov:

    def on_Record(self, value):
        return self(Cat(value.fields.values()))


class _RHSValueCompiler(_ValueCompiler):
    def __init__(self, signal_slots, sensitivity=None, mode="rhs"):
        self.signal_slots = signal_slots
        self.sensitivity  = sensitivity
        self.signal_mode  = mode

    def on_Const(self, value):
        return lambda state: value.value

    def on_Signal(self, value):
        if self.sensitivity is not None:
            self.sensitivity.add(value)
        if value not in self.signal_slots:
            # A signal that is neither driven nor a port always remains at its reset state.
            return lambda state: value.reset
        value_slot = self.signal_slots[value]
        if self.signal_mode == "rhs":
            return lambda state: state.curr[value_slot]
        elif self.signal_mode == "lhs":
            return lambda state: state.next[value_slot]
        else:
            raise ValueError # :nocov:

    def on_ClockSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_ResetSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_Operator(self, value):
        shape = value.shape()
        if len(value.operands) == 1:
            arg, = map(self, value.operands)
            if value.operator == "~":
                return lambda state: normalize(~arg(state), shape)
            if value.operator == "-":
                return lambda state: normalize(-arg(state), shape)
            if value.operator == "b":
                return lambda state: normalize(bool(arg(state)), shape)
            if value.operator == "r|":
                return lambda state: normalize(arg(state) != 0, shape)
            if value.operator == "r&":
                val, = value.operands
                mask = (1 << len(val)) - 1
                return lambda state: normalize(arg(state) == mask, shape)
            if value.operator == "r^":
                # Believe it or not, this is the fastest way to compute a sideways XOR in Python.
                return lambda state: normalize(format(arg(state), "b").count("1") % 2, shape)
        elif len(value.operands) == 2:
            lhs, rhs = map(self, value.operands)
            if value.operator == "+":
                return lambda state: normalize(lhs(state) +  rhs(state), shape)
            if value.operator == "-":
                return lambda state: normalize(lhs(state) -  rhs(state), shape)
            if value.operator == "*":
                return lambda state: normalize(lhs(state) *  rhs(state), shape)
            if value.operator == "//":
                def floordiv(lhs, rhs):
                    return 0 if rhs == 0 else lhs // rhs
                return lambda state: normalize(floordiv(lhs(state), rhs(state)), shape)
            if value.operator == "&":
                return lambda state: normalize(lhs(state) &  rhs(state), shape)
            if value.operator == "|":
                return lambda state: normalize(lhs(state) |  rhs(state), shape)
            if value.operator == "^":
                return lambda state: normalize(lhs(state) ^  rhs(state), shape)
            if value.operator == "<<":
                def sshl(lhs, rhs):
                    return lhs << rhs if rhs >= 0 else lhs >> -rhs
                return lambda state: normalize(sshl(lhs(state), rhs(state)), shape)
            if value.operator == ">>":
                def sshr(lhs, rhs):
                    return lhs >> rhs if rhs >= 0 else lhs << -rhs
                return lambda state: normalize(sshr(lhs(state), rhs(state)), shape)
            if value.operator == "==":
                return lambda state: normalize(lhs(state) == rhs(state), shape)
            if value.operator == "!=":
                return lambda state: normalize(lhs(state) != rhs(state), shape)
            if value.operator == "<":
                return lambda state: normalize(lhs(state) <  rhs(state), shape)
            if value.operator == "<=":
                return lambda state: normalize(lhs(state) <= rhs(state), shape)
            if value.operator == ">":
                return lambda state: normalize(lhs(state) >  rhs(state), shape)
            if value.operator == ">=":
                return lambda state: normalize(lhs(state) >= rhs(state), shape)
        elif len(value.operands) == 3:
            if value.operator == "m":
                sel, val1, val0 = map(self, value.operands)
                return lambda state: val1(state) if sel(state) else val0(state)
        raise NotImplementedError("Operator '{}' not implemented".format(value.operator)) # :nocov:

    def on_Slice(self, value):
        shape = value.shape()
        arg   = self(value.value)
        shift = value.start
        mask  = (1 << (value.stop - value.start)) - 1
        return lambda state: normalize((arg(state) >> shift) & mask, shape)

    def on_Part(self, value):
        shape  = value.shape()
        arg    = self(value.value)
        shift  = self(value.offset)
        mask   = (1 << value.width) - 1
        stride = value.stride
        return lambda state: normalize((arg(state) >> shift(state) * stride) & mask, shape)

    def on_Cat(self, value):
        shape  = value.shape()
        parts  = []
        offset = 0
        for opnd in value.parts:
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

    def on_ArrayProxy(self, value):
        shape  = value.shape()
        elems  = list(map(self, value.elems))
        index  = self(value.index)
        def eval(state):
            index_value = index(state)
            if index_value >= len(elems):
                index_value = len(elems) - 1
            return normalize(elems[index_value](state), shape)
        return eval


class _LHSValueCompiler(_ValueCompiler):
    def __init__(self, signal_slots, rhs_compiler):
        self.signal_slots = signal_slots
        self.rhs_compiler = rhs_compiler

    def on_Const(self, value):
        raise TypeError # :nocov:

    def on_Signal(self, value):
        shape = value.shape()
        value_slot = self.signal_slots[value]
        def eval(state, rhs):
            state.set(value_slot, normalize(rhs, shape))
        return eval

    def on_ClockSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_ResetSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_Operator(self, value):
        raise TypeError # :nocov:

    def on_Slice(self, value):
        lhs_r = self.rhs_compiler(value.value)
        lhs_l = self(value.value)
        shift = value.start
        mask  = (1 << (value.stop - value.start)) - 1
        def eval(state, rhs):
            lhs_value  = lhs_r(state)
            lhs_value &= ~(mask << shift)
            lhs_value |= (rhs & mask) << shift
            lhs_l(state, lhs_value)
        return eval

    def on_Part(self, value):
        lhs_r  = self.rhs_compiler(value.value)
        lhs_l  = self(value.value)
        shift  = self.rhs_compiler(value.offset)
        mask   = (1 << value.width) - 1
        stride = value.stride
        def eval(state, rhs):
            lhs_value   = lhs_r(state)
            shift_value = shift(state) * stride
            lhs_value  &= ~(mask << shift_value)
            lhs_value  |= (rhs & mask) << shift_value
            lhs_l(state, lhs_value)
        return eval

    def on_Cat(self, value):
        parts  = []
        offset = 0
        for opnd in value.parts:
            parts.append((offset, (1 << len(opnd)) - 1, self(opnd)))
            offset += len(opnd)
        def eval(state, rhs):
            for offset, mask, opnd in parts:
                opnd(state, (rhs >> offset) & mask)
        return eval

    def on_Repl(self, value):
        raise TypeError # :nocov:

    def on_ArrayProxy(self, value):
        elems = list(map(self, value.elems))
        index = self.rhs_compiler(value.index)
        def eval(state, rhs):
            index_value = index(state)
            if index_value >= len(elems):
                index_value = len(elems) - 1
            elems[index_value](state, rhs)
        return eval


class _StatementCompiler(StatementVisitor):
    def __init__(self, signal_slots):
        self.sensitivity   = SignalSet()
        self.rrhs_compiler = _RHSValueCompiler(signal_slots, self.sensitivity, mode="rhs")
        self.lrhs_compiler = _RHSValueCompiler(signal_slots, self.sensitivity, mode="lhs")
        self.lhs_compiler  = _LHSValueCompiler(signal_slots, self.lrhs_compiler)

    def on_Assign(self, stmt):
        shape = stmt.lhs.shape()
        lhs   = self.lhs_compiler(stmt.lhs)
        rhs   = self.rrhs_compiler(stmt.rhs)
        def run(state):
            lhs(state, normalize(rhs(state), shape))
        return run

    def on_Assert(self, stmt):
        raise NotImplementedError("Asserts not yet implemented for Simulator backend.") # :nocov:

    def on_Assume(self, stmt):
        pass # :nocov:

    def on_Cover(self, stmt):
        raise NotImplementedError("Covers not yet implemented for Simulator backend.") # :nocov:

    def on_Switch(self, stmt):
        test  = self.rrhs_compiler(stmt.test)
        cases = []
        for values, stmts in stmt.cases.items():
            if values == ():
                check = lambda test: True
            else:
                check = lambda test: False
                def make_check(mask, value, prev_check):
                    return lambda test: prev_check(test) or test & mask == value
                for value in values:
                    if "-" in value:
                        mask  = "".join("0" if b == "-" else "1" for b in value)
                        value = "".join("0" if b == "-" else  b  for b in value)
                    else:
                        mask  = "1" * len(value)
                    mask  = int(mask,  2)
                    value = int(value, 2)
                    check = make_check(mask, value, check)
            cases.append((check, self.on_statements(stmts)))
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
        self._fragment        = Fragment.get(fragment, platform=None)

        self._signal_slots    = SignalDict()  # Signal -> int/slot
        self._slot_signals    = list()        # int/slot -> Signal

        self._domains         = list()        # [ClockDomain]
        self._clk_edges       = dict()        # ClockDomain -> int/edge
        self._domain_triggers = list()        # int/slot -> ClockDomain

        self._signals         = SignalSet()   # {Signal}
        self._comb_signals    = bitarray()    # {Signal}
        self._sync_signals    = bitarray()    # {Signal}
        self._user_signals    = bitarray()    # {Signal}
        self._domain_signals  = dict()        # ClockDomain -> {Signal}

        self._started         = False
        self._timestamp       = 0.
        self._delta           = 0.
        self._epsilon         = 1e-10
        self._fastest_clock   = self._epsilon
        self._all_clocks      = set()         # {str/domain}
        self._state           = _State()

        self._processes       = set()         # {process}
        self._process_loc     = dict()        # process -> str/loc
        self._passive         = set()         # {process}
        self._suspended       = set()         # {process}
        self._wait_deadline   = dict()        # process -> float/timestamp
        self._wait_tick       = dict()        # process -> str/domain

        self._funclets        = list()        # int/slot -> set(lambda)

        self._vcd_file        = vcd_file
        self._vcd_writer      = None
        self._vcd_signals     = list()        # int/slot -> set(vcd_signal)
        self._vcd_names       = list()        # int/slot -> str/name
        self._gtkw_file       = gtkw_file
        self._traces          = traces

        self._run_called      = False

    @staticmethod
    def _check_process(process):
        if inspect.isgeneratorfunction(process):
            process = process()
        if not (inspect.isgenerator(process) or inspect.iscoroutine(process)):
            raise TypeError("Cannot add a process {!r} because it is not a generator or "
                            "a generator function"
                            .format(process))
        return process

    def _name_process(self, process):
        if process in self._process_loc:
            return self._process_loc[process]
        else:
            if inspect.isgenerator(process):
                frame = process.gi_frame
            if inspect.iscoroutine(process):
                frame = process.cr_frame
            return "{}:{}".format(inspect.getfile(frame), inspect.getlineno(frame))

    def add_process(self, process):
        process = self._check_process(process)
        self._processes.add(process)

    def add_sync_process(self, process, domain="sync"):
        process = self._check_process(process)
        def sync_process():
            try:
                cmd = None
                while True:
                    if cmd is None:
                        cmd = Tick(domain)
                    result = yield cmd
                    self._process_loc[sync_process] = self._name_process(process)
                    cmd = process.send(result)
            except StopIteration:
                pass
        sync_process = sync_process()
        self.add_process(sync_process)

    def add_clock(self, period, *, phase=None, domain="sync", if_exists=False):
        if self._fastest_clock == self._epsilon or period < self._fastest_clock:
            self._fastest_clock = period
        if domain in self._all_clocks:
            raise ValueError("Domain '{}' already has a clock driving it"
                             .format(domain))

        half_period = period / 2
        if phase is None:
            phase = half_period
        for domain_obj in self._domains:
            if not domain_obj.local and domain_obj.name == domain:
                clk = domain_obj.clk
                break
        else:
            if if_exists:
                return
            else:
                raise ValueError("Domain '{}' is not present in simulation"
                                 .format(domain))
        def clk_process():
            yield Passive()
            yield Delay(phase)
            while True:
                yield clk.eq(1)
                yield Delay(half_period)
                yield clk.eq(0)
                yield Delay(half_period)
        self.add_process(clk_process)
        self._all_clocks.add(domain)

    def __enter__(self):
        if self._vcd_file:
            self._vcd_writer = VCDWriter(self._vcd_file, timescale="100 ps",
                                         comment="Generated by nMigen")

        root_fragment = self._fragment.prepare()

        hierarchy = {}
        domains = set()
        def add_fragment(fragment, scope=()):
            hierarchy[fragment] = scope
            domains.update(fragment.domains.values())
            for index, (subfragment, name) in enumerate(fragment.subfragments):
                if name is None:
                    add_fragment(subfragment, (*scope, "U{}".format(index)))
                else:
                    add_fragment(subfragment, (*scope, name))
        add_fragment(root_fragment, scope=("top",))
        self._domains = list(domains)
        self._clk_edges = {domain: 1 if domain.clk_edge == "pos" else 0 for domain in domains}

        def add_signal(signal):
            if signal not in self._signals:
                self._signals.add(signal)

                signal_slot = self._state.add(normalize(signal.reset, signal.shape()))
                self._signal_slots[signal] = signal_slot
                self._slot_signals.append(signal)

                self._comb_signals.append(False)
                self._sync_signals.append(False)
                self._user_signals.append(False)
                for domain in self._domains:
                    if domain not in self._domain_signals:
                        self._domain_signals[domain] = bitarray()
                    self._domain_signals[domain].append(False)

                self._funclets.append(set())

                self._domain_triggers.append(None)
                if self._vcd_writer:
                    self._vcd_signals.append(set())
                    self._vcd_names.append(None)

            return self._signal_slots[signal]

        def add_domain_signal(signal, domain):
            signal_slot = add_signal(signal)
            self._domain_triggers[signal_slot] = domain

        for fragment, fragment_scope in hierarchy.items():
            for signal in fragment.iter_signals():
                add_signal(signal)

            for domain_name, domain in fragment.domains.items():
                add_domain_signal(domain.clk, domain)
                if domain.rst is not None:
                    add_domain_signal(domain.rst, domain)

        for fragment, fragment_scope in hierarchy.items():
            for signal in fragment.iter_signals():
                if not self._vcd_writer:
                    continue

                signal_slot = self._signal_slots[signal]

                for i, (subfragment, name) in enumerate(fragment.subfragments):
                    if signal in subfragment.ports:
                        var_name = "{}_{}".format(name or "U{}".format(i), signal.name)
                        break
                else:
                    var_name = signal.name

                if signal.decoder:
                    var_type = "string"
                    var_size = 1
                    var_init = signal.decoder(signal.reset).expandtabs().replace(" ", "_")
                else:
                    var_type = "wire"
                    var_size = signal.width
                    var_init = signal.reset

                suffix = None
                while True:
                    try:
                        if suffix is None:
                            var_name_suffix = var_name
                        else:
                            var_name_suffix = "{}${}".format(var_name, suffix)
                        self._vcd_signals[signal_slot].add(self._vcd_writer.register_var(
                            scope=".".join(fragment_scope), name=var_name_suffix,
                            var_type=var_type, size=var_size, init=var_init))
                        if self._vcd_names[signal_slot] is None:
                            self._vcd_names[signal_slot] = \
                                ".".join(fragment_scope + (var_name_suffix,))
                        break
                    except KeyError:
                        suffix = (suffix or 0) + 1

            for domain_name, signals in fragment.drivers.items():
                signals_bits = bitarray(len(self._signals))
                signals_bits.setall(False)
                for signal in signals:
                    signals_bits[self._signal_slots[signal]] = True

                if domain_name is None:
                    self._comb_signals |= signals_bits
                else:
                    self._sync_signals |= signals_bits
                    self._domain_signals[fragment.domains[domain_name]] |= signals_bits

            statements = []
            for domain_name, signals in fragment.drivers.items():
                reset_stmts = []
                hold_stmts  = []
                for signal in signals:
                    reset_stmts.append(signal.eq(signal.reset))
                    hold_stmts .append(signal.eq(signal))

                if domain_name is None:
                    statements += reset_stmts
                else:
                    if fragment.domains[domain_name].async_reset:
                        statements.append(Switch(fragment.domains[domain_name].rst,
                            {0: hold_stmts, 1: reset_stmts}))
                    else:
                        statements += hold_stmts
            statements += fragment.statements

            compiler = _StatementCompiler(self._signal_slots)
            funclet = compiler(statements)

            def add_funclet(signal, funclet):
                if signal in self._signal_slots:
                    self._funclets[self._signal_slots[signal]].add(funclet)

            for signal in compiler.sensitivity:
                add_funclet(signal, funclet)
            for domain in fragment.domains.values():
                add_funclet(domain.clk, funclet)
                if domain.rst is not None:
                    add_funclet(domain.rst, funclet)

        self._user_signals = bitarray(len(self._signals))
        self._user_signals.setall(True)
        self._user_signals &= ~self._comb_signals
        self._user_signals &= ~self._sync_signals

        return self

    def _update_dirty_signals(self):
        """Perform the statement part of IR processes (aka RTLIL case)."""
        # First, for all dirty signals, use sensitivity lists to determine the set of fragments
        # that need their statements to be reevaluated because the signals changed at the previous
        # delta cycle.
        funclets = set()
        for signal_slot in self._state.flush_curr_dirty():
            funclets.update(self._funclets[signal_slot])

        # Second, compute the values of all signals at the start of the next delta cycle, by
        # running precompiled statements.
        for funclet in funclets:
            funclet(self._state)

    def _commit_signal(self, signal_slot, domains):
        """Perform the driver part of IR processes (aka RTLIL sync), for individual signals."""
        # Take the computed value (at the start of this delta cycle) of a signal (that could have
        # come from an IR process that ran earlier, or modified by a simulator process) and update
        # the value for this delta cycle.
        old, new = self._state.commit(signal_slot)
        if old == new:
            return

        # If the signal is a clock that triggers synchronous logic, record that fact.
        if (self._domain_triggers[signal_slot] is not None and
                self._clk_edges[self._domain_triggers[signal_slot]] == new):
            domains.add(self._domain_triggers[signal_slot])

        if self._vcd_writer:
            # Finally, dump the new value to the VCD file.
            for vcd_signal in self._vcd_signals[signal_slot]:
                signal = self._slot_signals[signal_slot]
                if signal.decoder:
                    var_value = signal.decoder(new).expandtabs().replace(" ", "_")
                else:
                    var_value = new
                vcd_timestamp = (self._timestamp + self._delta) / self._epsilon
                self._vcd_writer.change(vcd_signal, vcd_timestamp, var_value)

    def _commit_comb_signals(self, domains):
        """Perform the comb part of IR processes (aka RTLIL always)."""
        # Take the computed value (at the start of this delta cycle) of every comb signal and
        # update the value for this delta cycle.
        for signal_slot in self._state.iter_next_dirty():
            if self._comb_signals[signal_slot]:
                self._commit_signal(signal_slot, domains)

    def _commit_sync_signals(self, domains):
        """Perform the sync part of IR processes (aka RTLIL posedge)."""
        # At entry, `domains` contains a set of every simultaneously triggered sync update.
        while domains:
            # Advance the timeline a bit (purely for observational purposes) and commit all of them
            # at the same timestamp.
            self._delta += self._epsilon
            curr_domains, domains = domains, set()

            while curr_domains:
                domain = curr_domains.pop()

                # Wake up any simulator processes that wait for a domain tick.
                for process, wait_domain_name in list(self._wait_tick.items()):
                    if domain.name == wait_domain_name:
                        del self._wait_tick[process]
                        self._suspended.remove(process)

                        # Immediately run the process. It is important that this happens here,
                        # and not on the next step, when all the processes will run anyway,
                        # because Tick() simulates an edge triggered process. Like DFFs that latch
                        # a value from the previous clock cycle, simulator processes observe signal
                        # values from the previous clock cycle on a tick, too.
                        self._run_process(process)

                # Take the computed value (at the start of this delta cycle) of every sync signal
                # in this domain and update the value for this delta cycle. This can trigger more
                # synchronous logic, so record that.
                for signal_slot in self._state.iter_next_dirty():
                    if self._domain_signals[domain][signal_slot]:
                        self._commit_signal(signal_slot, domains)

            # Unless handling synchronous logic above has triggered more synchronous logic (which
            # can happen e.g. if a domain is clocked off a clock divisor in fabric), we're done.
            # Otherwise, do one more round of updates.

    def _run_process(self, process):
        try:
            cmd = process.send(None)
            while True:
                if type(cmd) is Delay:
                    if cmd.interval is None:
                        interval = self._epsilon
                    else:
                        interval = cmd.interval
                    self._wait_deadline[process] = self._timestamp + interval
                    self._suspended.add(process)
                    break

                elif type(cmd) is Tick:
                    self._wait_tick[process] = cmd.domain
                    self._suspended.add(process)
                    break

                elif type(cmd) is Passive:
                    self._passive.add(process)

                elif type(cmd) is Assign:
                    lhs_signals = cmd.lhs._lhs_signals()
                    for signal in lhs_signals:
                        if not signal in self._signals:
                            raise ValueError("Process '{}' sent a request to set signal {!r}, "
                                             "which is not a part of simulation"
                                             .format(self._name_process(process), signal))
                        signal_slot = self._signal_slots[signal]
                        if self._comb_signals[signal_slot]:
                            raise ValueError("Process '{}' sent a request to set signal {!r}, "
                                             "which is a part of combinatorial assignment in "
                                             "simulation"
                                             .format(self._name_process(process), signal))

                    if type(cmd.lhs) is Signal and type(cmd.rhs) is Const:
                        # Fast path.
                        self._state.set(self._signal_slots[cmd.lhs],
                                        normalize(cmd.rhs.value, cmd.lhs.shape()))
                    else:
                        compiler = _StatementCompiler(self._signal_slots)
                        funclet = compiler(cmd)
                        funclet(self._state)

                    domains = set()
                    for signal in lhs_signals:
                        self._commit_signal(self._signal_slots[signal], domains)
                    self._commit_sync_signals(domains)

                elif type(cmd) is Signal:
                    # Fast path.
                    cmd = process.send(self._state.curr[self._signal_slots[cmd]])
                    continue

                elif isinstance(cmd, Value):
                    compiler = _RHSValueCompiler(self._signal_slots)
                    funclet = compiler(cmd)
                    cmd = process.send(funclet(self._state))
                    continue

                else:
                    raise TypeError("Received unsupported command {!r} from process '{}'"
                                    .format(cmd, self._name_process(process)))

                cmd = process.send(None)

        except StopIteration:
            self._processes.remove(process)
            self._passive.discard(process)

        except Exception as e:
            process.throw(e)

    def step(self, run_passive=False):
        # Are there any delta cycles we should run?
        if self._state.curr_dirty.any():
            # We might run some delta cycles, and we have simulator processes waiting on
            # a deadline. Take care to not exceed the closest deadline.
            if self._wait_deadline and \
                    (self._timestamp + self._delta) >= min(self._wait_deadline.values()):
                # Oops, we blew the deadline. We *could* run the processes now, but this is
                # virtually certainly a logic loop and a design bug, so bail out instead.d
                raise DeadlineError("Delta cycles exceeded process deadline; combinatorial loop?")

            domains = set()
            while self._state.curr_dirty.any():
                self._update_dirty_signals()
                self._commit_comb_signals(domains)
            self._commit_sync_signals(domains)
            return True

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
                self._delta = 0.
                self._run_process(process)
                return True

        # No processes, or all processes are passive. Nothing to do!
        return False

    def run(self):
        self._run_called = True

        while self.step():
            pass

    def run_until(self, deadline, run_passive=False):
        self._run_called = True

        while self._timestamp < deadline:
            if not self.step(run_passive):
                return False

        return True

    def __exit__(self, *args):
        if not self._run_called:
            warnings.warn("Simulation created, but not run", UserWarning)

        if self._vcd_writer:
            vcd_timestamp = (self._timestamp + self._delta) / self._epsilon
            self._vcd_writer.close(vcd_timestamp)

        if self._vcd_file and self._gtkw_file:
            gtkw_save = GTKWSave(self._gtkw_file)
            if hasattr(self._vcd_file, "name"):
                gtkw_save.dumpfile(self._vcd_file.name)
            if hasattr(self._vcd_file, "tell"):
                gtkw_save.dumpfile_size(self._vcd_file.tell())

            gtkw_save.treeopen("top")
            gtkw_save.zoom_markers(math.log(self._epsilon / self._fastest_clock) - 14)

            def add_trace(signal, **kwargs):
                signal_slot = self._signal_slots[signal]
                if self._vcd_names[signal_slot] is not None:
                    if len(signal) > 1 and not signal.decoder:
                        suffix = "[{}:0]".format(len(signal) - 1)
                    else:
                        suffix = ""
                    gtkw_save.trace(self._vcd_names[signal_slot] + suffix, **kwargs)

            for domain in self._domains:
                with gtkw_save.group("d.{}".format(domain.name)):
                    if domain.rst is not None:
                        add_trace(domain.rst)
                    add_trace(domain.clk)

            for signal in self._traces:
                add_trace(signal)

        if self._vcd_file:
            self._vcd_file.close()
        if self._gtkw_file:
            self._gtkw_file.close()
