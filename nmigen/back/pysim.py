from vcd import VCDWriter

from ..tools import flatten
from ..fhdl.ast import *
from ..fhdl.xfrm import ValueTransformer, StatementTransformer


__all__ = ["Simulator", "Delay", "Passive"]


class _State:
    __slots__ = ("curr", "curr_dirty", "next", "next_dirty")

    def __init__(self):
        self.curr = ValueDict()
        self.next = ValueDict()
        self.curr_dirty = ValueSet()
        self.next_dirty = ValueSet()

    def get(self, signal):
        return self.curr[signal]

    def set_curr(self, signal, value):
        assert isinstance(value, Const)
        if self.curr[signal].value != value.value:
            self.curr_dirty.add(signal)
            self.curr[signal] = value

    def set_next(self, signal, value):
        assert isinstance(value, Const)
        if self.next[signal].value != value.value:
            self.next_dirty.add(signal)
            self.next[signal] = value

    def commit(self, signal):
        old_value = self.curr[signal]
        if self.curr[signal].value != self.next[signal].value:
            self.next_dirty.remove(signal)
            self.curr_dirty.add(signal)
            self.curr[signal] = self.next[signal]
        new_value = self.curr[signal]
        return old_value, new_value

    def iter_dirty(self):
        dirty, self.dirty = self.dirty, ValueSet()
        for signal in dirty:
            yield signal, self.curr[signal], self.next[signal]


class _RHSValueCompiler(ValueTransformer):
    def __init__(self, sensitivity):
        self.sensitivity = sensitivity

    def on_Const(self, value):
        return lambda state: value

    def on_Signal(self, value):
        self.sensitivity.add(value)
        return lambda state: state.get(value)

    def on_ClockSignal(self, value):
        raise NotImplementedError

    def on_ResetSignal(self, value):
        raise NotImplementedError

    def on_Operator(self, value):
        shape = value.shape()
        if len(value.operands) == 1:
            arg, = map(self, value.operands)
            if value.op == "~":
                return lambda state: Const(~arg(state).value, shape)
            elif value.op == "-":
                return lambda state: Const(-arg(state).value, shape)
        elif len(value.operands) == 2:
            lhs, rhs = map(self, value.operands)
            if value.op == "+":
                return lambda state: Const(lhs(state).value +  rhs(state).value, shape)
            if value.op == "-":
                return lambda state: Const(lhs(state).value -  rhs(state).value, shape)
            if value.op == "&":
                return lambda state: Const(lhs(state).value &  rhs(state).value, shape)
            if value.op == "|":
                return lambda state: Const(lhs(state).value |  rhs(state).value, shape)
            if value.op == "^":
                return lambda state: Const(lhs(state).value ^  rhs(state).value, shape)
            elif value.op == "==":
                lhs, rhs = map(self, value.operands)
                return lambda state: Const(lhs(state).value == rhs(state).value, shape)
        elif len(value.operands) == 3:
            if value.op == "m":
                sel, val1, val0 = map(self, value.operands)
                return lambda state: val1(state) if sel(state).value else val0(state)
        raise NotImplementedError("Operator '{}' not implemented".format(value.op))

    def on_Slice(self, value):
        shape = value.shape()
        arg   = self(value.value)
        shift = value.start
        mask  = (1 << (value.end - value.start)) - 1
        return lambda state: Const((arg(state).value >> shift) & mask, shape)

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
                result |= (opnd(state).value & mask) << offset
            return Const(result, shape)
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
                result  |= opnd(state).value
            return Const(result, shape)
        return eval


class _StatementCompiler(StatementTransformer):
    def __init__(self):
        self.sensitivity  = ValueSet()
        self.rhs_compiler = _RHSValueCompiler(self.sensitivity)

    def lhs_compiler(self, value):
        # TODO
        return lambda state, arg: state.set_next(value, arg)

    def on_Assign(self, stmt):
        assert isinstance(stmt.lhs, Signal)
        shape = stmt.lhs.shape()
        lhs   = self.lhs_compiler(stmt.lhs)
        rhs   = self.rhs_compiler(stmt.rhs)
        def run(state):
            lhs(state, Const(rhs(state).value, shape))
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
            cases.append((lambda test: test & mask == value,
                          self.on_statements(stmts)))
        def run(state):
            test_value = test(state).value
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
    def __init__(self, fragment=None, vcd_file=None):
        self._fragments       = {}            # fragment -> hierarchy
        self._domains         = {}            # str -> ClockDomain
        self._domain_triggers = ValueDict()   # Signal -> str
        self._domain_signals  = {}            # str -> {Signal}
        self._signals         = ValueSet()    # {Signal}
        self._comb_signals    = ValueSet()    # {Signal}
        self._sync_signals    = ValueSet()    # {Signal}
        self._user_signals    = ValueSet()    # {Signal}

        self._started         = False
        self._timestamp       = 0.
        self._state           = _State()

        self._processes       = set()         # {process}
        self._passive         = set()         # {process}
        self._suspended       = {}            # process -> until

        self._handlers        = ValueDict()   # Signal -> set(lambda)

        self._vcd_file        = vcd_file
        self._vcd_writer      = None
        self._vcd_signals     = ValueDict()   # signal -> set(vcd_signal)

        if fragment is not None:
            fragment = fragment.prepare()
            self._add_fragment(fragment)
            self._domains = fragment.domains
            for domain, cd in self._domains.items():
                self._domain_triggers[cd.clk] = domain
                if cd.rst is not None:
                    self._domain_triggers[cd.rst] = domain
                self._domain_signals[domain] = ValueSet()

    def _add_fragment(self, fragment, hierarchy=("top",)):
        self._fragments[fragment] = hierarchy
        for subfragment, name in fragment.subfragments:
            self._add_fragment(subfragment, (*hierarchy, name))

    def add_process(self, fn):
        self._processes.add(fn)

    def add_clock(self, domain, period):
        clk = self._domains[domain].clk
        half_period = period / 2
        def clk_process():
            yield Passive()
            while True:
                yield clk.eq(1)
                yield Delay(half_period)
                yield clk.eq(0)
                yield Delay(half_period)
        self.add_process(clk_process())

    def _signal_name_in_fragment(self, fragment, signal):
        for subfragment, name in fragment.subfragments:
            if signal in subfragment.ports:
                return "{}_{}".format(name, signal.name)
        return signal.name

    def _add_handler(self, signal, handler):
        if signal not in self._handlers:
            self._handlers[signal] = set()
        self._handlers[signal].add(handler)

    def __enter__(self):
        if self._vcd_file:
            self._vcd_writer = VCDWriter(self._vcd_file, timescale="100 ps",
                                         comment="Generated by nMigen")

        for fragment in self._fragments:
            for signal in fragment.iter_signals():
                self._signals.add(signal)

                self._state.curr[signal] = self._state.next[signal] = \
                    Const(signal.reset, signal.shape())
                self._state.curr_dirty.add(signal)

                if signal not in self._vcd_signals:
                    self._vcd_signals[signal] = set()
                name   = self._signal_name_in_fragment(fragment, signal)
                suffix = None
                while True:
                    try:
                        if suffix is None:
                            name_suffix = name
                        else:
                            name_suffix = "{}${}".format(name, suffix)
                        self._vcd_signals[signal].add(self._vcd_writer.register_var(
                            scope=".".join(self._fragments[fragment]), name=name_suffix,
                            var_type="wire", size=signal.nbits, init=signal.reset))
                        break
                    except KeyError:
                        suffix = (suffix or 0) + 1

            for domain, signals in fragment.drivers.items():
                if domain is None:
                    self._comb_signals.update(signals)
                else:
                    self._sync_signals.update(signals)
                    self._domain_signals[domain].update(signals)

            compiler = _StatementCompiler()
            handler  = compiler(fragment.statements)
            for signal in compiler.sensitivity:
                self._add_handler(signal, handler)
            for domain, cd in fragment.domains.items():
                self._add_handler(cd.clk, handler)
                if cd.rst is not None:
                    self._add_handler(cd.rst, handler)

        self._user_signals = self._signals - self._comb_signals - self._sync_signals

    def _commit_signal(self, signal):
        old, new = self._state.commit(signal)
        if old.value == 0 and new.value == 1 and signal in self._domain_triggers:
            domain = self._domain_triggers[signal]
            for sync_signal in self._state.next_dirty:
                if sync_signal in self._domain_signals[domain]:
                    self._commit_signal(sync_signal)

        if self._vcd_writer:
            for vcd_signal in self._vcd_signals[signal]:
                self._vcd_writer.change(vcd_signal, self._timestamp * 1e10, new.value)

    def _handle_event(self):
        handlers = set()
        while self._state.curr_dirty:
            signal = self._state.curr_dirty.pop()
            if signal in self._handlers:
                handlers.update(self._handlers[signal])

        for handler in handlers:
            handler(self._state)

        for signal in self._state.next_dirty:
            if signal in self._comb_signals or signal in self._user_signals:
                self._commit_signal(signal)

    def _force_signal(self, signal, value):
        assert signal in self._comb_signals or signal in self._user_signals
        self._state.set_next(signal, value)
        self._commit_signal(signal)

    def _run_process(self, proc):
        try:
            stmt = proc.send(None)
        except StopIteration:
            self._processes.remove(proc)
            self._passive.discard(proc)
            return

        if isinstance(stmt, Delay):
            self._suspended[proc] = self._timestamp + stmt.interval
        elif isinstance(stmt, Passive):
            self._passive.add(proc)
        elif isinstance(stmt, Assign):
            assert isinstance(stmt.lhs, Signal)
            assert isinstance(stmt.rhs, Const)
            self._force_signal(stmt.lhs, Const(stmt.rhs.value, stmt.lhs.shape()))
        else:
            raise TypeError("Received unsupported statement '{!r}' from process {}"
                            .format(stmt, proc))

    def step(self, run_passive=False):
        # Are there any delta cycles we should run?
        while self._state.curr_dirty:
            self._timestamp += 1e-10
            self._handle_event()

        # Are there any processes that haven't had a chance to run yet?
        if len(self._processes) > len(self._suspended):
            # Schedule an arbitrary one.
            proc = (self._processes - set(self._suspended)).pop()
            self._run_process(proc)
            return True

        # All processes are suspended. Are any of them active?
        if len(self._processes) > len(self._passive) or run_passive:
            # Schedule the one with the lowest deadline.
            proc, deadline = min(self._suspended.items(), key=lambda x: x[1])
            del self._suspended[proc]
            self._timestamp = deadline
            self._run_process(proc)
            return True

        # No processes, or all processes are passive. Nothing to do!
        return False

    def run_until(self, deadline, run_passive=False):
        while self._timestamp < deadline:
            if not self.step(run_passive):
                return False
        return True

    def __exit__(self, *args):
        if self._vcd_writer:
            self._vcd_writer.close(self._timestamp * 1e10)
