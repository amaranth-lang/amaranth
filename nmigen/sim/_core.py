__all__ = ["Process", "Timeline"]


class Process:
    def __init__(self, *, is_comb):
        self.is_comb  = is_comb

        self.reset()

    def reset(self):
        self.runnable = self.is_comb
        self.passive  = True

    def run(self):
        raise NotImplementedError


class Timeline:
    def __init__(self):
        self.now = 0.0
        self.deadlines = dict()

    def reset(self):
        self.now = 0.0
        self.deadlines.clear()

    def at(self, run_at, process):
        assert process not in self.deadlines
        self.deadlines[process] = run_at

    def delay(self, delay_by, process):
        if delay_by is None:
            run_at = self.now
        else:
            run_at = self.now + delay_by
        self.at(run_at, process)

    def advance(self):
        nearest_processes = set()
        nearest_deadline = None
        for process, deadline in self.deadlines.items():
            if deadline is None:
                if nearest_deadline is not None:
                    nearest_processes.clear()
                nearest_processes.add(process)
                nearest_deadline = self.now
                break
            elif nearest_deadline is None or deadline <= nearest_deadline:
                assert deadline >= self.now
                if nearest_deadline is not None and deadline < nearest_deadline:
                    nearest_processes.clear()
                nearest_processes.add(process)
                nearest_deadline = deadline

        if not nearest_processes:
            return False

        for process in nearest_processes:
            process.runnable = True
            del self.deadlines[process]
        self.now = nearest_deadline

        return True
