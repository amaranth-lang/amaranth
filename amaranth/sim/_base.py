from abc import ABCMeta, abstractmethod

__all__ = ["BaseProcess", "BaseSignalState", "BaseMemoryState", "BaseEngineState", "BaseEngine", "Observer"]


class Observer(metaclass=ABCMeta):
    @property
    @abstractmethod
    def fs_per_delta(self) -> int:
        return 0

    @abstractmethod
    def update_signal(self, timestamp, signal):
       ...

    @abstractmethod
    def update_memory(self, timestamp, memory, addr):
        ...

    @abstractmethod
    def close(self, timestamp):
       assert False


class BaseProcess:
    __slots__ = ()

    runnable = False
    critical = False

    def reset(self):
        raise NotImplementedError # :nocov:

    def run(self):
        raise NotImplementedError # :nocov:


class BaseSignalState:
    __slots__ = ()

    signal = NotImplemented
    is_comb = NotImplemented

    curr = NotImplemented
    next = NotImplemented

    def update(self, value, mask=~0):
        raise NotImplementedError # :nocov:


class BaseMemoryState:
    __slots__ = ()

    memory = NotImplemented

    def read(self, addr):
        raise NotImplementedError # :nocov:

    def write(self, addr, value, mask=None):
        raise NotImplementedError # :nocov:


class BaseEngineState:
    def reset(self):
        raise NotImplementedError # :nocov:

    def get_signal(self, signal):
        raise NotImplementedError # :nocov:

    def get_memory(self, memory):
        raise NotImplementedError # :nocov:

    slots = NotImplemented

    def set_delay_waker(self, interval, waker):
        raise NotImplementedError # :nocov:

    def add_signal_waker(self, signal, waker):
        raise NotImplementedError # :nocov:

    def add_memory_waker(self, memory, waker):
        raise NotImplementedError # :nocov:


class BaseEngine:
    @property
    def state(self) -> BaseEngineState:
        raise NotImplementedError # :nocov:

    @property
    def now(self):
        raise NotImplementedError # :nocov:

    def reset(self):
        raise NotImplementedError # :nocov:

    def add_clock_process(self, clock, *, phase, period):
        raise NotImplementedError # :nocov:

    def add_async_process(self, simulator, process):
        raise NotImplementedError # :nocov:

    def add_async_testbench(self, simulator, process, *, background):
        raise NotImplementedError # :nocov:

    def add_trigger_combination(self, combination, *, oneshot):
        raise NotImplementedError # :nocov:

    def get_value(self, expr):
        raise NotImplementedError # :nocov:

    def set_value(self, expr, value):
        raise NotImplementedError # :nocov:

    def step_design(self):
        raise NotImplementedError # :nocov:

    def advance(self):
        raise NotImplementedError # :nocov:

    def observe(self, observer: Observer):
        raise NotImplementedError # :nocov:
