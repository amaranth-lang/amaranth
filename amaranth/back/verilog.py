import warnings

from .._toolchain.yosys import *
from ..hdl import ir
from . import rtlil


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text(rtlil_text, *, strip_internal_attrs=False, write_verilog_opts=()):
    # this version requirement needs to be synchronized with the one in setup.py!
    yosys = find_yosys(lambda ver: ver >= (0, 10))
    yosys_version = yosys.version()

    script = []
    script.append("read_ilang <<rtlil\n{}\nrtlil".format(rtlil_text))
    script.append("proc -nomux")
    script.append("memory_collect")

    if strip_internal_attrs:
        attr_map = []
        attr_map.append("-remove generator")
        attr_map.append("-remove top")
        attr_map.append("-remove src")
        attr_map.append("-remove amaranth.hierarchy")
        attr_map.append("-remove amaranth.decoding")
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


def convert(elaboratable, name="top", platform=None, ports=None, *, emit_src=True, strip_internal_attrs=False, **kwargs):
    # TODO(amaranth-0.4): remove
    if ports is None:
        warnings.warn("Implicit port determination is deprecated, specify ports explictly",
                      DeprecationWarning, stacklevel=2)
    fragment = ir.Fragment.get(elaboratable, platform).prepare(ports=ports, **kwargs)
    verilog_text, name_map = convert_fragment(fragment, name, emit_src=emit_src, strip_internal_attrs=strip_internal_attrs)
    return verilog_text
