from .._yosys import *
from . import rtlil


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text(rtlil_text, *, src_loc_at=0):
     # FIXME: update this requirement once Yosys updates its node version
    yosys = find_yosys(lambda ver: ver >= (0, 9))
    return yosys.run(["-q", "-"], """
read_ilang <<rtlil
{}
rtlil
delete w:$verilog_initial_trigger
write_cxxrtl
""".format(rtlil_text), src_loc_at=1 + src_loc_at)


def convert_fragment(*args, **kwargs):
    rtlil_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _convert_rtlil_text(rtlil_text, src_loc_at=1), name_map


def convert(*args, **kwargs):
    rtlil_text = rtlil.convert(*args, **kwargs)
    return _convert_rtlil_text(rtlil_text, src_loc_at=1)
