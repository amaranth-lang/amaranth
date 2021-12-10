import functools
import inspect
from collections.abc import Iterable
from ...hdl.cd import ClockDomain
from ...hdl.ir import Fragment
from ...sim import *


__all__ = ["run_simulation", "passive"]


def run_simulation(fragment_or_module, generators, clocks={"sync": 10}, vcd_name=None,
                   special_overrides={}):
    assert not special_overrides

    if hasattr(fragment_or_module, "get_fragment"):
        fragment = fragment_or_module.get_fragment()
    else:
        fragment = fragment_or_module

    fragment = Fragment.get(fragment, platform=None)

    if not isinstance(generators, dict):
        generators = {"sync": generators}
        if "sync" not in fragment.domains:
            fragment.add_domains(ClockDomain("sync"))

    sim = Simulator(fragment)
    for domain, period in clocks.items():
        sim.add_clock(period / 1e9, domain=domain)
    for domain, processes in generators.items():
        def wrap(process):
            def wrapper():
                yield from process
            return wrapper
        if isinstance(processes, Iterable) and not inspect.isgenerator(processes):
            for process in processes:
                sim.add_sync_process(wrap(process), domain=domain)
        else:
            sim.add_sync_process(wrap(processes), domain=domain)

    if vcd_name is not None:
        with sim.write_vcd(vcd_name):
            sim.run()
    else:
        sim.run()


def passive(generator):
    @functools.wraps(generator)
    def wrapper(*args, **kwargs):
        yield Passive()
        yield from generator(*args, **kwargs)
    return wrapper
