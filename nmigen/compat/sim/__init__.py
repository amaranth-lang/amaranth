import functools
import inspect
from collections.abc import Iterable
from ...hdl.cd import ClockDomain
from ...back.pysim import *


__all__ = ["run_simulation", "passive"]


def run_simulation(fragment_or_module, generators, clocks={"sync": 10}, vcd_name=None,
                   special_overrides={}):
    assert not special_overrides

    if hasattr(fragment_or_module, "get_fragment"):
        fragment = fragment_or_module.get_fragment()
    else:
        fragment = fragment_or_module

    if not isinstance(generators, dict):
        generators = {"sync": generators}
        fragment.domains += ClockDomain("sync")

    with Simulator(fragment, vcd_file=open(vcd_name, "w") if vcd_name else None) as sim:
        for domain, period in clocks.items():
            sim.add_clock(period / 1e9, domain=domain)
        for domain, processes in generators.items():
            if isinstance(processes, Iterable) and not inspect.isgenerator(processes):
                for process in processes:
                    sim.add_sync_process(process, domain=domain)
            else:
                sim.add_sync_process(processes, domain=domain)
        sim.run()


def passive(generator):
    @functools.wraps(generator)
    def wrapper(*args, **kwargs):
        yield Passive()
        yield from generator(*args, **kwargs)
    return wrapper
