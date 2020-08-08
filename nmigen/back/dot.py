from .._toolchain.yosys import *
from . import rtlil
from .verilog import _convert_rtlil_text
import tempfile, os


__all__ = ["YosysError", "convert", "convert_fragment"]


def _convert_rtlil_text_dot(rtlil_text, *, strip_internal_attrs=False, show_opts=("-stretch", "-colors 42")):
    # TODO: add option in yosys to output graphviz to stdout
    with tempfile.TemporaryDirectory() as tmpdirname:
        prefix = os.path.join(tmpdirname, "tmp")
        viewer = "cat" if os.name != "nt" else "type"

        write_script = []
        # TODO: can these procs be improved?
        write_script.append("proc_mux")
        write_script.append("proc_clean")
        write_script.append("show -format dot -prefix {} -viewer {} {}"
            .format(prefix, viewer, " ".join(show_opts)))

        return _convert_rtlil_text(rtlil_text,
            strip_internal_attrs=strip_internal_attrs, write_script=write_script)


def convert_fragment(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _convert_rtlil_text_dot(rtlil_text, strip_internal_attrs=strip_internal_attrs), name_map


def convert(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text = rtlil.convert(*args, **kwargs)
    return _convert_rtlil_text_dot(rtlil_text, strip_internal_attrs=strip_internal_attrs)
