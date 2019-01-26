import warnings

from ...hdl.ir import Fragment
from ...back import verilog
from .conv_output import ConvOutput


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

    v_output = verilog.convert(
        fragment=Fragment.get(fi.get_fragment(), platform=None),
        name=name,
        ports=ios or (),
        ensure_sync_exists=create_clock_domains
    )
    output = ConvOutput()
    output.set_main_source(v_output)
    return output
