import warnings

from ...hdl.ir import Fragment
from ...hdl.cd import ClockDomain
from ...back import verilog
from .conv_output import ConvOutput
from .module import Module


def convert(fi, ios=None, name="top", special_overrides=dict(),
            attr_translate=None, create_clock_domains=True,
            display_run=False):
    if display_run:
        warnings.warn("`display_run=True` support has been removed",
                      DeprecationWarning, stacklevel=1)
    if special_overrides:
        warnings.warn("`special_overrides` support as well as `Special` has been removed",
                      DeprecationWarning, stacklevel=1)
    # TODO: attr_translate

    if isinstance(fi, Module):
        fi = fi.get_fragment()

    def missing_domain(name):
        if create_clock_domains:
            return ClockDomain(name)
    v_output = verilog.convert(
        elaboratable=fi,
        name=name,
        ports=ios or (),
        missing_domain=missing_domain
    )
    output = ConvOutput()
    output.set_main_source(v_output)
    return output
