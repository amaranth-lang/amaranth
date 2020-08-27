from .._toolchain.yosys import *
from . import rtlil


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text(rtlil_text, *, strip_internal_attrs=False, write_verilog_opts=()):
    # this version requirement needs to be synchronized with the one in setup.py!
    yosys = find_yosys(lambda ver: ver >= (0, 9))
    yosys_version = yosys.version()

    script = []
    script.append("read_ilang <<rtlil\n{}\nrtlil".format(rtlil_text))

    if yosys_version >= (0, 9, 3527):
        # Yosys >=0.9+3527 (since commit 656ee70f) supports the `-nomux` option for the `proc`
        # script pass. Because the individual `proc_*` passes are not a stable interface,
        # `proc -nomux` is used instead, if available.
        script.append("delete w:$verilog_initial_trigger")
        script.append("proc -nomux")
    else:
        # On earlier versions, use individual `proc_*` passes; this is a known range of Yosys
        # versions and we know it's compatible with what nMigen does.
        script.append("proc_init")
        script.append("proc_arst")
        script.append("proc_dff")
        script.append("proc_clean")
    script.append("memory_collect")

    if strip_internal_attrs:
        attr_map = []
        attr_map.append("-remove generator")
        attr_map.append("-remove top")
        attr_map.append("-remove src")
        attr_map.append("-remove nmigen.hierarchy")
        attr_map.append("-remove nmigen.decoding")
        script.append("attrmap {}".format(" ".join(attr_map)))
        script.append("attrmap -modattr {}".format(" ".join(attr_map)))

    script.append("write_verilog -norename {}".format(" ".join(write_verilog_opts)))

    return yosys.run(["-q", "-"], "\n".join(script),
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
