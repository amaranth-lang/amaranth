import os
import subprocess

from . import rtlil


__all__ = ["convert"]


class YosysError(Exception):
    pass


def convert(*args, **kwargs):
    il_text = rtlil.convert(*args, **kwargs)
    popen = subprocess.Popen([os.getenv("YOSYS", "yosys"), "-q", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8")
    verilog_text, error = popen.communicate("""
# Convert nMigen's RTLIL to readable Verilog.
read_ilang <<rtlil
{}
rtlil
proc_init
proc_arst
proc_dff
proc_clean
write_verilog
# Make sure there are no undriven wires in generated RTLIL.
proc
write_ilang x.il
select -assert-none w:* i:* %a %d o:* %a %ci* %d c:* %co* %a %d n:$* %d
""".format(il_text))
    if popen.returncode:
        raise YosysError(error.strip())
    else:
        return verilog_text
