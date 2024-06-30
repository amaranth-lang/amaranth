import re
from abc import abstractmethod

from ..hdl import *
from ..hdl._ir import RequirePosedge
from ..lib.cdc import ResetSynchronizer
from ..lib import io, wiring
from ..build import *


__all__ = ["XilinxPlatform"]


class InnerBuffer(wiring.Component):
    """A private component used to implement ``lib.io`` buffers.

    Works like ``lib.io.Buffer``, with the following differences:

    - ``port.invert`` is ignored (handling the inversion is the outer buffer's responsibility)
    - ``t`` is per-pin inverted output enable
    """
    def __init__(self, direction, port):
        self.direction = direction
        self.port = port
        members = {}
        if direction is not io.Direction.Output:
            members["i"] = wiring.In(len(port))
        if direction is not io.Direction.Input:
            members["o"] = wiring.Out(len(port))
            members["t"] = wiring.Out(len(port))
        super().__init__(wiring.Signature(members).flip())

    def elaborate(self, platform):
        m = Module()

        for bit in range(len(self.port)):
            name = f"buf{bit}"
            if isinstance(self.port, io.SingleEndedPort):
                if self.direction is io.Direction.Input:
                    m.submodules[name] = Instance("IBUF",
                        i_I=self.port.io[bit],
                        o_O=self.i[bit],
                    )
                elif self.direction is io.Direction.Output:
                    m.submodules[name] = Instance("OBUFT",
                        i_T=self.t[bit],
                        i_I=self.o[bit],
                        o_O=self.port.io[bit],
                    )
                elif self.direction is io.Direction.Bidir:
                    m.submodules[name] = Instance("IOBUF",
                        i_T=self.t[bit],
                        i_I=self.o[bit],
                        o_O=self.i[bit],
                        io_IO=self.port.io[bit],
                    )
                else:
                    assert False # :nocov:
            elif isinstance(self.port, io.DifferentialPort):
                if self.direction is io.Direction.Input:
                    m.submodules[name] = Instance("IBUFDS",
                        i_I=self.port.p[bit],
                        i_IB=self.port.n[bit],
                        o_O=self.i[bit],
                    )
                elif self.direction is io.Direction.Output:
                    m.submodules[name] = Instance("OBUFTDS",
                        i_T=self.t[bit],
                        i_I=self.o[bit],
                        o_O=self.port.p[bit],
                        o_OB=self.port.n[bit],
                    )
                elif self.direction is io.Direction.Bidir:
                    m.submodules[name] = Instance("IOBUFDS",
                        i_T=self.t[bit],
                        i_I=self.o[bit],
                        o_O=self.i[bit],
                        io_IO=self.port.p[bit],
                        io_IOB=self.port.n[bit],
                    )
                else:
                    assert False # :nocov:
            else:
                raise TypeError(f"Unknown port type {self.port!r}")

        return m


class IOBuffer(io.Buffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.d.comb += self.i.eq(buf.i ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.d.comb += buf.o.eq(self.o ^ inv_mask)
            m.d.comb += buf.t.eq(~self.oe.replicate(len(self.port)))

        return m


def _make_dff(m, prefix, domain, d, q, *, iob=False, inv_clk=False):
    for bit in range(len(q)):
        kwargs = {}
        if iob:
            kwargs["a_IOB"] = "TRUE"
        m.submodules[f"{prefix}_ff{bit}"] = Instance("FDCE",
            i_C=~ClockSignal(domain) if inv_clk else ClockSignal(domain),
            i_CE=Const(1),
            i_CLR=Const(0),
            i_D=d[bit],
            o_Q=q[bit],
            **kwargs,
        )


class FFBuffer(io.FFBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i_inv = Signal.like(self.i)
            _make_dff(m, "i", self.i_domain, buf.i, i_inv, iob=True)
            m.d.comb += self.i.eq(i_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o_inv = Signal.like(self.o)
            m.d.comb += o_inv.eq(self.o ^ inv_mask)
            _make_dff(m, "o", self.o_domain, o_inv, buf.o, iob=True)
            _make_dff(m, "oe", self.o_domain, ~self.oe.replicate(len(self.port)), buf.t, iob=True)

        return m


class DDRBufferVirtex2(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            # First-generation input DDR register: basically just two FFs with opposite
            # clocks. Add a register on both outputs, so that they enter fabric on
            # the same clock edge, adding one cycle of latency.
            i0_ff = Signal(len(self.port))
            i1_ff = Signal(len(self.port))
            _make_dff(m, "i0", self.i_domain, buf.i, i0_ff, iob=True)
            _make_dff(m, "i1", self.i_domain, buf.i, i1_ff, iob=True, inv_clk=True)
            _make_dff(m, "i0_p", self.i_domain, i0_ff, i0_inv)
            _make_dff(m, "i1_p", self.i_domain, i1_ff, i0_inv)
            m.d.comb += self.i[0].eq(i0_inv ^ inv_mask)
            m.d.comb += self.i[1].eq(i1_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o0_inv = Signal(len(self.port))
            o1_inv = Signal(len(self.port))
            o1_ff = Signal(len(self.port))
            m.d.comb += [
                o0_inv.eq(self.o[0] ^ inv_mask),
                o1_inv.eq(self.o[1] ^ inv_mask),
            ]
            _make_dff(m, "o1_p", self.o_domain, o1_inv, o1_ff)
            for bit in range(len(self.port)):
                m.submodules[f"o_ddr{bit}"] = Instance("FDDRCPE",
                    i_C0=ClockSignal(self.o_domain),
                    i_C1=~ClockSignal(self.o_domain),
                    i_CE=Const(1),
                    i_PRE=Const(0),
                    i_CLR=Const(0),
                    i_D0=o0_inv[bit],
                    i_D1=o1_ff[bit],
                    o_Q=buf.o[bit],
                )
            _make_dff(m, "oe", self.o_domain, ~self.oe.replicate(len(self.port)), buf.t, iob=True)

        return m


class DDRBufferSpartan3E(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        # On Spartan 3E/3A, the situation with DDR registers is messy: while the hardware
        # supports same-edge alignment, it does so by borrowing the resources of the other
        # pin in the differential pair (if any).  Since we cannot be sure if the other pin
        # is actually unused (or if the pin is even part of a differential pair in the first
        # place), we only use the hardware alignment feature in two cases:
        #
        # - differential inputs (since the other pin's input registers will be unused)
        # - true differential outputs (since they use only one pin's output registers,
        #   as opposed to pseudo-differential outputs that use both)
        TRUE_DIFF_S3EA = {
            "LVDS_33", "LVDS_25",
            "MINI_LVDS_33", "MINI_LVDS_25",
            "RSDS_33", "RSDS_25",
            "PPDS_33", "PPDS_25",
            "TMDS_33",
        }

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            if platform.family == "spartan6" or isinstance(self.port, io.DifferentialPort):
                # Second-generation input DDR register: hw realigns i1 to positive clock edge,
                # but also misaligns it with i0 input.  Re-register first input before it
                # enters fabric. This allows both inputs to enter fabric on the same clock
                # edge, and adds one cycle of latency.
                i0_ff = Signal(len(self.port))
                for bit in range(len(self.port)):
                    m.submodules[f"i_ddr{bit}"] = Instance("IDDR2",
                        p_DDR_ALIGNMENT="C0",
                        p_SRTYPE="ASYNC",
                        p_INIT_Q0=Const(0),
                        p_INIT_Q1=Const(0),
                        i_C0=ClockSignal(self.i_domain),
                        i_C1=~ClockSignal(self.i_domain),
                        i_CE=Const(1),
                        i_S=Const(0), i_R=Const(0),
                        i_D=buf.i[bit],
                        o_Q0=i0_ff[bit],
                        o_Q1=i1_inv[bit]
                    )
                _make_dff(m, "i0_p", self.i_domain, i0_ff, i0_inv)
            else:
                # No extra register available for hw alignment, use CLB registers.
                i0_ff = Signal(len(self.port))
                i1_ff = Signal(len(self.port))
                for bit in range(len(self.port)):
                    m.submodules[f"i_ddr{bit}"] = Instance("IDDR2",
                        p_DDR_ALIGNMENT="NONE",
                        p_SRTYPE="ASYNC",
                        p_INIT_Q0=Const(0),
                        p_INIT_Q1=Const(0),
                        i_C0=ClockSignal(self.i_domain),
                        i_C1=~ClockSignal(self.i_domain),
                        i_CE=Const(1),
                        i_S=Const(0), i_R=Const(0),
                        i_D=buf.i[bit],
                        o_Q0=i0_ff[bit],
                        o_Q1=i1_ff[bit]
                    )
                _make_dff(m, "i0_p", self.i_domain, i0_ff, i0_inv)
                _make_dff(m, "i1_p", self.i_domain, i1_ff, i0_inv)
            m.d.comb += self.i[0].eq(i0_inv ^ inv_mask)
            m.d.comb += self.i[1].eq(i1_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o0_inv = Signal(len(self.port))
            o1_inv = Signal(len(self.port))
            m.d.comb += [
                o0_inv.eq(self.o[0] ^ inv_mask),
                o1_inv.eq(self.o[1] ^ inv_mask),
            ]
            for bit in range(len(self.port)):
                if platform.family == "spartan3e":
                    merge_ff = False
                elif platform.family.startswith("spartan3a"):
                    if isinstance(self.port, io.DifferentialPort):
                        iostd = self.port.p.metadata[bit].attrs.get("IOSTANDARD", "LVDS_25")
                        merge_ff = iostd in TRUE_DIFF_S3EA
                    else:
                        merge_ff = False
                else:
                    merge_ff = True
                if merge_ff:
                    m.submodules[f"o_ddr{bit}"] = Instance("ODDR2",
                        p_DDR_ALIGNMENT="C0",
                        p_SRTYPE="ASYNC",
                        p_INIT=Const(0),
                        i_C0=ClockSignal(self.o_domain),
                        i_C1=~ClockSignal(self.o_domain),
                        i_CE=Const(1),
                        i_S=Const(0),
                        i_R=Const(0),
                        i_D0=o0_inv[bit],
                        i_D1=o1_inv[bit],
                        o_Q=buf.o[bit],
                    )
                else:
                    o1_ff = Signal()
                    _make_dff(m, f"o1_p{bit}_", self.o_domain, o1_inv[bit], o1_ff)
                    m.submodules[f"o_ddr{bit}"] = Instance("ODDR2",
                        p_DDR_ALIGNMENT="NONE",
                        p_SRTYPE="ASYNC",
                        p_INIT=Const(0),
                        i_C0=ClockSignal(self.o_domain),
                        i_C1=~ClockSignal(self.o_domain),
                        i_CE=Const(1),
                        i_S=Const(0),
                        i_R=Const(0),
                        i_D0=o0_inv[bit],
                        i_D1=o1_ff,
                        o_Q=buf.o[bit],
                    )
            if platform.family == "spartan6":
                for bit in range(len(self.port)):
                    m.submodules[f"oe_ddr{bit}"] = Instance("ODDR2",
                        p_DDR_ALIGNMENT="C0",
                        p_SRTYPE="ASYNC",
                        p_INIT=Const(0),
                        i_C0=ClockSignal(self.o_domain),
                        i_C1=~ClockSignal(self.o_domain),
                        i_CE=Const(1),
                        i_S=Const(0),
                        i_R=Const(0),
                        i_D0=~self.oe,
                        i_D1=~self.oe,
                        o_Q=buf.t[bit],
                    )
            else:
                _make_dff(m, "oe", self.o_domain, ~self.oe.replicate(len(self.port)), buf.t, iob=True)

        return m


class DDRBufferVirtex4(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            for bit in range(len(self.port)):
                m.submodules[f"i_ddr{bit}"] = Instance("IDDR",
                    p_DDR_CLK_EDGE="SAME_EDGE_PIPELINED",
                    p_SRTYPE="ASYNC",
                    p_INIT_Q1=Const(0),
                    p_INIT_Q2=Const(0),
                    i_C=ClockSignal(self.i_domain),
                    i_CE=Const(1),
                    i_S=Const(0), i_R=Const(0),
                    i_D=buf.i[bit],
                    o_Q1=i0_inv[bit],
                    o_Q2=i1_inv[bit]
                )
            m.d.comb += self.i[0].eq(i0_inv ^ inv_mask)
            m.d.comb += self.i[1].eq(i1_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o0_inv = Signal(len(self.port))
            o1_inv = Signal(len(self.port))
            m.d.comb += [
                o0_inv.eq(self.o[0] ^ inv_mask),
                o1_inv.eq(self.o[1] ^ inv_mask),
            ]
            for bit in range(len(self.port)):
                m.submodules[f"o_ddr{bit}"] = Instance("ODDR",
                    p_DDR_CLK_EDGE="SAME_EDGE",
                    p_SRTYPE="ASYNC",
                    p_INIT=Const(0),
                    i_C=ClockSignal(self.o_domain),
                    i_CE=Const(1),
                    i_S=Const(0),
                    i_R=Const(0),
                    i_D1=o0_inv[bit],
                    i_D2=o1_inv[bit],
                    o_Q=buf.o[bit],
                )
            _make_dff(m, "oe", self.o_domain, ~self.oe.replicate(len(self.port)), buf.t, iob=True)

        return m


class DDRBufferUltrascale(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            for bit in range(len(self.port)):
                m.submodules[f"i_ddr{bit}"] = Instance("IDDRE1",
                    p_DDR_CLK_EDGE="SAME_EDGE_PIPELINED",
                    p_IS_C_INVERTED=Const(0),
                    p_IS_CB_INVERTED=Const(1),
                    i_C=ClockSignal(self.i_domain),
                    i_CB=ClockSignal(self.i_domain),
                    i_R=Const(0),
                    i_D=buf.i[bit],
                    o_Q1=i0_inv[bit],
                    o_Q2=i1_inv[bit]
                )
            m.d.comb += self.i[0].eq(i0_inv ^ inv_mask)
            m.d.comb += self.i[1].eq(i1_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o0_inv = Signal(len(self.port))
            o1_inv = Signal(len(self.port))
            m.d.comb += [
                o0_inv.eq(self.o[0] ^ inv_mask),
                o1_inv.eq(self.o[1] ^ inv_mask),
            ]
            for bit in range(len(self.port)):
                m.submodules[f"o_ddr{bit}"] = Instance("ODDRE1",
                    p_SRVAL=Const(0),
                    i_C=ClockSignal(self.o_domain),
                    i_SR=Const(0),
                    i_D1=o0_inv[bit],
                    i_D2=o1_inv[bit],
                    o_Q=buf.o[bit],
                )
            _make_dff(m, "oe", self.o_domain, ~self.oe.replicate(len(self.port)), buf.t, iob=True)

        return m


class XilinxPlatform(TemplatedPlatform):
    """
    .. rubric:: Vivado toolchain

    Required tools:
        * ``vivado``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_VIVADO``, if present.

    Available overrides:
        * ``script_after_read``: inserts commands after ``read_xdc`` in Tcl script.
        * ``synth_design_opts``: sets options for ``synth_design``.
        * ``script_after_synth``: inserts commands after ``synth_design`` in Tcl script.
        * ``script_after_place``: inserts commands after ``place_design`` in Tcl script.
        * ``script_after_route``: inserts commands after ``route_design`` in Tcl script.
        * ``script_before_bitstream``: inserts commands before ``write_bitstream`` in Tcl script.
        * ``script_after_bitstream``: inserts commands after ``write_bitstream`` in Tcl script.
        * ``add_constraints``: inserts commands in XDC file.
        * ``vivado_opts``: adds extra options for ``vivado``.

    Build products:
        * ``{{name}}.log``: Vivado log.
        * ``{{name}}_timing_synth.rpt``: Vivado report.
        * ``{{name}}_utilization_hierarchical_synth.rpt``: Vivado report.
        * ``{{name}}_utilization_synth.rpt``: Vivado report.
        * ``{{name}}_utilization_hierarchical_place.rpt``: Vivado report.
        * ``{{name}}_utilization_place.rpt``: Vivado report.
        * ``{{name}}_io.rpt``: Vivado report.
        * ``{{name}}_control_sets.rpt``: Vivado report.
        * ``{{name}}_clock_utilization.rpt``:  Vivado report.
        * ``{{name}}_route_status.rpt``: Vivado report.
        * ``{{name}}_drc.rpt``: Vivado report.
        * ``{{name}}_methodology.rpt``: Vivado report.
        * ``{{name}}_timing.rpt``: Vivado report.
        * ``{{name}}_power.rpt``: Vivado report.
        * ``{{name}}_route.dcp``: Vivado design checkpoint.
        * ``{{name}}.bit``: binary bitstream with metadata.
        * ``{{name}}.bin``: binary bitstream.

    .. rubric:: ISE toolchain

    Required tools:
        * ``xst``
        * ``ngdbuild``
        * ``map``
        * ``par``
        * ``bitgen``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_ISE``, if present.

    Available overrides:
        * ``script_after_run``: inserts commands after ``run`` in XST script.
        * ``add_constraints``: inserts commands in UCF file.
        * ``xst_opts``: adds extra options for ``xst``.
        * ``ngdbuild_opts``: adds extra options for ``ngdbuild``.
        * ``map_opts``: adds extra options for ``map``.
        * ``par_opts``: adds extra options for ``par``.
        * ``bitgen_opts``: adds extra and overrides default options for ``bitgen``;
          default options: ``-g Compress``.

    Build products:
        * ``{{name}}.srp``: synthesis report.
        * ``{{name}}.ngc``: synthesized RTL.
        * ``{{name}}.bld``: NGDBuild log.
        * ``{{name}}.ngd``: design database.
        * ``{{name}}_map.map``: MAP log.
        * ``{{name}}_map.mrp``: mapping report.
        * ``{{name}}_map.ncd``: mapped netlist.
        * ``{{name}}.pcf``: physical constraints.
        * ``{{name}}_par.par``: PAR log.
        * ``{{name}}_par_pad.txt``: I/O usage report.
        * ``{{name}}_par.ncd``: place and routed netlist.
        * ``{{name}}.drc``: DRC report.
        * ``{{name}}.bgn``: BitGen log.
        * ``{{name}}.bit``: binary bitstream with metadata.
        * ``{{name}}.bin``: raw binary bitstream.

    .. rubric:: Symbiflow toolchain

    Required tools:
        * ``symbiflow_synth``
        * ``symbiflow_pack``
        * ``symbiflow_place``
        * ``symbiflow_route``
        * ``symbiflow_write_fasm``
        * ``symbiflow_write_bitstream``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_SYMBIFLOW``, if present.

    Available overrides:
        * ``add_constraints``: inserts commands in XDC file.

    .. rubric:: Xray toolchain

    Required tools:
        * ``yosys``
        * ``nextpnr-xilinx``
        * ``fasm2frames``
        * ``xc7frames2bit``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_XRAY``, if present.
    """

    toolchain = None # selected when creating platform

    device  = property(abstractmethod(lambda: None))
    package = property(abstractmethod(lambda: None))
    speed   = property(abstractmethod(lambda: None))

    @property
    def _part(self):
        if self.family in {"ultrascale", "ultrascaleplus"}:
            return f"{self.device}-{self.package}-{self.speed}"
        else:
            return f"{self.device}{self.package}-{self.speed}"

    @property
    def vendor_toolchain(self):
        return self.toolchain in ["Vivado", "ISE"]

    # Vivado templates

    _vivado_required_tools = ["vivado"]
    _vivado_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
            #!/bin/sh
            # {{autogenerated}}
            set -e{{verbose("x")}}
            if [ -z "$BASH" ] ; then exec /bin/bash "$0" "$@"; fi
            [ -n "${{platform._toolchain_env_var}}" ] && . "${{platform._toolchain_env_var}}"
            {{emit_commands("sh")}}
        """,
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_verilog()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.tcl": r"""
            # {{autogenerated}}
            create_project -force -name {{name}} -part {{platform._part}}
            {% for file in platform.iter_files(".v", ".sv", ".vhd", ".vhdl") -%}
                add_files {{file|tcl_quote}}
            {% endfor %}
            add_files {{name}}.v
            read_xdc {{name}}.xdc
            {% for file in platform.iter_files(".xdc") -%}
                read_xdc {{file|tcl_quote}}
            {% endfor %}
            {{get_override("script_after_read")|default("# (script_after_read placeholder)")}}
            synth_design -top {{name}} {{get_override("synth_design_opts")}}
            foreach cell [get_cells -quiet -hier -filter {amaranth.vivado.false_path == "TRUE"}] {
                set_false_path -to $cell
            }
            foreach pin [get_pins -of \
                             [get_cells -quiet -hier -filter {amaranth.vivado.false_path_pre == "TRUE"}] \
                             -filter {REF_PIN_NAME == PRE}] {
                set_false_path -to $pin
            }
            foreach cell [get_cells -quiet -hier -filter {amaranth.vivado.max_delay != ""}] {
                set clock [get_clocks -of_objects \
                    [all_fanin -flat -startpoints_only [get_pin $cell/D]]]
                if {[llength $clock] != 0} {
                    set_max_delay -datapath_only -from $clock \
                        -to [get_cells $cell] [get_property amaranth.vivado.max_delay $cell]
                }
            }
            foreach cell [get_cells -quiet -hier -filter {amaranth.vivado.max_delay_pre != ""}] {
                set_max_delay \
                    -to [get_pins -of [get_cells $cell] -filter {REF_PIN_NAME == PRE}] \
                    [get_property amaranth.vivado.max_delay_pre $cell]
            }
            {{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
            report_timing_summary -file {{name}}_timing_synth.rpt
            report_utilization -hierarchical -file {{name}}_utilization_hierarchical_synth.rpt
            report_utilization -file {{name}}_utilization_synth.rpt
            opt_design
            place_design
            {{get_override("script_after_place")|default("# (script_after_place placeholder)")}}
            report_utilization -hierarchical -file {{name}}_utilization_hierarchical_place.rpt
            report_utilization -file {{name}}_utilization_place.rpt
            report_io -file {{name}}_io.rpt
            report_control_sets -verbose -file {{name}}_control_sets.rpt
            report_clock_utilization -file {{name}}_clock_utilization.rpt
            route_design
            {{get_override("script_after_route")|default("# (script_after_route placeholder)")}}
            phys_opt_design
            report_timing_summary -no_header -no_detailed_paths
            write_checkpoint -force {{name}}_route.dcp
            report_route_status -file {{name}}_route_status.rpt
            report_drc -file {{name}}_drc.rpt
            report_methodology -file {{name}}_methodology.rpt
            report_timing_summary -datasheet -max_paths 10 -file {{name}}_timing.rpt
            report_power -file {{name}}_power.rpt
            {{get_override("script_before_bitstream")|default("# (script_before_bitstream placeholder)")}}
            write_bitstream -force -bin_file {{name}}.bit
            {{get_override("script_after_bitstream")|default("# (script_after_bitstream placeholder)")}}
            quit
        """,
        "{{name}}.xdc": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                set_property LOC {{pin_name}} [get_ports {{port_name|tcl_quote}}]
                {% for attr_name, attr_value in attrs.items() -%}
                    set_property {{attr_name}} {{attr_value|tcl_quote}} [get_ports {{port_name|tcl_quote}}]
                {% endfor %}
            {% endfor %}
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                create_clock -name {{signal.name|ascii_escape}} -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("/")|tcl_quote}}]
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                create_clock -name {{port.name|ascii_escape}} -period {{1000000000/frequency}} [get_nets {{port|hierarchy("/")|tcl_quote}}]
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """
    }
    _vivado_command_templates = [
        r"""
        {{invoke_tool("vivado")}}
            {{verbose("-verbose")}}
            {{get_override("vivado_opts")|options}}
            -mode batch
            -log {{name}}.log
            -source {{name}}.tcl
        """
    ]

    # ISE toolchain

    _ise_required_tools = [
        "xst",
        "ngdbuild",
        "map",
        "par",
        "bitgen",
    ]
    _ise_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
            # {{autogenerated}}
            set -e{{verbose("x")}}
            if [ -z "$BASH" ] ; then exec /bin/bash "$0" "$@"; fi
            [ -n "${{platform._toolchain_env_var}}" ] && . "${{platform._toolchain_env_var}}"
            {{emit_commands("sh")}}
        """,
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_verilog()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.prj": r"""
            # {{autogenerated}}
            {% for file in platform.iter_files(".vhd", ".vhdl") -%}
                vhdl work {{file}}
            {% endfor %}
            {% for file in platform.iter_files(".v") -%}
                verilog work {{file}}
            {% endfor %}
            verilog work {{name}}.v
        """,
        "{{name}}.xst": r"""
            # {{autogenerated}}
            run
            -ifn {{name}}.prj
            -ofn {{name}}.ngc
            -top {{name}}
            -use_new_parser yes
            -p {{platform.device}}{{platform.package}}-{{platform.speed}}
            {{get_override("script_after_run")|default("# (script_after_run placeholder)")}}
        """,
        "{{name}}.ucf": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                {% set port_name = port_name|replace("[", "<")|replace("]", ">") -%}
                NET "{{port_name}}" LOC={{pin_name}};
                {% for attr_name, attr_value in attrs.items() -%}
                    NET "{{port_name}}" {{attr_name}}={{attr_value}};
                {% endfor %}
            {% endfor %}
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                NET "{{signal|hierarchy("/")}}" TNM_NET="PRD{{signal|hierarchy("/")}}";
                TIMESPEC "TS{{signal|hierarchy("__")}}"=PERIOD "PRD{{signal|hierarchy("/")}}" {{1000000000/frequency}} ns HIGH 50%;
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                NET "{{port|hierarchy("/")}}" TNM_NET="PRD{{port|hierarchy("/")}}";
                TIMESPEC "TS{{port|hierarchy("__")}}"=PERIOD "PRD{{port|hierarchy("/")}}" {{1000000000/frequency}} ns HIGH 50%;
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """
    }
    _ise_command_templates = [
        r"""
        {{invoke_tool("xst")}}
            {{get_override("xst_opts")|options}}
            -ifn {{name}}.xst
        """,
        r"""
        {{invoke_tool("ngdbuild")}}
            {{quiet("-quiet")}}
            {{verbose("-verbose")}}
            {{get_override("ngdbuild_opts")|options}}
            -uc {{name}}.ucf
            {{name}}.ngc
        """,
        r"""
        {{invoke_tool("map")}}
            {{verbose("-detail")}}
            {{get_override("map_opts")|default([])|options}}
            -w
            -o {{name}}_map.ncd
            {{name}}.ngd
            {{name}}.pcf
        """,
        r"""
        {{invoke_tool("par")}}
            {{get_override("par_opts")|default([])|options}}
            -w
            {{name}}_map.ncd
            {{name}}_par.ncd
            {{name}}.pcf
        """,
        r"""
        {{invoke_tool("bitgen")}}
            {{get_override("bitgen_opts")|default(["-g Compress"])|options}}
            -w
            -g Binary:Yes
            {{name}}_par.ncd
            {{name}}.bit
        """
    ]

    # Symbiflow templates

    # symbiflow does not distinguish between speed grades
    # TODO: join with _xray_part
    @property
    def _symbiflow_part(self):
        # drop the trailing speed grade letter(s), if any
        part = re.sub(r"[^\d]+$", "", self._part)
        # drop temp/speed grade letters after family name, if any
        part = re.sub(r"(.{4}\d+t)[il]", r"\1", part)
        return part

    # bitstream device name according to prjxray-db path
    # TODO: join with _xray_family
    @property
    def _symbiflow_bitstream_device(self):
        if self._part.startswith("xc7a"):
            return "artix7"
        elif self._part.startswith("xc7k"):
            return "kintex7"
        elif self._part.startswith("xc7z"):
            return "zynq7"
        elif self._part.startswith("xc7s"):
            return "spartan7"
        else:
            print(f"Unknown bitstream device for part {self._part}")
            raise ValueError

    # device naming according to part_db.yml of f4pga project
    @property
    def _symbiflow_device(self):
        if self._part.startswith("xc7a35") or self._part.startswith("xc7a50"):
            return "xc7a50t_test"
        elif self._part.startswith("xc7a100"):
            return "xc7a100t_test"
        elif self._part.startswith("xc7a200"):
            return "xc7a200t_test"
        else:
            print(f"Unknown symbiflow device for part {self._part}")
            raise ValueError


    _symbiflow_required_tools = [
        "symbiflow_synth",
        "symbiflow_pack",
        "symbiflow_place",
        "symbiflow_route",
        "symbiflow_write_fasm",
        "symbiflow_write_bitstream"
    ]
    _symbiflow_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_verilog()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.pcf": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                set_io {{port_name}} {{pin_name}}
            {% endfor %}
        """,
        "{{name}}.xdc": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                {% for attr_name, attr_value in attrs.items() -%}
                    set_property {{attr_name}} {{attr_value}} [get_ports {{port_name|tcl_quote}} }]
                {% endfor %}
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """,
        "{{name}}.sdc": r"""
            # {{autogenerated}}
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                create_clock -period {{1000000000/frequency}} {{signal.name|ascii_escape}}
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                create_clock -period {{1000000000/frequency}} {{port.name|ascii_escape}}
            {% endfor %}
        """
    }
    _symbiflow_command_templates = [
        r"""
        {{invoke_tool("symbiflow_synth")}}
            -t {{name}}
            -v {% for file in platform.iter_files(".v", ".sv", ".vhd", ".vhdl") -%} {{file}} {% endfor %} {{name}}.v
            -p {{platform._symbiflow_part}}
            -d {{platform._symbiflow_bitstream_device}}
            -x {{name}}.xdc
        """,
        r"""
        {{invoke_tool("symbiflow_pack")}}
            -e {{name}}.eblif
            -d {{platform._symbiflow_device}}
            -s {{name}}.sdc
        """,
        r"""
        {{invoke_tool("symbiflow_place")}}
            -e {{name}}.eblif
            -p {{name}}.pcf
            -n {{name}}.net
            -P {{platform._symbiflow_part}}
            -d {{platform._symbiflow_device}}
            -s {{name}}.sdc
        """,
        r"""
        {{invoke_tool("symbiflow_route")}}
            -e {{name}}.eblif
            -P {{platform._symbiflow_part}}
            -d {{platform._symbiflow_device}}
            -s {{name}}.sdc
            -s {{name}}.sdc
        """,
        r"""
        {{invoke_tool("symbiflow_write_fasm")}}
            -e {{name}}.eblif
            -P {{platform._symbiflow_part}}
            -d {{platform._symbiflow_device}}
        """,
        r"""
        {{invoke_tool("symbiflow_write_bitstream")}}
            -f {{name}}.fasm
            -p {{platform._symbiflow_part}}
            -d {{platform._symbiflow_bitstream_device}}
            -b {{name}}.bit
        """
    ]

    # Yosys NextPNR prjxray templates

    @property
    def _xray_part(self):
        return {
            "xc7a35ticsg324-1L":  "xc7a35tcsg324-1",  # Arty-A7 35t
            "xc7a100ticsg324-1L": "xc7a100tcsg324-1", # Arty-A7 100t
        }.get(self._part, self._part)

    @property
    def _xray_device(self):
        return {
            "xc7a35ti":  "xc7a35t",
            "xc7a100ti": "xc7a100t",
        }.get(self.device, self.device)

    @property
    def _xray_family(self):
        return {
            "xc7a": "artix7",
            "xc7z": "zynq7",
        }[self.device[:4]]

    _xray_required_tools = [
        "yosys",
        "nextpnr-xilinx",
        "fasm2frames",
        "xc7frames2bit"
    ]
    _xray_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
            # {{autogenerated}}
            set -e{{verbose("x")}}
            [ -n "${{platform._toolchain_env_var}}" ] && . "${{platform._toolchain_env_var}}"
            : ${DB_DIR:=/usr/share/nextpnr/prjxray-db}
            : ${CHIPDB_DIR:=/usr/share/nextpnr/xilinx-chipdb}
            {{emit_commands("sh")}}
        """,
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_verilog()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.xdc": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                {% for attr_name, attr_value in attrs.items() -%}
                    set_property {{attr_name}} {{attr_value}} [get_ports {{port_name|tcl_quote}}]
                    set_property LOC {{pin_name}} [get_ports {{port_name|tcl_quote}}]
                {% endfor %}
            {% endfor %}
        """,
    }
    _xray_command_templates = [
        r"""
        {{invoke_tool("yosys")}}
            -p "synth_xilinx -flatten -abc9 -nobram -arch xc7 -top {{name}}; write_json {{name}}.json"
            {% for file in platform.iter_files(".v", ".sv", ".vhd", ".vhdl") -%} {{file}} {% endfor %}
            {{name}}.v
        """,
        r"""
        {{invoke_tool("nextpnr-xilinx")}}
            --chipdb $CHIPDB_DIR/{{platform._xray_device}}.bin
            --xdc {{name}}.xdc
            --json {{name}}.json
            --write {{name}}_routed.json
            --fasm {{name}}.fasm
        """,
        r"""
        {{invoke_tool("fasm2frames")}}
            --part {{platform._xray_part}}
            --db-root $DB_DIR/{{platform._xray_family}} {{name}}.fasm > {{name}}.frames
        """,
        r"""
        {{invoke_tool("xc7frames2bit")}}
            --part_file $DB_DIR/{{platform._xray_family}}/{{platform._xray_part}}/part.yaml
            --part_name {{platform._xray_part}}
            --frm_file {{name}}.frames
            --output_file {{name}}.bit
        """,
    ]

    # Common logic

    def __init__(self, *, toolchain=None):
        super().__init__()

        # Determine device family.
        device = self.device.lower()
        # Remove the prefix.
        if device.startswith("xc"):
            device = device[2:]
        elif device.startswith("xa"):
            device = device[2:]
        elif device.startswith("xqr"):
            device = device[3:]
        elif device.startswith("xq"):
            device = device[2:]
        else:
            raise ValueError(f"Device '{self.device}' is not recognized")
        # Do actual name matching.
        if device.startswith("2vp"):
            self.family = "virtex2p"
        elif device.startswith("2v"):
            self.family = "virtex2"
        elif device.startswith("3sd"):
            self.family = "spartan3adsp"
        elif device.startswith("3s"):
            if device.endswith("a"):
                self.family = "spartan3a"
            elif device.endswith("e"):
                self.family = "spartan3e"
            else:
                self.family = "spartan3"
        elif device.startswith("4v"):
            self.family = "virtex4"
        elif device.startswith("5v"):
            self.family = "virtex5"
        elif device.startswith("6v"):
            self.family = "virtex6"
        elif device.startswith("6s"):
            self.family = "spartan6"
        elif device.startswith("7"):
            self.family = "series7"
        elif device.startswith(("vu", "ku")):
            if device.endswith("p"):
                self.family = "ultrascaleplus"
            else:
                self.family = "ultrascale"
        elif device.startswith(("zu", "u", "k26", "au")):
            self.family = "ultrascaleplus"
        elif device.startswith(("v", "2s")):
            # Match last to avoid conflict with ultrascale.
            # Yes, Spartan 2 is the same thing as Virtex.
            if device.endswith("e"):
                self.family = "virtexe"
            else:
                self.family = "virtex"


        ISE_FAMILIES = {
                "virtex", "virtexe",
                "virtex2", "virtex2p",
                "spartan3", "spartan3e", "spartan3a", "spartan3adsp",
                "virtex4",
                "virtex5",
                "virtex6",
                "spartan6",
        }
        if toolchain is None:
            if self.family in ISE_FAMILIES:
                toolchain = "ISE"
            else:
                toolchain = "Vivado"

        assert toolchain in ("Vivado", "ISE", "Symbiflow", "Xray")
        if toolchain == "Vivado":
            if self.family in ISE_FAMILIES:
                raise ValueError(f"Family '{self.family}' is not supported by the Vivado toolchain, please use ISE instead")
        elif toolchain == "ISE":
            if self.family not in ISE_FAMILIES and self.family != "series7":
                raise ValueError(f"Family '{self.family}' is not supported by the ISE toolchain, please use Vivado instead")
        elif toolchain == "Symbiflow":
            if self.family != "series7":
                raise ValueError(f"Family '{self.family}' is not supported by the Symbiflow toolchain")
        elif toolchain == "Xray":
            if self.family != "series7":
                raise ValueError(f"Family '{self.family}' is not supported by the yosys nextpnr toolchain")

        self.toolchain = toolchain

    @property
    def required_tools(self):
        if self.toolchain == "Vivado":
            return self._vivado_required_tools
        if self.toolchain == "ISE":
            return self._ise_required_tools
        if self.toolchain == "Symbiflow":
            return self._symbiflow_required_tools
        if self.toolchain == "Xray":
            return self._xray_required_tools
        assert False

    @property
    def file_templates(self):
        if self.toolchain == "Vivado":
            return self._vivado_file_templates
        if self.toolchain == "ISE":
            return self._ise_file_templates
        if self.toolchain == "Symbiflow":
            return self._symbiflow_file_templates
        if self.toolchain == "Xray":
            return self._xray_file_templates
        assert False

    @property
    def command_templates(self):
        if self.toolchain == "Vivado":
            return self._vivado_command_templates
        if self.toolchain == "ISE":
            return self._ise_command_templates
        if self.toolchain == "Symbiflow":
            return self._symbiflow_command_templates
        if self.toolchain == "Xray":
            return self._xray_command_templates
        assert False

    def create_missing_domain(self, name):
        # Xilinx devices have a global write enable (GWE) signal that asserted during configuration
        # and deasserted once it ends. Because it is an asynchronous signal (GWE is driven by logic
        # synchronous to configuration clock, which is not used by most designs), even though it is
        # a low-skew global network, its deassertion may violate a setup/hold constraint with
        # relation to a user clock. The recommended solution is to use a BUFGCE driven by the EOS
        # signal (if available). For details, see:
        #   * https://www.xilinx.com/support/answers/44174.html
        #   * https://www.xilinx.com/support/documentation/white_papers/wp272.pdf

        STARTUP_PRIMITIVE = {
                "spartan6": "STARTUP_SPARTAN6",
                "virtex4": "STARTUP_VIRTEX4",
                "virtex5": "STARTUP_VIRTEX5",
                "virtex6": "STARTUP_VIRTEX6",
                "series7": "STARTUPE2",
                "ultrascale": "STARTUPE3",
                "ultrascaleplus": "STARTUPE3",
        }

        if self.family not in STARTUP_PRIMITIVE or not self.vendor_toolchain:
            # Spartan 3 and before lacks a STARTUP primitive with EOS output; use a simple ResetSynchronizer
            # in that case, as is the default.
            # Symbiflow does not support the STARTUPE2 primitive.
            return super().create_missing_domain(name)

        if name == "sync" and self.default_clk is not None:
            m = Module()

            clk_io = self.request(self.default_clk, dir="-")
            m.submodules.clk_buf = clk_buf = io.Buffer("i", clk_io)
            clk_i = clk_buf.i
            if self.default_rst is not None:
                rst_io = self.request(self.default_rst, dir="-")
                m.submodules.rst_buf = rst_buf = io.Buffer("i", rst_io)
                rst_i = rst_buf.i

            ready = Signal()
            m.submodules += Instance(STARTUP_PRIMITIVE[self.family], o_EOS=ready)
            m.domains += ClockDomain("sync", reset_less=self.default_rst is None)
            if self.toolchain != "Vivado":
                m.submodules += Instance("BUFGCE", i_CE=ready, i_I=clk_i, o_O=ClockSignal("sync"))
            elif self.family == "series7":
                # Actually use BUFGCTRL configured as BUFGCE, since using BUFGCE causes
                # sim/synth mismatches with Vivado 2019.2, and the suggested workaround
                # (SIM_DEVICE parameter) breaks Vivado 2017.4.
                m.submodules += Instance("BUFGCTRL",
                    p_SIM_DEVICE="7SERIES",
                    i_I0=clk_i,   i_S0=C(1, 1), i_CE0=ready,   i_IGNORE0=C(0, 1),
                    i_I1=C(1, 1), i_S1=C(0, 1), i_CE1=C(0, 1), i_IGNORE1=C(1, 1),
                    o_O=ClockSignal("sync")
                )
            else:
                m.submodules += Instance("BUFGCE",
                    p_SIM_DEVICE="ULTRASCALE",
                    i_CE=ready,
                    i_I=clk_i,
                    o_O=ClockSignal("sync")
                )
            if self.default_rst is not None:
                m.submodules.reset_sync = ResetSynchronizer(rst_i, domain="sync")
            return m

    def add_clock_constraint(self, clock, frequency):
        super().add_clock_constraint(clock, frequency)
        if not isinstance(clock, IOPort):
            clock.attrs["keep"] = "TRUE"

    def get_io_buffer(self, buffer):
        if isinstance(buffer, io.Buffer):
            result = IOBuffer(buffer.direction, buffer.port)
        elif isinstance(buffer, io.FFBuffer):
            result = FFBuffer(buffer.direction, buffer.port,
                              i_domain=buffer.i_domain,
                              o_domain=buffer.o_domain)
        elif isinstance(buffer, io.DDRBuffer):
            if self.family in ("virtex2", "virtex2p", "spartan3"):
                result = DDRBufferVirtex2(buffer.direction, buffer.port,
                                          i_domain=buffer.i_domain,
                                          o_domain=buffer.o_domain)
            elif self.family in ("spartan3e", "spartan3a", "spartan3adsp", "spartan6"):
                result = DDRBufferSpartan3E(buffer.direction, buffer.port,
                                            i_domain=buffer.i_domain,
                                            o_domain=buffer.o_domain)
            elif self.family in ("virtex4", "virtex5", "virtex6", "series7"):
                result = DDRBufferVirtex4(buffer.direction, buffer.port,
                                          i_domain=buffer.i_domain,
                                          o_domain=buffer.o_domain)
            elif self.family in ("ultrascale", "ultrascaleplus"):
                result = DDRBufferUltrascale(buffer.direction, buffer.port,
                                             i_domain=buffer.i_domain,
                                             o_domain=buffer.o_domain)
            else:
                raise TypeError(f"Family {self.family} doesn't implement DDR buffers")
        else:
            raise TypeError(f"Unsupported buffer type {buffer!r}") # :nocov:
        if buffer.direction is not io.Direction.Output:
            result.i = buffer.i
        if buffer.direction is not io.Direction.Input:
            result.o = buffer.o
            result.oe = buffer.oe
        return result

    # The synchronizer implementations below apply two separate but related timing constraints.
    #
    # First, the ASYNC_REG attribute prevents inference of shift registers from synchronizer FFs,
    # and constraints the FFs to be placed as close as possible, ideally in one CLB. This attribute
    # only affects the synchronizer FFs themselves.
    #
    # Second, for Vivado only, the amaranth.vivado.false_path or amaranth.vivado.max_delay attribute
    # affects the path into the synchronizer. If maximum input delay is specified, a datapath-only
    # maximum delay constraint is applied, limiting routing delay (and therefore skew) at
    # the synchronizer input.  Otherwise, a false path constraint is used to omit the input path
    # from the timing analysis.

    def get_ff_sync(self, ff_sync):
        m = Module()
        flops = [Signal(ff_sync.i.shape(), name=f"stage{index}",
                        init=ff_sync._init, reset_less=ff_sync._reset_less,
                        attrs={"ASYNC_REG": "TRUE"})
                 for index in range(ff_sync._stages)]
        if self.toolchain == "Vivado":
            if ff_sync._max_input_delay is None:
                flops[0].attrs["amaranth.vivado.false_path"] = "TRUE"
            else:
                flops[0].attrs["amaranth.vivado.max_delay"] = str(ff_sync._max_input_delay * 1e9)
        elif ff_sync._max_input_delay is not None:
            raise NotImplementedError("Platform '{}' does not support constraining input delay "
                                      "for FFSynchronizer"
                                      .format(type(self).__qualname__))
        for i, o in zip((ff_sync.i, *flops), flops):
            m.d[ff_sync._o_domain] += o.eq(i)
        m.d.comb += ff_sync.o.eq(flops[-1])
        return m


    def get_async_ff_sync(self, async_ff_sync):
        m = Module()
        m.submodules += RequirePosedge(async_ff_sync._o_domain)
        m.domains += ClockDomain("async_ff", async_reset=True, local=True)
        # Instantiate a chain of async_ff_sync._stages FDPEs with all
        # their PRE pins connected to either async_ff_sync.i or
        # ~async_ff_sync.i. The D of the first FDPE in the chain is
        # connected to GND.
        flops_q = Signal(async_ff_sync._stages, reset_less=True)
        flops_d = Signal(async_ff_sync._stages, reset_less=True)
        flops_pre = Signal(reset_less=True)
        for i in range(async_ff_sync._stages):
            flop = Instance("FDPE", p_INIT=Const(1), o_Q=flops_q[i],
                            i_C=ClockSignal(async_ff_sync._o_domain),
                            i_CE=Const(1), i_PRE=flops_pre, i_D=flops_d[i],
                            a_ASYNC_REG="TRUE")
            m.submodules[f"stage{i}"] = flop
            if self.toolchain == "Vivado":
                if async_ff_sync._max_input_delay is None:
                    # This attribute should be used with a constraint of the form
                    #
                    # set_false_path -to [ \
                    #   get_pins -of [get_cells -hier -filter {amaranth.vivado.false_path_pre == "TRUE"}] \
                    #     -filter { REF_PIN_NAME == PRE } ]
                    #
                    flop.attrs["amaranth.vivado.false_path_pre"] = "TRUE"
                else:
                    # This attributed should be used with a constraint of the form
                    #
                    # set_max_delay -to [ \
                    #   get_pins -of [get_cells -hier -filter {amaranth.vivado.max_delay_pre == "3.0"}] \
                    #     -filter { REF_PIN_NAME == PRE } ] \
                    #   3.0
                    #
                    # A different constraint must be added for each different _max_input_delay value
                    # used. The same value should be used in the second parameter of set_max_delay
                    # and in the -filter.
                    flop.attrs["amaranth.vivado.max_delay_pre"] = str(async_ff_sync._max_input_delay * 1e9)
            elif async_ff_sync._max_input_delay is not None:
                raise NotImplementedError("Platform '{}' does not support constraining input delay "
                                          "for AsyncFFSynchronizer"
                                          .format(type(self).__qualname__))

        for i, o in zip((0, *flops_q), flops_d):
            m.d.comb += o.eq(i)

        if async_ff_sync._edge == "pos":
            m.d.comb += flops_pre.eq(async_ff_sync.i)
        else:
            m.d.comb += flops_pre.eq(~async_ff_sync.i)

        m.d.comb += async_ff_sync.o.eq(flops_q[-1])

        return m
