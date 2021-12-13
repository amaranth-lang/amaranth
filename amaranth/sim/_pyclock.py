from ._base import BaseProcess


__all__ = ["PyClockProcess"]


class PyClockProcess(BaseProcess):
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
        self.runnable = False

        if self.initial:
            self.initial = False
            self.state.wait_interval(self, self.phase)

        else:
            clk_state = self.state.slots[self.slot]
            clk_state.set(not clk_state.curr)
            self.state.wait_interval(self, self.period // 2)
