import inspect

from ._core import Process


__all__ = ["PyClockProcess"]


class PyClockProcess(Process):
    def __init__(self, state, signal, *, phase, period):
        assert len(signal) == 1

        self.state  = state
        self.slot   = self.state.get_signal(signal)
        self.phase  = phase
        self.period = period

        self.reset()

    def reset(self):
        self.runnable = True
        self.passive = True
        self.initial = True

    def run(self):
        if self.initial:
            self.initial = False
            self.state.timeline.delay(self.phase, self)

        else:
            clk_state = self.state.slots[self.slot]
            clk_state.set(not clk_state.curr)
            self.state.timeline.delay(self.period / 2, self)

        self.runnable = False
