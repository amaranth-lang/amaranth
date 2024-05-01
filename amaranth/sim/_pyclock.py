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
        self.critical = False

        self.initial = True

    def run(self):
        self.runnable = False

        def waker():
            self.runnable = True

        if self.initial:
            self.initial = False
            self.state.set_delay_waker(self.phase, waker)

        else:
            clk_state = self.state.slots[self.slot]
            clk_state.update(not clk_state.curr)
            self.state.set_delay_waker(self.period // 2, waker)
