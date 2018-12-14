from ...back.pysim import *


__all__ = ["run_simulation"]


def run_simulation(fragment_or_module, generators, clocks={"sync": 10}, vcd_name=None,
                   special_overrides={}):
    assert not special_overrides

    if hasattr(fragment_or_module, "get_fragment"):
        fragment = fragment_or_module.get_fragment().get_fragment(platform=None)
    else:
        fragment = fragment_or_module

    if not isinstance(generators, dict):
        generators = {"sync": generators}

    with Simulator(fragment, vcd_file=open(vcd_name, "w") if vcd_name else None) as sim:
        for domain, period in clocks.items():
            sim.add_clock(period / 1e9, domain)
        for domain, process in generators.items():
            sim.add_sync_process(process, domain)
        sim.run()
