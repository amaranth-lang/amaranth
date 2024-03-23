__all__ = ["BaseProcess", "BaseSignalState", "BaseMemoryState", "BaseSimulation", "BaseEngine"]


class BaseProcess:
    __slots__ = ()

    def __init__(self):
        self.reset()

    def reset(self):
        self.runnable = False
        self.passive  = True

    def run(self):
        raise NotImplementedError # :nocov:


class BaseSignalState:
    __slots__ = ()

    signal = NotImplemented

    curr = NotImplemented
    next = NotImplemented

    def set(self, value):
        raise NotImplementedError # :nocov:


class BaseMemoryState:
    __slots__ = ()

    memory = NotImplemented

    def read(self, addr):
        raise NotImplementedError # :nocov:

    def write(self, addr, value):
        raise NotImplementedError # :nocov:


class BaseSimulation:
    def reset(self):
        raise NotImplementedError # :nocov:

    def get_signal(self, signal):
        raise NotImplementedError # :nocov:

    slots = NotImplemented

    def add_trigger(self, process, signal, *, trigger=None):
        raise NotImplementedError # :nocov:

    def remove_trigger(self, process, signal):
        raise NotImplementedError # :nocov:

    def add_memory_trigger(self, process, identity):
        raise NotImplementedError # :nocov:

    def remove_memory_trigger(self, process, identity):
        raise NotImplementedError # :nocov:

    def wait_interval(self, process, interval):
        raise NotImplementedError # :nocov:


class BaseEngine:
    def add_clock_process(self, clock, *, phase, period):
        raise NotImplementedError # :nocov:

    def add_coroutine_process(self, process, *, default_cmd):
        raise NotImplementedError # :nocov:

    def add_testbench_process(self, process):
        raise NotImplementedError # :nocov:

    def reset(self):
        raise NotImplementedError # :nocov:

    @property
    def now(self):
        raise NotImplementedError # :nocov:

    def advance(self):
        raise NotImplementedError # :nocov:

    def write_vcd(self, *, vcd_file, gtkw_file, traces, fs_per_delta):
        raise NotImplementedError # :nocov:
