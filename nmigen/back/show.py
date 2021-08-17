from .._toolchain.yosys import *
from . import rtlil

__all__ = ["convert", "convert_fragment"]


def _show_rtlil_text(rtlil_text, *, src_loc_at=0):
    yosys = find_yosys(lambda ver: ver >= (0, 9, 3468))
    yosys_version = yosys.version()

    module_prefix = "module \\"

    modules = [
        m.replace(module_prefix, "") for m in rtlil_text.split('\n')
                                     if m.startswith(module_prefix)]

    script = []
    script.append("read_ilang <<rtlil\n{}\nrtlil".format(rtlil_text))

    if yosys_version >= (0, 9, 3468):
        # Yosys >=0.9+3468 (since commit 128522f1) emits the workaround for the `always @*`
        # initial scheduling issue on its own.
        script.append("delete w:$verilog_initial_trigger")

    for module in modules:
        script.append("show -nobg -colors 42 " + module)

    return yosys.run(["-q", "-"], "\n".join(script), src_loc_at=1 + src_loc_at)


def convert_fragment(*args, **kwargs):
    rtlil_text, name_map = rtlil.convert_fragment(*args, **kwargs)
    return _show_rtlil_text(rtlil_text, src_loc_at=1), name_map


def convert(*args, **kwargs):
    rtlil_text = rtlil.convert(*args, **kwargs)
    return _show_rtlil_text(rtlil_text, src_loc_at=1)
