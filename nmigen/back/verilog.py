import os
import re
import subprocess

from .._toolchain import *
from . import rtlil


__all__ = ["YosysError", "convert", "convert_fragment"]


class YosysError(Exception):
    pass


def _yosys_version():
    yosys_path = require_tool("yosys")
    version = subprocess.check_output([yosys_path, "-V"], encoding="utf-8")
    m = re.match(r"^Yosys ([\d.]+)(?:\+(\d+))?", version)
    tag, offset = m[1], m[2] or 0
    return tuple(map(int, tag.split("."))), offset


def _convert_rtlil_text(rtlil_text, *, strip_internal_attrs=False, write_verilog_opts=()):
    version, offset = _yosys_version()
    if version < (0, 9):
        raise YosysError("Yosys %d.%d is not suppored", *version)

    attr_map = []
    if strip_internal_attrs:
        attr_map.append("-remove generator")
        attr_map.append("-remove top")
        attr_map.append("-remove src")
        attr_map.append("-remove nmigen.hierarchy")
        attr_map.append("-remove nmigen.decoding")

    script = """
# Convert nMigen's RTLIL to readable Verilog.
read_ilang <<rtlil
{}
rtlil
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
        prune="# " if version == (0, 9) and offset == 0 else "",
        attr_map=" ".join(attr_map),
        write_verilog_opts=" ".join(write_verilog_opts),
    )

    popen = subprocess.Popen([require_tool("yosys"), "-q", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8")
    verilog_text, error = popen.communicate(script)
    if popen.returncode:
        raise YosysError(error.strip())
    else:
        return verilog_text


def convert_fragment(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _convert_rtlil_text(rtlil_text, strip_internal_attrs=strip_internal_attrs), name_map


def convert(*args, strip_internal_attrs=False, **kwargs):
    rtlil_text = rtlil.convert(*args, **kwargs)
    return _convert_rtlil_text(rtlil_text, strip_internal_attrs=strip_internal_attrs)
