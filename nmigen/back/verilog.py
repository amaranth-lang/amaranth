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


def _convert_il_text(il_text, strip_src):
    version, offset = _yosys_version()
    if version < (0, 9):
        raise YosysError("Yosys %d.%d is not suppored", *version)

    attr_map = []
    if strip_src:
        attr_map.append("-remove src")

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
attrmap {}
write_verilog -norename
""".format(il_text, " ".join(attr_map),
           prune="# " if version == (0, 9) and offset == 0 else "")

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


def convert_fragment(*args, strip_src=False, **kwargs):
    il_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _convert_il_text(il_text, strip_src), name_map


def convert(*args, strip_src=False, **kwargs):
    il_text = rtlil.convert(*args, **kwargs)
    return _convert_il_text(il_text, strip_src)
