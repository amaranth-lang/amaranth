import itertools
import re
import enum as py_enum

import nanots

from ..hdl import *
from ..hdl._mem import MemoryInstance
from ..hdl._ast import SignalDict
from ..lib import data, wiring
from ._base import *
from ._async import *


class TimeSeriesWriter(Observer):
    def __init__(self, state, design, *, db_filename, traces=(), **kwargs):
        super().__init__(**kwargs)

        self.state = state

        self._signal_vars = SignalDict()
        self._memory_vars = {}

        self.traces = traces

        self.writer = nanots.Writer(db_filename, auto_reclaim=False)

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
                        if trace_signal and trace_signal not in signal_names:
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

        for signal, names in itertools.chain(signal_names.items(), trace_names.items()):
            self._signal_vars[signal] = []

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
                        context = writer.create_context(f"{var_scope}@{field_name}"
                            scope=var_scope, name=field_name,
                            var_type=var_type, size=var_size, init=var_init)
                        if var_size > 1:
                            suffix = f"[{var_size - 1}:0]"
                        else:
                            suffix = ""
                        self._signal_names[signal].append(
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


