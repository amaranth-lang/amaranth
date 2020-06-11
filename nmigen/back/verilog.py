from .._yosys import *
from . import rtlil


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text(rtlil_text, *, strip_internal_attrs=False, write_verilog_opts=()):
    # this version requirement needs to be synchronized with the one in setup.py!
    yosys = find_yosys(lambda ver: ver >= (0, 9))
    yosys_version = yosys.version()

    attr_map = []
    if strip_internal_attrs:
        attr_map.append("-remove generator")
        attr_map.append("-remove top")
        attr_map.append("-remove src")
        attr_map.append("-remove nmigen.hierarchy")
        attr_map.append("-remove nmigen.decoding")

    return yosys.run(["-q", "-"], """
# Convert nMigen's RTLIL to readable Verilog.
read_ilang <<rtlil
{}
rtlil
{prune}delete w:$verilog_initial_trigger
{prune}proc_prune
proc_init
proc_arst
proc_dff
proc_clean
memory_collect
attrmap {attr_map}
attrmap -modattr {attr_map}
write_verilog -norename {write_verilog_opts}
""".format(rtlil_text,
        # Yosys 0.9 release has buggy proc_prune.
        prune="# " if yosys_version < (0, 9, 231) else "",
        attr_map=" ".join(attr_map),
        write_verilog_opts=" ".join(write_verilog_opts),
    ),
    # At the moment, Yosys always shows a warning indicating that not all processes can be
    # translated to Verilog. We carefully emit only the processes that *can* be translated, and
    # squash this warning. Once Yosys' write_verilog pass is fixed, we should remove this.
    ignore_warnings=True)


def convert_fragment(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _convert_rtlil_text(rtlil_text, strip_internal_attrs=strip_internal_attrs), name_map


def convert(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text = rtlil.convert(*args, **kwargs)
    return _convert_rtlil_text(rtlil_text, strip_internal_attrs=strip_internal_attrs)
