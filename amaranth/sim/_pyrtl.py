import os
import tempfile
from contextlib import contextmanager

from ..hdl import *
from ..hdl.ast import SignalSet
from ..hdl.xfrm import ValueVisitor, StatementVisitor, LHSGroupFilter
from ._base import BaseProcess


__all__ = ["PyRTLProcess"]


class PyRTLProcess(BaseProcess):
    __slots__ = ("is_comb", "runnable", "passive", "run")

    def __init__(self, *, is_comb):
        self.is_comb  = is_comb

        self.reset()

    def reset(self):
        self.runnable = self.is_comb
        self.passive  = True


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

        return super().on_value(value)

    def on_ClockSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_ResetSignal(self, value):
        raise NotImplementedError # :nocov:

    def on_AnyConst(self, value):
        raise NotImplementedError # :nocov:

    def on_AnySeq(self, value):
        raise NotImplementedError # :nocov:

    def on_Sample(self, value):
        raise NotImplementedError # :nocov:

    def on_Initial(self, value):
        raise NotImplementedError # :nocov:


class _RHSValueCompiler(_ValueCompiler):
    def __init__(self, state, emitter, *, mode, inputs=None):
        super().__init__(state, emitter)
        assert mode in ("curr", "next")
        self.mode = mode
        # If not None, `inputs` gets populated with RHS signals.
        self.inputs = inputs

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
            return f"({value_mask} & {self(value)})"

        def sign(value):
            if value.shape().signed:
                return f"sign({mask(value)}, {-1 << (len(value) - 1)})"
            else: # unsigned
                return mask(value)

        if len(value.operands) == 1:
            arg, = value.operands
            if value.operator == "~":
                return f"(~{self(arg)})"
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
                return f"({self(lhs)} & {self(rhs)})"
            if value.operator == "|":
                return f"({self(lhs)} | {self(rhs)})"
            if value.operator == "^":
                return f"({self(lhs)} ^ {self(rhs)})"
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
        elif len(value.operands) == 3:
            if value.operator == "m":
                sel, val1, val0 = value.operands
                return f"({self(val1)} if {mask(sel)} else {self(val0)})"
        raise NotImplementedError("Operator '{}' not implemented".format(value.operator)) # :nocov:

    def on_Slice(self, value):
        return f"({(1 << len(value)) - 1} & ({self(value.value)} >> {value.start}))"

    def on_Part(self, value):
        offset_mask = (1 << len(value.offset)) - 1
        offset = f"({value.stride} * ({offset_mask} & {self(value.offset)}))"
        return f"({(1 << value.width) - 1} & " \
               f"{self(value.value)} >> {offset})"

    def on_Cat(self, value):
        gen_parts = []
        offset = 0
        for part in value.parts:
            part_mask = (1 << len(part)) - 1
            gen_parts.append(f"(({part_mask} & {self(part)}) << {offset})")
            offset += len(part)
        if gen_parts:
            return f"({' | '.join(gen_parts)})"
        return f"0"

    def on_Repl(self, value):
        part_mask = (1 << len(value.value)) - 1
        gen_part = self.emitter.def_var("repl", f"{part_mask} & {self(value.value)}")
        gen_parts = []
        offset = 0
        for _ in range(value.count):
            gen_parts.append(f"({gen_part} << {offset})")
            offset += len(value.value)
        if gen_parts:
            return f"({' | '.join(gen_parts)})"
        return f"0"

    def on_ArrayProxy(self, value):
        index_mask = (1 << len(value.index)) - 1
        gen_index = self.emitter.def_var("rhs_index", f"{index_mask} & {self(value.index)}")
        gen_value = self.emitter.gen_var("rhs_proxy")
        if value.elems:
            for index, elem in enumerate(value.elems):
                if index == 0:
                    self.emitter.append(f"if {index} == {gen_index}:")
                else:
                    self.emitter.append(f"elif {index} == {gen_index}:")
                with self.emitter.indent():
                    self.emitter.append(f"{gen_value} = {self(elem)}")
            self.emitter.append(f"else:")
            with self.emitter.indent():
                self.emitter.append(f"{gen_value} = {self(value.elems[-1])}")
            return gen_value
        else:
            return f"0"

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
        self.lrhs = _RHSValueCompiler(state, emitter, mode="next", inputs=None)
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
                value_sign = f"sign({value_mask} & {arg}, {-1 << (len(value) - 1)})"
            else: # unsigned
                value_sign = f"{value_mask} & {arg}"
            self.emitter.append(f"next_{self.state.get_signal(value)} = {value_sign}")
        return gen

    def on_Operator(self, value):
        raise TypeError # :nocov:

    def on_Slice(self, value):
        def gen(arg):
            width_mask = (1 << (value.stop - value.start)) - 1
            self(value.value)(f"({self.lrhs(value.value)} & " \
                f"{~(width_mask << value.start)} | " \
                f"(({width_mask} & {arg}) << {value.start}))")
        return gen

    def on_Part(self, value):
        def gen(arg):
            width_mask = (1 << value.width) - 1
            offset_mask = (1 << len(value.offset)) - 1
            offset = f"({value.stride} * ({offset_mask} & {self.rrhs(value.offset)}))"
            self(value.value)(f"({self.lrhs(value.value)} & " \
                f"~({width_mask} << {offset}) | " \
                f"(({width_mask} & {arg}) << {offset}))")
        return gen

    def on_Cat(self, value):
        def gen(arg):
            gen_arg = self.emitter.def_var("cat", arg)
            offset = 0
            for part in value.parts:
                part_mask = (1 << len(part)) - 1
                self(part)(f"({part_mask} & ({gen_arg} >> {offset}))")
                offset += len(part)
        return gen

    def on_Repl(self, value):
        raise TypeError # :nocov:

    def on_ArrayProxy(self, value):
        def gen(arg):
            index_mask = (1 << len(value.index)) - 1
            gen_index = self.emitter.def_var("index", f"{self.rrhs(value.index)} & {index_mask}")
            if value.elems:
                for index, elem in enumerate(value.elems):
                    if index == 0:
                        self.emitter.append(f"if {index} == {gen_index}:")
                    else:
                        self.emitter.append(f"elif {index} == {gen_index}:")
                    with self.emitter.indent():
                        self(elem)(arg)
                self.emitter.append(f"else:")
                with self.emitter.indent():
                    self(value.elems[-1])(arg)
            else:
                self.emitter.append(f"pass")
        return gen


class _StatementCompiler(StatementVisitor, _Compiler):
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
        gen_rhs_value = self.rhs(stmt.rhs) # check for oversized value before generating mask
        gen_rhs = f"({(1 << len(stmt.rhs)) - 1} & {gen_rhs_value})"
        if stmt.rhs.shape().signed:
            gen_rhs = f"sign({gen_rhs}, {-1 << (len(stmt.rhs) - 1)})"
        return self.lhs(stmt.lhs)(gen_rhs)

    def on_Switch(self, stmt):
        gen_test_value = self.rhs(stmt.test) # check for oversized value before generating mask
        gen_test = self.emitter.def_var("test", f"{(1 << len(stmt.test)) - 1} & {gen_test_value}")
        for index, (patterns, stmts) in enumerate(stmt.cases.items()):
            gen_checks = []
            if not patterns:
                gen_checks.append(f"True")
            else:
                for pattern in patterns:
                    if "-" in pattern:
                        mask  = int("".join("0" if b == "-" else "1" for b in pattern), 2)
                        value = int("".join("0" if b == "-" else  b  for b in pattern), 2)
                        gen_checks.append(f"{value} == ({mask} & {gen_test})")
                    else:
                        value = int(pattern, 2)
                        gen_checks.append(f"{value} == {gen_test}")
            if index == 0:
                self.emitter.append(f"if {' or '.join(gen_checks)}:")
            else:
                self.emitter.append(f"elif {' or '.join(gen_checks)}:")
            with self.emitter.indent():
                self(stmts)

    def on_Assert(self, stmt):
        raise NotImplementedError # :nocov:

    def on_Assume(self, stmt):
        raise NotImplementedError # :nocov:

    def on_Cover(self, stmt):
        raise NotImplementedError # :nocov:

    @classmethod
    def compile(cls, state, stmt):
        output_indexes = [state.get_signal(signal) for signal in stmt._lhs_signals()]
        emitter = _PythonEmitter()
        for signal_index in output_indexes:
            emitter.append(f"next_{signal_index} = slots[{signal_index}].next")
        compiler = cls(state, emitter)
        compiler(stmt)
        for signal_index in output_indexes:
            emitter.append(f"slots[{signal_index}].set(next_{signal_index})")
        return emitter.flush()


class _FragmentCompiler:
    def __init__(self, state):
        self.state = state

    def __call__(self, fragment):
        processes = set()

        for domain_name, domain_signals in fragment.drivers.items():
            domain_stmts = LHSGroupFilter(domain_signals)(fragment.statements)
            domain_process = PyRTLProcess(is_comb=domain_name is None)

            emitter = _PythonEmitter()
            emitter.append(f"def run():")
            emitter._level += 1

            if domain_name is None:
                for signal in domain_signals:
                    signal_index = self.state.get_signal(signal)
                    emitter.append(f"next_{signal_index} = {signal.reset}")

                inputs = SignalSet()
                _StatementCompiler(self.state, emitter, inputs=inputs)(domain_stmts)

                for input in inputs:
                    self.state.add_trigger(domain_process, input)

            else:
                domain = fragment.domains[domain_name]
                clk_trigger = 1 if domain.clk_edge == "pos" else 0
                self.state.add_trigger(domain_process, domain.clk, trigger=clk_trigger)
                if domain.rst is not None and domain.async_reset:
                    rst_trigger = 1
                    self.state.add_trigger(domain_process, domain.rst, trigger=rst_trigger)

                for signal in domain_signals:
                    signal_index = self.state.get_signal(signal)
                    emitter.append(f"next_{signal_index} = slots[{signal_index}].next")

                _StatementCompiler(self.state, emitter)(domain_stmts)

            for signal in domain_signals:
                signal_index = self.state.get_signal(signal)
                emitter.append(f"slots[{signal_index}].set(next_{signal_index})")

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

            exec_locals = {"slots": self.state.slots, **_ValueCompiler.helpers}
            exec(compile(code, filename, "exec"), exec_locals)
            domain_process.run = exec_locals["run"]

            processes.add(domain_process)

        for subfragment_index, (subfragment, subfragment_name) in enumerate(fragment.subfragments):
            if subfragment_name is None:
                subfragment_name = "U${}".format(subfragment_index)
            processes.update(self(subfragment))

        return processes
