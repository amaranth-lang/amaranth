import os
import tempfile
from contextlib import contextmanager
import sys

from ..hdl import *
from ..hdl._ast import SignalSet, _StatementList, Property
from ..hdl._xfrm import ValueVisitor, StatementVisitor, LHSMaskCollector
from ..hdl._mem import MemoryInstance
from ._base import BaseProcess
from ._pyeval import value_to_string


__all__ = ["PyRTLProcess"]


_USE_PATTERN_MATCHING = (sys.version_info >= (3, 10))


class PyRTLProcess(BaseProcess):
    __slots__ = ("is_comb", "runnable", "critical", "run")

    def __init__(self, *, is_comb):
        self.is_comb  = is_comb

        self.reset()

    def reset(self):
        self.runnable = self.is_comb
        self.critical = False


class _PythonEmitter:
    def __init__(self):
        self._buffer = []
        self._suffix = 0
        self._level  = 0

    def append(self, code):
        self._buffer.append("    " * self._level)
        self._buffer.append(code)
        self._buffer.append("\n")

    @contextmanager
    def indent(self):
        self._level += 1
        yield
        self._level -= 1

    def flush(self, indent=""):
        code = "".join(self._buffer)
        self._buffer.clear()
        return code

    def gen_var(self, prefix):
        name = f"{prefix}_{self._suffix}"
        self._suffix += 1
        return name

    def def_var(self, prefix, value):
        name = self.gen_var(prefix)
        self.append(f"{name} = {value}")
        return name


class _Compiler:
    def __init__(self, state, emitter):
        self.state = state
        self.emitter = emitter

    def _emit_switch(self, test, cases, case_handler):
        if not cases:
            return
        use_match = _USE_PATTERN_MATCHING
        for patterns, *_ in cases:
            if patterns is None:
                continue
            for pattern in patterns:
                if "-" in pattern:
                    use_match = False
        if use_match:
            self.emitter.append(f"match {test}:")
            with self.emitter.indent():
                for case in cases:
                    patterns = case[0]
                    if patterns is None:
                        self.emitter.append(f"case _:")
                    elif not patterns:
                        self.emitter.append(f"case _ if False:")
                    else:
                        self.emitter.append(f"case {' | '.join(f'0b0{pattern}' for pattern in patterns)}:")
                    with self.emitter.indent():
                        case_handler(*case)
        else:
            for index, case in enumerate(cases):
                patterns = case[0]
                gen_checks = []
                if patterns is None:
                    gen_checks.append(f"True")
                elif not patterns:
                    gen_checks.append(f"False")
                else:
                    for pattern in patterns:
                        if "-" in pattern:
                            mask  = int("".join("0" if b == "-" else "1" for b in pattern), 2)
                            value = int("".join("0" if b == "-" else  b  for b in pattern), 2)
                            gen_checks.append(f"{value} == ({mask} & {test})")
                        else:
                            value = int(pattern or "0", 2)
                            gen_checks.append(f"{value} == {test}")
                if index == 0:
                    self.emitter.append(f"if {' or '.join(gen_checks)}:")
                else:
                    self.emitter.append(f"elif {' or '.join(gen_checks)}:")
                with self.emitter.indent():
                    case_handler(*case)


class _ValueCompiler(ValueVisitor, _Compiler):
    helpers = {
        "sign": lambda value, sign: value | sign if value & sign else value,
        "zdiv": lambda lhs, rhs: 0 if rhs == 0 else lhs // rhs,
        "zmod": lambda lhs, rhs: 0 if rhs == 0 else lhs % rhs,
    }

    def on_value(self, value):
        # Very large values are unlikely to compile or simulate in reasonable time.
        if len(value) > 2 ** 16:
            if value.src_loc:
                src = "{}:{}".format(*value.src_loc)
            else:
                src = "unknown location"
            raise OverflowError("Value defined at {} is {} bits wide, which is unlikely to "
                                "simulate in reasonable time"
                                .format(src, len(value)))

        code = super().on_value(value)
        if isinstance(code, str) and len(code) > 1000:
            # Avoid parser stack overflow on older Pythons.
            return self.emitter.def_var("expr_split", code)
        return code

    def on_ClockSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_ResetSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_AnyValue(self, value):
        raise NotImplementedError # :nocov:

    def on_Initial(self, value):
        raise NotImplementedError # :nocov:


class _RHSValueCompiler(_ValueCompiler):
    def __init__(self, state, emitter, *, mode, inputs=None, rrhs=None):
        super().__init__(state, emitter)
        assert mode in ("curr", "next")
        self.mode = mode
        # If not None, `inputs` gets populated with RHS signals.
        self.inputs = inputs
        # When this compiler is used to grab the "next" value from within _LHSValueCompiler,
        # we still need to use "curr" mode for reading part offsets etc. Allow setting a separate
        # _RhsValueCompiler for these contexts.
        self.rrhs = rrhs or self

    def sign(self, value):
        value_mask = (1 << len(value)) - 1
        masked = f"({value_mask:#x} & {self(value)})"

        if value.shape().signed:
            return f"sign({masked}, {-1 << (len(value) - 1):#x})"
        else: # unsigned
            return masked

    def on_Const(self, value):
        return f"{value.value}"

    def on_Signal(self, value):
        if self.inputs is not None:
            self.inputs.add(value)

        if self.mode == "curr":
            return f"slots[{self.state.get_signal(value)}].{self.mode}"
        else:
            return f"next_{self.state.get_signal(value)}"

    def on_Operator(self, value):
        def mask(value):
            value_mask = (1 << len(value)) - 1
            return f"({value_mask:#x} & {self(value)})"

        def sign(value):
            if value.shape().signed:
                return f"sign({mask(value)}, {-1 << (len(value) - 1):#x})"
            else: # unsigned
                return mask(value)

        if len(value.operands) == 1:
            arg, = value.operands
            if value.operator == "~":
                return f"(~{mask(arg)})"
            if value.operator == "-":
                return f"(-{sign(arg)})"
            if value.operator == "b":
                return f"bool({mask(arg)})"
            if value.operator == "r|":
                return f"(0 != {mask(arg)})"
            if value.operator == "r&":
                return f"({(1 << len(arg)) - 1} == {mask(arg)})"
            if value.operator == "r^":
                # Believe it or not, this is the fastest way to compute a sideways XOR in Python.
                return f"(format({mask(arg)}, 'b').count('1') % 2)"
            if value.operator in ("u", "s"):
                # These operators don't change the bit pattern, only its interpretation.
                return self(arg)
        elif len(value.operands) == 2:
            lhs, rhs = value.operands
            if value.operator == "+":
                return f"({sign(lhs)} + {sign(rhs)})"
            if value.operator == "-":
                return f"({sign(lhs)} - {sign(rhs)})"
            if value.operator == "*":
                return f"({sign(lhs)} * {sign(rhs)})"
            if value.operator == "//":
                return f"zdiv({sign(lhs)}, {sign(rhs)})"
            if value.operator == "%":
                return f"zmod({sign(lhs)}, {sign(rhs)})"
            if value.operator == "&":
                return f"({sign(lhs)} & {sign(rhs)})"
            if value.operator == "|":
                return f"({sign(lhs)} | {sign(rhs)})"
            if value.operator == "^":
                return f"({sign(lhs)} ^ {sign(rhs)})"
            if value.operator == "<<":
                return f"({sign(lhs)} << {sign(rhs)})"
            if value.operator == ">>":
                return f"({sign(lhs)} >> {sign(rhs)})"
            if value.operator == "==":
                return f"({sign(lhs)} == {sign(rhs)})"
            if value.operator == "!=":
                return f"({sign(lhs)} != {sign(rhs)})"
            if value.operator == "<":
                return f"({sign(lhs)} < {sign(rhs)})"
            if value.operator == "<=":
                return f"({sign(lhs)} <= {sign(rhs)})"
            if value.operator == ">":
                return f"({sign(lhs)} > {sign(rhs)})"
            if value.operator == ">=":
                return f"({sign(lhs)} >= {sign(rhs)})"
        raise NotImplementedError(f"Operator '{value.operator}' not implemented") # :nocov:

    def on_Slice(self, value):
        return f"({(1 << len(value)) - 1:#x} & ({self(value.value)} >> {value.start}))"

    def on_Part(self, value):
        offset_mask = (1 << len(value.offset)) - 1
        offset = f"({value.stride} * ({offset_mask:#x} & {self.rrhs(value.offset)}))"
        return f"({(1 << value.width) - 1} & " \
               f"{self(value.value)} >> {offset})"

    def on_Concat(self, value):
        gen_parts = []
        offset = 0
        for part in value.parts:
            part_mask = (1 << len(part)) - 1
            gen_parts.append(f"(({part_mask:#x} & {self(part)}) << {offset})")
            offset += len(part)
        if gen_parts:
            return f"({' | '.join(gen_parts)})"
        return f"0"

    def on_SwitchValue(self, value):
        gen_test = self.emitter.def_var("test", f"{(1 << len(value.test)) - 1:#x} & {self.rrhs(value.test)}")
        gen_value = self.emitter.def_var("rhs_switch", "0")
        def case_handler(patterns, elem):
            self.emitter.append(f"{gen_value} = {self.sign(elem)}")
        self._emit_switch(gen_test, value.cases, case_handler)
        return gen_value

    @classmethod
    def compile(cls, state, value, *, mode):
        emitter = _PythonEmitter()
        compiler = cls(state, emitter, mode=mode)
        emitter.append(f"result = {compiler(value)}")
        return emitter.flush()


class _LHSValueCompiler(_ValueCompiler):
    def __init__(self, state, emitter, *, rhs, outputs=None):
        super().__init__(state, emitter)
        # `rrhs` is used to translate rvalues that are syntactically a part of an lvalue, e.g.
        # the offset of a Part.
        self.rrhs = rhs
        # `lrhs` is used to translate the read part of a read-modify-write cycle during partial
        # update of an lvalue.
        self.lrhs = _RHSValueCompiler(state, emitter, mode="next", inputs=None, rrhs=rhs)
        # If not None, `outputs` gets populated with signals on LHS.
        self.outputs = outputs

    def on_Const(self, value):
        raise TypeError # :nocov:

    def on_Signal(self, value):
        if self.outputs is not None:
            self.outputs.add(value)

        def gen(arg):
            value_mask = (1 << len(value)) - 1
            if value.shape().signed:
                value_sign = f"sign({value_mask:#x} & {arg}, {-1 << (len(value) - 1)})"
            else: # unsigned
                value_sign = f"{value_mask:#x} & {arg}"
            self.emitter.append(f"next_{self.state.get_signal(value)} = {value_sign}")
        return gen

    def on_Operator(self, value):
        if value.operator in ("u", "s"):
            return self(value.operands[0])
        raise TypeError # :nocov:

    def on_Slice(self, value):
        def gen(arg):
            width_mask = (1 << (value.stop - value.start)) - 1
            self(value.value)(f"({self.lrhs(value.value)} & " \
                f"{~(width_mask << value.start):#x} | " \
                f"(({width_mask:#x} & {arg}) << {value.start}))")
        return gen

    def on_Part(self, value):
        def gen(arg):
            width_mask = (1 << value.width) - 1
            offset_mask = (1 << len(value.offset)) - 1
            offset = f"({value.stride} * ({offset_mask:#x} & {self.rrhs(value.offset)}))"
            self(value.value)(f"({self.lrhs(value.value)} & " \
                f"~({width_mask:#x} << {offset}) | " \
                f"(({width_mask:#x} & {arg}) << {offset}))")
        return gen

    def on_Concat(self, value):
        def gen(arg):
            gen_arg = self.emitter.def_var("cat", arg)
            offset = 0
            for part in value.parts:
                part_mask = (1 << len(part)) - 1
                self(part)(f"({part_mask:#x} & ({gen_arg} >> {offset}))")
                offset += len(part)
        return gen

    def on_SwitchValue(self, value):
        def gen(arg):
            gen_test = self.emitter.def_var("test", f"{(1 << len(value.test)) - 1:#x} & {self.rrhs(value.test)}")
            def case_handler(patterns, elem):
                self(elem)(arg)
            self._emit_switch(gen_test, value.cases, case_handler)
        return gen


def pin_blame(src_loc, exc):
    if src_loc is None:
        raise exc
    filename, line = src_loc
    code = compile("\n" * (line - 1) + "raise exc", filename, "exec")
    exec(code, {"exc": exc})


class _StatementCompiler(StatementVisitor, _Compiler):
    helpers = {
        "value_to_string": value_to_string,
        "pin_blame": pin_blame,
    }

    def __init__(self, state, emitter, *, inputs=None, outputs=None):
        super().__init__(state, emitter)
        self.rhs = _RHSValueCompiler(state, emitter, mode="curr", inputs=inputs)
        self.lhs = _LHSValueCompiler(state, emitter, rhs=self.rhs, outputs=outputs)

    def on_statements(self, stmts):
        for stmt in stmts:
            self(stmt)
        if not stmts:
            self.emitter.append("pass")

    def on_Assign(self, stmt):
        return self.lhs(stmt.lhs)(self.rhs.sign(stmt.rhs))

    def on_Switch(self, stmt):
        gen_test_value = self.rhs(stmt.test) # check for oversized value before generating mask
        gen_test = self.emitter.def_var("test", f"{(1 << len(stmt.test)) - 1:#x} & {gen_test_value}")
        def case_handler(pattern, stmt, src_loc):
            self(stmt)
        self._emit_switch(gen_test, stmt.cases, case_handler)

    def emit_format(self, format):
        format_string = []
        args = []
        for chunk in format._chunks:
            if isinstance(chunk, str):
                format_string.append(chunk.replace("{", "{{").replace("}", "}}"))
            else:
                value, format_desc = chunk
                value = self.rhs.sign(value)
                if format_desc.endswith("s"):
                    format_desc = format_desc[:-1]
                    value = f"value_to_string({value})"
                format_string.append(f"{{:{format_desc}}}")
                args.append(value)
        format_string = "".join(format_string)
        args = ", ".join(args)
        return f"{format_string!r}.format({args})"

    def on_Print(self, stmt):
        self.emitter.append(f"print({self.emit_format(stmt.message)}, end='')")

    def on_Property(self, stmt):
        if stmt.kind == Property.Kind.Cover:
            if stmt.message is not None:
                self.emitter.append(f"if {self.rhs.sign(stmt.test)}:")
                with self.emitter.indent():
                    filename, line = stmt.src_loc
                    self.emitter.append(f"print(\"Coverage hit at \" {filename!r} \":{line}:\", {self.emit_format(stmt.message)})")
        else:
            self.emitter.append(f"if not {self.rhs.sign(stmt.test)}:")
            with self.emitter.indent():
                if stmt.kind == Property.Kind.Assert:
                    kind = "Assertion"
                elif stmt.kind == Property.Kind.Assume:
                    kind = "Assumption"
                else:
                    assert False # :nocov:
                if stmt.message is not None:
                    self.emitter.append(f"pin_blame({stmt.src_loc!r}, AssertionError(\"{kind} violated: \" + {self.emit_format(stmt.message)}))")
                else:
                    self.emitter.append(f"pin_blame({stmt.src_loc!r}, AssertionError(\"{kind} violated\"))")

    @classmethod
    def compile(cls, state, stmt):
        output_indexes = [state.get_signal(signal) for signal in stmt._lhs_signals()]
        emitter = _PythonEmitter()
        for signal_index in output_indexes:
            emitter.append(f"next_{signal_index} = slots[{signal_index}].next")
        compiler = cls(state, emitter)
        compiler(stmt)
        for signal_index in output_indexes:
            emitter.append(f"slots[{signal_index}].update(next_{signal_index})")
        return emitter.flush()


def comb_waker(process):
    def waker(curr, next):
        process.runnable = True
        return True
    return waker


def edge_waker(process, polarity):
    def waker(curr, next):
        if next == polarity:
            process.runnable = True
        return True
    return waker


def memory_waker(process):
    def waker():
        process.runnable = True
        return True
    return waker


class _FragmentCompiler:
    def __init__(self, state):
        self.state = state

    def __call__(self, fragment):
        processes = set()

        domains = set(fragment.statements)

        if isinstance(fragment, MemoryInstance):
            for port in fragment._read_ports:
                domains.add(port._domain)
            for port in fragment._write_ports:
                domains.add(port._domain)

        for domain_name in domains:
            domain_stmts = fragment.statements.get(domain_name, _StatementList())
            domain_process = PyRTLProcess(is_comb=domain_name == "comb")
            lhs_masks = LHSMaskCollector()
            lhs_masks.visit_stmt(domain_stmts)

            if isinstance(fragment, MemoryInstance):
                for port in fragment._read_ports:
                    if port._domain == domain_name:
                        lhs_masks.visit_value(port._data, ~0)

            emitter = _PythonEmitter()
            emitter.append(f"def run():")
            emitter._level += 1

            if domain_name == "comb":
                for (signal, _) in lhs_masks.masks():
                    signal_index = self.state.get_signal(signal)
                    self.state.slots[signal_index].is_comb = True
                    emitter.append(f"next_{signal_index} = {signal.init}")

                inputs = SignalSet()
                _StatementCompiler(self.state, emitter, inputs=inputs)(domain_stmts)

                if isinstance(fragment, MemoryInstance):
                    self.state.add_memory_waker(fragment._data, memory_waker(domain_process))
                    memory_index = self.state.get_memory(fragment._data)
                    rhs = _RHSValueCompiler(self.state, emitter, mode="curr", inputs=inputs)
                    lhs = _LHSValueCompiler(self.state, emitter, rhs=rhs)

                    for port in fragment._read_ports:
                        if port._domain != "comb":
                            continue

                        addr = rhs(port._addr)
                        addr = f"({(1 << len(port._addr)) - 1:#x} & {addr})"
                        data = emitter.def_var("read_data", f"slots[{memory_index}].read({addr})")
                        lhs(port._data)(data)

                waker = comb_waker(domain_process)
                for input in inputs:
                    self.state.add_signal_waker(input, waker)

            else:
                domain = fragment.domains[domain_name]
                clk_polarity = 1 if domain.clk_edge == "pos" else 0
                self.state.add_signal_waker(domain.clk, edge_waker(domain_process, clk_polarity))
                if domain.async_reset and domain.rst is not None:
                    self.state.add_signal_waker(domain.rst, edge_waker(domain_process, 1))

                for (signal, _) in lhs_masks.masks():
                    signal_index = self.state.get_signal(signal)
                    emitter.append(f"next_{signal_index} = slots[{signal_index}].next")

                _StatementCompiler(self.state, emitter)(domain_stmts)

                if domain.rst is not None:
                    rhs = _RHSValueCompiler(self.state, emitter, mode="curr")
                    rst = rhs(domain.rst)
                    rst = f"(1 & {rst})"
                    emitter.append(f"if {rst}:")
                    with emitter.indent():
                        emitter.append("pass")
                        for (signal, _) in lhs_masks.masks():
                            if not signal.reset_less:
                                signal_index = self.state.get_signal(signal)
                                emitter.append(f"next_{signal_index} = {signal.init}")

                if isinstance(fragment, MemoryInstance):
                    memory_index = self.state.get_memory(fragment._data)
                    rhs = _RHSValueCompiler(self.state, emitter, mode="curr")
                    lhs = _LHSValueCompiler(self.state, emitter, rhs=rhs)

                    write_vals = {}

                    for idx, port in enumerate(fragment._write_ports):
                        if port._domain != domain_name:
                            continue

                        addr = rhs(port._addr)
                        addr = emitter.def_var("write_addr", f"({(1 << len(port._addr)) - 1:#x} & {addr})")
                        data = rhs(port._data)
                        data = emitter.def_var("write_data", f"({(1 << len(port._data)) - 1:#x} & {data})")
                        en = rhs(Cat(bit.replicate(port._granularity) for bit in port._en))
                        en = emitter.def_var("write_en", f"({(1 << len(port._data)) - 1:#x} & {en})")
                        emitter.append(f"slots[{memory_index}].write({addr}, {data}, {en})")
                        write_vals[idx] = addr, data, en

                    for port in fragment._read_ports:
                        if port._domain != domain_name:
                            continue

                        en = rhs(port._en)
                        en = f"(1 & {en})"
                        emitter.append(f"if {en}:")
                        with emitter.indent():
                            addr = rhs(port._addr)
                            addr = emitter.def_var("read_addr", f"({(1 << len(port._addr)) - 1:#x} & {addr})")
                            data = emitter.def_var("read_data", f"slots[{memory_index}].read({addr})")

                            for idx in port._transparent_for:
                                waddr, wdata, wen = write_vals[idx]
                                emitter.append(f"if {addr} == {waddr}:")
                                with emitter.indent():
                                    emitter.append(f"{data} &= ~{wen}")
                                    emitter.append(f"{data} |= {wdata} & {wen}")

                            lhs(port._data)(data)

            for (signal, mask) in lhs_masks.masks():
                if signal.shape().signed and (mask & 1 << (len(signal) - 1)):
                    mask |= -1 << len(signal)
                signal_index = self.state.get_signal(signal)
                emitter.append(f"slots[{signal_index}].update(next_{signal_index}, {mask})")

            # There shouldn't be any exceptions raised by the generated code, but if there are
            # (almost certainly due to a bug in the code generator), use this environment variable
            # to make backtraces useful.
            code = emitter.flush()
            if os.getenv("AMARANTH_pysim_dump"):
                file = tempfile.NamedTemporaryFile("w", prefix="amaranth_pysim_", delete=False)
                file.write(code)
                filename = file.name
            else:
                filename = "<string>"

            exec_locals = {
                "slots": self.state.slots,
                **_ValueCompiler.helpers,
                **_StatementCompiler.helpers,
            }
            exec(compile(code, filename, "exec"), exec_locals)
            domain_process.run = exec_locals["run"]

            processes.add(domain_process)

        for subfragment_index, (subfragment, subfragment_name, _src_loc) in enumerate(fragment.subfragments):
            if subfragment_name is None:
                subfragment_name = f"U${subfragment_index}"
            processes.update(self(subfragment))

        return processes
