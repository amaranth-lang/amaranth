import os
import tempfile
from contextlib import contextmanager
from vcd.gtkw import GTKWSave

from ..hdl import *
from ..hdl.ast import SignalDict
from .._toolchain.yosys import find_yosys
from .._toolchain.cxx import build_cxx
from ..back import cxxrtl
from ._base import *
from ._sched import *
from ._cxxrtl import cxxrtl_type, cxxrtl_flag, cxxrtl_object, cxxrtl_library, cxxrtl_trace_library
from ._pycoro import PyCoroProcess
from ._pyclock import PyClockProcess


__all__ = ["CxxSimEngine"]


class _CxxSignalState(BaseSignalState):
    def __init__(self, signal, parts):
        self.signal = signal
        self.parts  = parts

    def reset(self):
        for part in self.parts:
            part.curr = part.next = self.signal.reset

    @property
    def curr(self):
        value = 0
        for part in self.parts:
            value |= part.curr
        return value

    @property
    def next(self):
        value = 0
        for part in self.parts:
            value |= part.next
        return value

    def set(self, value):
        for part in self.parts:
            part.next = value

    def commit(self):
        next_value = self.next
        if self.curr == next_value:
            return False
        for part in self.parts:
            part.curr = next_value
        return True


class _CxxRTLProcess(BaseProcess):
    def __init__(self, cxxlib, handle):
        self.cxxlib = cxxlib
        self.handle = handle

        self.reset()

    def reset(self):
        self.runnable = True
        self.passive  = True

        self.cxxlib.reset(self.handle)

    def run(self):
        self.cxxlib.eval(self.handle)


class _CxxSimulation(BaseSimulation):
    def __init__(self, cxxlib, names):
        self.cxxlib = cxxlib
        self.names = names

        self.slots = []
        self.owned = set()

        self.rtl_handle  = self.cxxlib.create_at(self.cxxlib.design_create(), b"top")
        self.rtl_process = _CxxRTLProcess(self.cxxlib, self.rtl_handle)
        self.rtl_signals = SignalDict()

        self.sim_signals = SignalDict()

        self.timeline = Timeline()
        self.triggers = {}

    def reset(self):
        self.timeline.reset()

        for signal_state in self.owned:
            signal_state.reset()

    def _add_signal(self, signal, signal_parts, *, owned):
        signal_state = _CxxSignalState(signal, signal_parts)
        if owned:
            self.owned.add(signal_state)

        index = len(self.slots)
        self.slots.append(signal_state)
        return index

    def _add_rtl_signal(self, signal):
        raw_name = " ".join(self.names[signal]).encode()
        signal_parts = self.cxxlib.get_parts(self.rtl_handle, raw_name)
        assert all(part.type == signal_parts[0].type for part in signal_parts)

        if (signal_parts[0].type == cxxrtl_type.VALUE and
                signal_parts[0].flags & cxxrtl_flag.UNDRIVEN):
            shadow_parts = [cxxrtl_object.create_shadow(part) for part in signal_parts]
            index = self._add_signal(signal, shadow_parts, owned=True)

        elif signal_parts[0].type in (cxxrtl_type.WIRE, cxxrtl_type.VALUE, cxxrtl_type.ALIAS):
            index = self._add_signal(signal, signal_parts, owned=False)

        else:
            assert False, f"unsupported signal type {signal_parts[0].type}"

        # FIXME: toggling a clock input that is a CXXRTL_WIRE won't work because of how the posedge
        # detector in generated code works; we wake the CXXRTL process while committing, but that
        # means the detector will never fire
        self.triggers[self.rtl_process, index] = None

        return index

    def _add_sim_signal(self, signal):
        signal_part = cxxrtl_object.create(cxxrtl_type.WIRE, len(signal))
        signal_part.curr = signal_part.next = signal.reset
        return self._add_signal(signal, [signal_part], owned=True)

    def get_signal(self, signal):
        if signal in self.names:
            try:
                index = self.rtl_signals[signal]
            except KeyError:
                index = self._add_rtl_signal(signal)
                self.rtl_signals[signal] = index
            return index
        else:
            try:
                index = self.sim_signals[signal]
            except KeyError:
                index = self._add_sim_signal(signal)
                self.sim_signals[signal] = index
            return index

    def add_trigger(self, process, signal, *, trigger=None):
        self.triggers[process, self.get_signal(signal)] = trigger

    def remove_trigger(self, process, signal):
        del self.triggers[process, self.get_signal(signal)]

    def wait_interval(self, process, interval):
        self.timeline.delay(interval, process)

    def commit(self):
        converged = True

        for (process, signal_index), trigger in self.triggers.items():
            signal_state = self.slots[signal_index]
            try:
                if signal_state.next == signal_state.curr:
                    continue
            except ValueError: # FIXME: handle aliases (and driven comb signals) properly here
                continue
            if trigger is None or signal_state.next == trigger:
                process.runnable = True
                converged = False

        if self.cxxlib.commit(self.rtl_handle):
            converged = False

        for signal_state in self.owned:
            if signal_state.commit():
                converged = False

        return converged


class CxxSimEngine(BaseEngine):
    def __init__(self, fragment):
        # All undriven signals are converted to toplevel ports by Fragment.prepare(), which is
        # necessary to enable testbench reuse between pysim and cxxsim; pysim testbenches assume
        # that any otherwise undriven signal functions like a register, and converting them to
        # inputs is the only reasonable way to preserve that for cxxsim. However, this conversion
        # drops the reset value, since the Yosys model only has initial values for registers and
        # not inputs, which are wires. Preserve the reset value by setting it directly on toplevel
        # inputs, which is recognized by CXXRTL as an extension to the Yosys model.
        for port, dir in fragment.ports.items():
            if dir == "i":
                port.attrs["init"] = port.reset

        yosys = cxxrtl._find_yosys()
        cxx_source, name_map = cxxrtl.convert_fragment(fragment)

        if os.getenv("AMARANTH_cxxsim_dump"):
            with tempfile.NamedTemporaryFile("w",
                    prefix="amaranth_cxxsim_", suffix=".cc", delete=False) as f:
                f.write(cxx_source)
                print(f"Dumped generated C++ code to {f.name}")

        self._build_dir, so_filename = build_cxx(
            cxx_sources={"sim.cc": cxx_source},
            include_dirs=[yosys.data_dir() / "include"],
            macros=["CXXRTL_NDEBUG", "CXXRTL_INCLUDE_CAPI_IMPL", "CXXRTL_INCLUDE_VCD_CAPI_IMPL"],
            output_name="sim"
        )

        full_so_filename = os.path.join(self._build_dir.name, so_filename)
        if os.getenv("AMARANTH_cxxsim_trace"):
            cxxlib = cxxrtl_trace_library(full_so_filename)
        else:
            cxxlib = cxxrtl_library(full_so_filename)

        self._state = _CxxSimulation(cxxlib, name_map)
        self._timeline = self._state.timeline

        self._fragment = fragment
        self._processes = {self._state.rtl_process}
        self._vcd_writers = []

    def __del__(self):
        try:
            self._build_dir.cleanup()
        except AttributeError:
            pass

    def add_coroutine_process(self, process, *, default_cmd):
        self._processes.add(PyCoroProcess(self._state, self._fragment.domains, process,
                                          default_cmd=default_cmd))

    def add_clock_process(self, clock, *, phase, period):
        self._processes.add(PyClockProcess(self._state, clock,
                                           phase=phase, period=period))

    def reset(self):
        self._state.reset()
        for process in self._processes:
            process.reset()

    def _step(self):
        while True:
            for process in self._processes:
                if process.runnable:
                    process.runnable = False
                    process.run()

            if self._state.commit():
                break

        for vcd_writer, vcd_file in self._vcd_writers:
            self._state.cxxlib.vcd_sample(vcd_writer, int(self._timeline.now * 10 ** 10))
            vcd_file.write(self._state.cxxlib.vcd_read(vcd_writer))

    def advance(self):
        self._step()
        self._timeline.advance()
        return any(not process.passive for process in self._processes)

    @property
    def now(self):
        return self._timeline.now

    @contextmanager
    def write_vcd(self, vcd_file, gtkw_file=None, *, traces=()):
        if isinstance(vcd_file, str):
            vcd_file = open(vcd_file, "wb")
        if isinstance(gtkw_file, str):
            gtkw_file = open(gtkw_file, "wt")

        for trace_signal in traces:
            # Ensure that all simulation-only signals in `traces` are registered, since it is
            # not possible to add new signals to a VCD file once data is being streamed into it.
            self._state.get_signal(trace_signal)

        try:
            vcd_writer = self._state.cxxlib.vcd_create()
            self._vcd_writers.append((vcd_writer, vcd_file))
            self._state.cxxlib.vcd_timescale(vcd_writer, 100, b"ps")
            self._state.cxxlib.vcd_add_from(vcd_writer, self._state.rtl_handle)

            used_sim_names = set()
            sim_names = SignalDict()
            for signal, index in self._state.sim_signals.items():
                signal_state = self._state.slots[index]
                assert len(signal_state.parts) == 1

                signal_name = signal.name
                name_index = 1
                while signal_name in used_sim_names:
                    signal_name = "{}${}".format(signal.name, name_index)
                    name_index += 1

                self._state.cxxlib.vcd_add(vcd_writer, signal_name.encode(), signal_state.parts[0])
                used_sim_names.add(signal_name)
                sim_names[signal] = signal_name

            yield
        finally:
            self._state.cxxlib.vcd_sample(vcd_writer, int(self._timeline.now * 10 ** 10))
            vcd_file.write(self._state.cxxlib.vcd_read(vcd_writer))
            self._vcd_writers.remove((vcd_writer, vcd_file))
            self._state.cxxlib.vcd_destroy(vcd_writer)

            if gtkw_file is not None:
                gtkw_save = GTKWSave(gtkw_file)
                gtkw_save.dumpfile(vcd_file.name)
                gtkw_save.dumpfile_size(vcd_file.tell())
                gtkw_save.treeopen("top")
                for signal in traces:
                    if len(signal) > 1 and not signal.decoder:
                        suffix = "[{}:0]".format(len(signal) - 1)
                    else:
                        suffix = ""
                    if signal in self._state.names:
                        gtkw_save.trace(".".join(self._state.names[signal]) + suffix)
                    else:
                        gtkw_save.trace(sim_names[signal] + suffix)

            vcd_file.close()
            if gtkw_file is not None:
                gtkw_file.close()
