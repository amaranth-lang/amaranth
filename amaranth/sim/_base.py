__all__ = ["BaseProcess", "BaseSignalState", "BaseSimulation", "BaseEngine"]


class BaseProcess:
    __slots__ = ()

    def __init__(self):
        self.reset()

    def reset(self):
        self.runnable = False
        self.passive  = True

    def run(self):
        raise NotImplementedError


class BaseSignalState:
    __slots__ = ()

    signal = NotImplemented

    curr = NotImplemented
    next = NotImplemented

    def set(self, value):
        raise NotImplementedError


class BaseSimulation:
    def reset(self):
        raise NotImplementedError

    def get_signal(self, signal):
        raise NotImplementedError

    slots = NotImplemented

    def add_trigger(self, process, signal, *, trigger=None):
        raise NotImplementedError

    def remove_trigger(self, process, signal):
        raise NotImplementedError

    def wait_interval(self, process, interval):
        raise NotImplementedError


class BaseEngine:
    def add_coroutine_process(self, process, *, default_cmd):
        raise NotImplementedError

    def add_clock_process(self, clock, *, phase, period):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError

    @property
    def now(self):
        raise NotImplementedError

    def advance(self):
        raise NotImplementedError

    def write_vcd(self, *, vcd_file, gtkw_file, traces):
        raise NotImplementedError
