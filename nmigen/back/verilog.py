from .._toolchain.yosys import *
from . import rtlil


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text(rtlil_text, *, strip_internal_attrs=False, write_script=[]):
    # this version requirement needs to be synchronized with the one in setup.py!
    yosys = find_yosys(lambda ver: ver >= (0, 9))
    yosys_version = yosys.version()

    script = []
    script.append("read_ilang <<rtlil\n{}\nrtlil".format(rtlil_text))

    if yosys_version >= (0, 9, 231):
        # Yosys 0.9 release has buggy proc_prune.
        script.append("delete w:$verilog_initial_trigger")
        script.append("proc_prune")
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

    script.extend(write_script)

    return yosys.run(["-q", "-"], "\n".join(script),
        # At the moment, Yosys always shows a warning indicating that not all processes can be
        # translated to Verilog. We carefully emit only the processes that *can* be translated, and
        # squash this warning. Once Yosys' write_verilog pass is fixed, we should remove this.
        ignore_warnings=True)


def _convert_rtlil_text_verilog(rtlil_text, *, strip_internal_attrs=False, write_verilog_opts=()):
    write_script = []
    write_script.append("write_verilog -norename {}".format(" ".join(write_verilog_opts)))

    return _convert_rtlil_text(rtlil_text,
        strip_internal_attrs=strip_internal_attrs, write_script=write_script)


def convert_fragment(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _convert_rtlil_text_verilog(rtlil_text, strip_internal_attrs=strip_internal_attrs), name_map


def convert(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text = rtlil.convert(*args, **kwargs)
    return _convert_rtlil_text_verilog(rtlil_text, strip_internal_attrs=strip_internal_attrs)
