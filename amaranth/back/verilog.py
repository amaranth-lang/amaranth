from .._toolchain.yosys import *
from ..hdl import _ast, _ir
from ..lib import wiring
from . import rtlil


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text(rtlil_text, *, strip_internal_attrs=False, write_verilog_opts=()):
    # This version requirement needs to be synchronized with the one in pyproject.toml!
    yosys = find_yosys(lambda ver: ver >= (0, 40))

    script = []
    script.append(f"read_ilang <<rtlil\n{rtlil_text}\nrtlil")
    script.append("proc -nomux -norom")
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


def convert(elaboratable, name="top", platform=None, *, ports=None, emit_src=True,
            strip_internal_attrs=False, **kwargs):
    if (ports is None and
            hasattr(elaboratable, "signature") and
            isinstance(elaboratable.signature, wiring.Signature)):
        ports = {}
        for path, member, value in elaboratable.signature.flatten(elaboratable):
            if isinstance(value, _ast.ValueCastable):
                value = value.as_value()
            if isinstance(value, _ast.Value):
                if member.flow == wiring.In:
                    dir = _ir.PortDirection.Input
                else:
                    dir = _ir.PortDirection.Output
                ports["__".join(map(str, path))] = (value, dir)
    elif ports is None:
        raise TypeError("The `convert()` function requires a `ports=` argument")
    fragment = _ir.Fragment.get(elaboratable, platform)
    verilog_text, name_map = convert_fragment(fragment, ports, name, emit_src=emit_src, strip_internal_attrs=strip_internal_attrs, **kwargs)
    return verilog_text
