from abc import ABCMeta, abstractmethod

__all__ = ["BaseProcess", "BaseSignalState", "BaseMemoryState", "BaseEngineState", "BaseEngine", "Observer", "DummyEngine", "PrintObserver"]


class Observer(metaclass=ABCMeta):
    def __init__(self, fs_per_delta=0):
        self._fs_per_delta = fs_per_delta

    @property
    def fs_per_delta(self) -> int:
        return self._fs_per_delta

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
    # add storage for observers
    def __init__(self):
        self._observers = []

    # append observer to list
    def add_observer(self, observer: Observer):
        self._observers.append(observer)

    def notify_signal_change(self, signal):
        for observer in self._observers:
            observer.update_signal(self.now, signal)

    def notify_memory_change(self, memory, addr):
        for observer in self._observers:
            observer.update_memory(self.now, memory, addr)

    def notify_close(self):
        for observer in self._observers:
            observer.close(self.now)

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

class DummyEngine(BaseEngine):
    def __init__(self):
        super().__init__()
        self._now = 0  

    @property
    def now(self):
        return self._now

    def notify_signal_change(self, signal):
        for obs in self._observers:
            obs.update_signal(self.now, signal)

    def notify_memory_change(self, memory, addr):
        for obs in self._observers:
            obs.update_memory(self.now, memory, addr)

    def notify_close(self):
        for obs in self._observers:
            obs.close(self.now)


class PrintObserver(Observer):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def fs_per_delta(self) -> int:
        return 1

    def update_signal(self, timestamp, signal):
        print(f"[{timestamp}] Signal changed: {signal}")

    def update_memory(self, timestamp, memory, addr):
        print(f"[{timestamp}] Memory write at {addr}")

    def close(self, timestamp):
        print(f"[{timestamp}] Simulation ended")
