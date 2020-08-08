from .._toolchain.yosys import *
from . import rtlil
from .verilog import _convert_rtlil_text


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text_firrtl(rtlil_text, *, strip_internal_attrs=False, write_firrtl_opts=()):
    write_script = []
    write_script.append("proc_mux") # TODO: can this be improved?
    write_script.append("write_firrtl {} -".format(" ".join(write_firrtl_opts)))

    return _convert_rtlil_text(rtlil_text,
        strip_internal_attrs=strip_internal_attrs, write_script=write_script)


def convert_fragment(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _convert_rtlil_text_firrtl(rtlil_text, strip_internal_attrs=strip_internal_attrs), name_map


def convert(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text = rtlil.convert(*args, **kwargs)
    return _convert_rtlil_text_firrtl(rtlil_text, strip_internal_attrs=strip_internal_attrs)
