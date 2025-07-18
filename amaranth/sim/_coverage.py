from ._base import Observer
from amaranth.sim._vcdwriter import eval_value, eval_format

class ToggleCoverageObserver(Observer):
    def __init__(self, state, **kwargs):
        self.state = state
        self._prev_values = {}
        self._toggles = {}
        self._signal_names = {}
        super().__init__(**kwargs)

    def update_signal(self, timestamp, signal):
        if getattr(signal, "name", "") != "out":
            return

        sig_id = id(signal)
        try:
            val = eval_value(self.state, signal)
        except Exception:
            val = int(self.state.get_signal(signal))
        try:
            curr_val = int(val)
        except TypeError:
            curr_val = val
        print(f"[DEBUG] Signal {getattr(signal, 'name', signal)} = {curr_val}")

        if sig_id not in self._prev_values:
            self._prev_values[sig_id] = curr_val
            self._toggles[sig_id] = {"0->1": 0, "1->0": 0}
            self._signal_names[sig_id] = signal.name  
            return

        prev_val = self._prev_values[sig_id]

        if prev_val == 0 and curr_val == 1:
            self._toggles[sig_id]["0->1"] += 1
        elif prev_val == 1 and curr_val == 0:
            self._toggles[sig_id]["1->0"] += 1

        self._prev_values[sig_id] = curr_val

    def update_memory(self, timestamp, memory, addr):
        pass 

    def get_results(self):
        return {
            self._signal_names[sig_id]: toggles
            for sig_id, toggles in self._toggles.items()
        }

    def close(self, timestamp):
        results = self.get_results()
        print("=== Toggle Coverage Report ===")
        for signal, toggles in results.items():
            print(f"{signal}: 0→1={toggles['0->1']}, 1→0={toggles['1->0']}")




