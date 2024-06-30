from abc import abstractmethod

from ..hdl import *
from ..hdl._ir import RequirePosedge
from ..lib import io, wiring
from ..build import *


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

        if isinstance(self.port, io.SingleEndedPort):
            io_port = self.port.io
        elif isinstance(self.port, io.DifferentialPort):
            io_port = self.port.p
        else:
            raise TypeError(f"Unknown port type {self.port!r}")

        for bit in range(len(self.port)):
            name = f"buf{bit}"
            if self.direction is io.Direction.Input:
                m.submodules[name] = Instance("IB",
                    i_I=io_port[bit],
                    o_O=self.i[bit],
                )
            elif self.direction is io.Direction.Output:
                m.submodules[name] = Instance("OBZ",
                    i_T=self.t[bit],
                    i_I=self.o[bit],
                    o_O=io_port[bit],
                )
            elif self.direction is io.Direction.Bidir:
                m.submodules[name] = Instance("BB",
                    i_T=self.t[bit],
                    i_I=self.o[bit],
                    o_O=self.i[bit],
                    io_B=io_port[bit],
                )
            else:
                assert False # :nocov:

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


def _make_oereg_ecp5_machxo2(m, domain, oe, q):
    for bit in range(len(q)):
        m.submodules[f"oe_ff{bit}"] = Instance("OFS1P3DX",
            i_SCLK=ClockSignal(domain),
            i_SP=Const(1),
            i_CD=Const(0),
            i_D=oe,
            o_Q=q[bit],
        )


def _make_oereg_nexus(m, domain, oe, q):
    for bit in range(len(q)):
        m.submodules[f"oe_ff{bit}"] = Instance("OFD1P3DX",
            i_CK=ClockSignal(domain),
            i_SP=Const(1),
            i_CD=Const(0),
            i_D=oe,
            o_Q=q[bit],
        )


class FFBufferECP5(io.FFBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i_inv = Signal.like(self.i)
            for bit in range(len(self.port)):
                m.submodules[f"i_ff{bit}"] = Instance("IFS1P3DX",
                    i_SCLK=ClockSignal(self.i_domain),
                    i_SP=Const(1),
                    i_CD=Const(0),
                    i_D=buf.i[bit],
                    o_Q=i_inv[bit],
                )
            m.d.comb += self.i.eq(i_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o_inv = Signal.like(self.o)
            m.d.comb += o_inv.eq(self.o ^ inv_mask)
            for bit in range(len(self.port)):
                m.submodules[f"o_ff{bit}"] = Instance("OFS1P3DX",
                    i_SCLK=ClockSignal(self.o_domain),
                    i_SP=Const(1),
                    i_CD=Const(0),
                    i_D=o_inv[bit],
                    o_Q=buf.o[bit],
                )
            _make_oereg_ecp5_machxo2(m, self.o_domain, ~self.oe, buf.t)

        return m


class FFBufferNexus(io.FFBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i_inv = Signal.like(self.i)
            for bit in range(len(self.port)):
                m.submodules[f"i_ff{bit}"] = Instance("IFD1P3DX",
                    i_CK=ClockSignal(self.i_domain),
                    i_SP=Const(1),
                    i_CD=Const(0),
                    i_D=buf.i[bit],
                    o_Q=i_inv[bit],
                )
            m.d.comb += self.i.eq(i_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o_inv = Signal.like(self.o)
            m.d.comb += o_inv.eq(self.o ^ inv_mask)
            for bit in range(len(self.port)):
                m.submodules[f"o_ff{bit}"] = Instance("OFD1P3DX",
                    i_CK=ClockSignal(self.o_domain),
                    i_SP=Const(1),
                    i_CD=Const(0),
                    i_D=o_inv[bit],
                    o_Q=buf.o[bit],
                )
            _make_oereg_nexus(m, self.o_domain, ~self.oe, buf.t)

        return m


class DDRBufferECP5(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            for bit in range(len(self.port)):
                m.submodules[f"i_ddr{bit}"] = Instance("IDDRX1F",
                    i_SCLK=ClockSignal(self.i_domain),
                    i_RST=Const(0),
                    i_D=buf.i[bit],
                    o_Q0=i0_inv[bit],
                    o_Q1=i1_inv[bit],
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
                m.submodules[f"o_ddr{bit}"] = Instance("ODDRX1F",
                    i_SCLK=ClockSignal(self.o_domain),
                    i_RST=Const(0),
                    i_D0=o0_inv[bit],
                    i_D1=o1_inv[bit],
                    o_Q=buf.o[bit],
                )
            _make_oereg_ecp5_machxo2(m, self.o_domain, ~self.oe, buf.t)

        return m


class DDRBufferMachXO2(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            for bit in range(len(self.port)):
                m.submodules[f"i_ddr{bit}"] = Instance("IDDRXE",
                    i_SCLK=ClockSignal(self.i_domain),
                    i_RST=Const(0),
                    i_D=buf.i[bit],
                    o_Q0=i0_inv[bit],
                    o_Q1=i1_inv[bit],
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
                m.submodules[f"o_ddr{bit}"] = Instance("ODDRXE",
                    i_SCLK=ClockSignal(self.o_domain),
                    i_RST=Const(0),
                    i_D0=o0_inv[bit],
                    i_D1=o1_inv[bit],
                    o_Q=buf.o[bit],
                )
            _make_oereg_ecp5_machxo2(m, self.o_domain, ~self.oe, buf.t)

        return m


class DDRBufferNexus(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            for bit in range(len(self.port)):
                m.submodules[f"i_ddr{bit}"] = Instance("IDDRX1",
                    i_SCLK=ClockSignal(self.i_domain),
                    i_RST=Const(0),
                    i_D=buf.i[bit],
                    o_Q0=i0_inv[bit],
                    o_Q1=i1_inv[bit],
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
                m.submodules[f"o_ddr{bit}"] = Instance("ODDRX1",
                    i_SCLK=ClockSignal(self.o_domain),
                    i_RST=Const(0),
                    i_D0=o0_inv[bit],
                    i_D1=o1_inv[bit],
                    o_Q=buf.o[bit],
                )
            _make_oereg_nexus(m, self.o_domain, ~self.oe, buf.t)

        return m


class LatticePlatform(TemplatedPlatform):
    """
    .. rubric:: Trellis toolchain (ECP5, MachXO2, MachXO3)

    Required tools:
        * ``yosys``
        * ``nextpnr-ecp5`` or ``nextpnr-machxo2``
        * ``ecppack``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_TRELLIS``, if present.

    Available overrides:
        * ``verbose``: enables logging of informational messages to standard error.
        * ``read_verilog_opts``: adds options for ``read_verilog`` Yosys command.
        * ``synth_opts``: adds options for ``synth_<family>`` Yosys command.
        * ``script_after_read``: inserts commands after ``read_ilang`` in Yosys script.
        * ``script_after_synth``: inserts commands after ``synth_<family>`` in Yosys script.
        * ``yosys_opts``: adds extra options for ``yosys``.
        * ``nextpnr_opts``: adds extra options for ``nextpnr-<family>``.
        * ``ecppack_opts``: adds extra options for ``ecppack``.
        * ``add_preferences``: inserts commands at the end of the LPF file.

    Build products:
        * ``{{name}}.rpt``: Yosys log.
        * ``{{name}}.json``: synthesized RTL.
        * ``{{name}}.tim``: nextpnr log.
        * ``{{name}}.config``: ASCII bitstream.
        * ``{{name}}.bit``: binary bitstream.
        * ``{{name}}.svf``: JTAG programming vector.

    .. rubric:: Oxide toolchain (Nexus)

    Required tools:
        * ``yosys``
        * ``nextpnr-nexus``
        * ``prjoxide``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_OXIDE``, if present.

    Available overrides:
        * ``verbose``: enables logging of informational messages to standard error.
        * ``read_verilog_opts``: adds options for ``read_verilog`` Yosys command.
        * ``synth_opts``: adds options for ``synth_nexus`` Yosys command.
        * ``script_after_read``: inserts commands after ``read_ilang`` in Yosys script.
        * ``script_after_synth``: inserts commands after ``synth_nexus`` in Yosys script.
        * ``yosys_opts``: adds extra options for ``yosys``.
        * ``nextpnr_opts``: adds extra options for ``nextpnr-nexus``.
        * ``prjoxide_opts``: adds extra options for ``prjoxide``.
        * ``add_preferences``: inserts commands at the end of the PDC file.

    Build products:
        * ``{{name}}.rpt``: Yosys log.
        * ``{{name}}.json``: synthesized RTL.
        * ``{{name}}.tim``: nextpnr log.
        * ``{{name}}.config``: ASCII bitstream.
        * ``{{name}}.bit``: binary bitstream.
        * ``{{name}}.xcf``: JTAG programming vector.

    .. rubric:: Diamond toolchain (ECP5, MachXO2, MachXO3)

    Required tools:
        * ``pnmainc``
        * ``ddtcmd``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_DIAMOND``, if present. On Linux, diamond_env as provided by Diamond
    itself is a good candidate. On Windows, the following script (named ``diamond_env.bat``,
    for instance) is known to work::

        @echo off
        set PATH=C:\\lscc\\diamond\\%DIAMOND_VERSION%\\bin\\nt64;%PATH%

    Available overrides:
        * ``script_project``: inserts commands before ``prj_project save`` in Tcl script.
        * ``script_after_export``: inserts commands after ``prj_run Export`` in Tcl script.
        * ``add_preferences``: inserts commands at the end of the LPF file.
        * ``add_constraints``: inserts commands at the end of the XDC file.

    Build products:
        * ``{{name}}_impl/{{name}}_impl.htm``: consolidated log.
        * ``{{name}}.jed``: JEDEC fuse file (MachXO2, MachXO3 only).
        * ``{{name}}.bit``: binary bitstream.
        * ``{{name}}.svf``: JTAG programming vector (ECP5 only).
        * ``{{name}}_flash.svf``: JTAG programming vector for FLASH programming (MachXO2, MachXO3 only).
        * ``{{name}}_sram.svf``: JTAG programming vector for SRAM programming (MachXO2, MachXO3 only).

    .. rubric:: Radiant toolchain (Nexus)

    Required tools:
        * ``radiantc``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_RADIANT``, if present. On Linux, radiant_env as provided by Radiant
    itself is a good candidate. On Windows, the following script (named ``radiant_env.bat``,
    for instance) is known to work::

        @echo off
        set PATH=C:\\lscc\\radiant\\%RADIANT_VERSION%\\bin\\nt64;%PATH%

    Available overrides:
        * ``script_project``: inserts commands before ``prj_save`` in Tcl script.
        * ``script_after_export``: inserts commands after ``prj_run Export`` in Tcl script.
        * ``add_constraints``: inserts commands at the end of the SDC file.
        * ``add_preferences``: inserts commands at the end of the PDC file.

    Build products:
        * ``{{name}}_impl/{{name}}_impl.htm``: consolidated log.
        * ``{{name}}.bit``: binary bitstream.
        * ``{{name}}.xcf``: JTAG programming vector. (if using ``programmer``)
    """

    toolchain = None # selected when creating platform

    device  = property(abstractmethod(lambda: None))
    package = property(abstractmethod(lambda: None))
    speed   = property(abstractmethod(lambda: None))
    grade   = "C" # [C]ommercial, [I]ndustrial

    # Trellis templates

    _nextpnr_device_options = {
        "LFE5U-12F":    "--12k",
        "LFE5U-25F":    "--25k",
        "LFE5U-45F":    "--45k",
        "LFE5U-85F":    "--85k",
        "LFE5UM-25F":   "--um-25k",
        "LFE5UM-45F":   "--um-45k",
        "LFE5UM-85F":   "--um-85k",
        "LFE5UM5G-25F": "--um5g-25k",
        "LFE5UM5G-45F": "--um5g-45k",
        "LFE5UM5G-85F": "--um5g-85k",
    }
    _nextpnr_package_options = {
        "BG256": "caBGA256",
        "MG285": "csfBGA285",
        "BG381": "caBGA381",
        "BG554": "caBGA554",
        "BG756": "caBGA756",
    }

    _trellis_required_tools_ecp5 = [
        "yosys",
        "nextpnr-ecp5",
        "ecppack"
    ]
    _trellis_required_tools_machxo2 = [
        "yosys",
        "nextpnr-machxo2",
        "ecppack"
    ]
    _trellis_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "{{name}}.il": r"""
            # {{autogenerated}}
            {{emit_rtlil()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.ys": r"""
            # {{autogenerated}}
            {% for file in platform.iter_files(".v") -%}
                read_verilog {{get_override("read_verilog_opts")|options}} {{file}}
            {% endfor %}
            {% for file in platform.iter_files(".sv") -%}
                read_verilog -sv {{get_override("read_verilog_opts")|options}} {{file}}
            {% endfor %}
            {% for file in platform.iter_files(".il") -%}
                read_ilang {{file}}
            {% endfor %}
            read_ilang {{name}}.il
            {{get_override("script_after_read")|default("# (script_after_read placeholder)")}}
            {% if platform.family == "ecp5" %}
                synth_ecp5 {{get_override("synth_opts")|options}} -top {{name}}
            {% else %}
                synth_lattice -family xo2 {{get_override("synth_opts")|options}} -top {{name}}
            {% endif %}
            {{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
            write_json {{name}}.json
        """,
        "{{name}}.lpf": r"""
            # {{autogenerated}}
            BLOCK ASYNCPATHS;
            BLOCK RESETPATHS;
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                LOCATE COMP "{{port_name}}" SITE "{{pin_name}}";
                {% if attrs -%}
                IOBUF PORT "{{port_name}}"
                    {%- for key, value in attrs.items() %} {{key}}={{value}}{% endfor %};
                {% endif %}
            {% endfor %}
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                FREQUENCY NET "{{signals|hierarchy(".")}}" {{frequency}} HZ;
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                FREQUENCY PORT "{{port.name}}" {{frequency}} HZ;
            {% endfor %}
            {{get_override("add_preferences")|default("# (add_preferences placeholder)")}}
        """
    }
    _trellis_command_templates = [
        r"""
        {{invoke_tool("yosys")}}
            {{quiet("-q")}}
            {{get_override("yosys_opts")|options}}
            -l {{name}}.rpt
            {{name}}.ys
        """,
        r"""
        {{invoke_tool("nextpnr-" + platform.family)}}
            {{quiet("--quiet")}}
            {{get_override("nextpnr_opts")|options}}
            --log {{name}}.tim
            {% if platform.family == "ecp5" %}
                {{platform._nextpnr_device_options[platform.device]}}
                --package {{platform._nextpnr_package_options[platform.package]|upper}}
                --speed {{platform.speed}}
            {% else %}
                --device {{platform.device}}-{{platform.speed}}{{platform.package}}{{platform.grade}}
            {% endif %}
            --json {{name}}.json
            --lpf {{name}}.lpf
            --textcfg {{name}}.config
        """,
        r"""
        {{invoke_tool("ecppack")}}
            {{verbose("--verbose")}}
            {{get_override("ecppack_opts")|options}}
            --input {{name}}.config
            --bit {{name}}.bit
            --svf {{name}}.svf
        """
    ]

    # Oxide templates

    _oxide_required_tools = [
        "yosys",
        "nextpnr-nexus",
        "prjoxide"
    ]
    _oxide_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "{{name}}.il": r"""
            # {{autogenerated}}
            {{emit_rtlil()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.ys": r"""
            # {{autogenerated}}
            {% for file in platform.iter_files(".v") -%}
                read_verilog {{get_override("read_verilog_opts")|options}} {{file}}
            {% endfor %}
            {% for file in platform.iter_files(".sv") -%}
                read_verilog -sv {{get_override("read_verilog_opts")|options}} {{file}}
            {% endfor %}
            {% for file in platform.iter_files(".il") -%}
                read_ilang {{file}}
            {% endfor %}
            read_ilang {{name}}.il
            delete w:$verilog_initial_trigger
            {{get_override("script_after_read")|default("# (script_after_read placeholder)")}}
            synth_nexus {{get_override("synth_opts")|options}} -top {{name}}
            {{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
            write_json {{name}}.json
        """,
        "{{name}}.pdc": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                ldc_set_location -site {{ '{' }}{{pin_name}}{{ '}' }} {{'['}}get_ports {{port_name}}{{']'}}
                {% if attrs -%}
                ldc_set_port -iobuf {{ '{' }}{%- for key, value in attrs.items() %}{{key}}={{value}} {% endfor %}{{ '}' }} {{'['}}get_ports {{port_name}}{{']'}}
                {% endif %}
            {% endfor %}
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                create_clock -name {{signal.name|tcl_quote}} -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("/")|tcl_quote}}]
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                create_clock -name {{port.name|tcl_quote}} -period {{1000000000/frequency}} [get_ports {{port.name|tcl_quote}}]
            {% endfor %}
            {{get_override("add_preferences")|default("# (add_preferences placeholder)")}}
        """
    }
    _oxide_command_templates = [
        r"""
        {{invoke_tool("yosys")}}
            {{get_override("yosys_opts")|options}}
            -l {{name}}.rpt
            {{name}}.ys
        """,
        r"""
        {{invoke_tool("nextpnr-nexus")}}
            {{get_override("nextpnr_opts")|options}}
            --log {{name}}.tim
            --device {{platform.device}}-{{platform.speed}}{{platform.package}}{{platform.grade}}
            --pdc {{name}}.pdc
            --json {{name}}.json
            --fasm {{name}}.fasm
        """,
        r"""
        {{invoke_tool("prjoxide")}}
            {{verbose("--verbose")}}
            {{get_override("prjoxide_opts")|options}}
            pack {{name}}.fasm
            {{name}}.bit
        """
    ]

    # Diamond templates

    _diamond_required_tools = [
        "pnmainc",
        "ddtcmd"
    ]
    _diamond_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
            #!/bin/sh
            # {{autogenerated}}
            set -e{{verbose("x")}}
            if [ -z "$BASH" ] ; then exec /bin/bash "$0" "$@"; fi
            if [ -n "${{platform._toolchain_env_var}}" ]; then
                bindir=$(dirname "${{platform._toolchain_env_var}}")
                . "${{platform._toolchain_env_var}}"
            fi
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
            prj_project new -name {{name}} -impl impl -impl_dir {{name}}_impl \
                -dev {{platform.device}}-{{platform.speed}}{{platform.package}}{{platform.grade}} \
                -lpf {{name}}.lpf \
                -synthesis synplify
            {% for file in platform.iter_files(".v", ".sv", ".vhd", ".vhdl") -%}
                prj_src add {{file|tcl_quote}}
            {% endfor %}
            prj_src add {{name}}.v
            prj_impl option top {{name}}
            prj_src add {{name}}.sdc
            {{get_override("script_project")|default("# (script_project placeholder)")}}
            prj_project save
            prj_run Synthesis -impl impl
            prj_run Translate -impl impl
            prj_run Map -impl impl
            prj_run PAR -impl impl
            prj_run Export -impl impl -task Bitgen
            {% if platform.family == "machxo2" -%}
                prj_run Export -impl impl -task Jedecgen
            {% endif %}
            {{get_override("script_after_export")|default("# (script_after_export placeholder)")}}
        """,
        "{{name}}.lpf": r"""
            # {{autogenerated}}
            BLOCK ASYNCPATHS;
            BLOCK RESETPATHS;
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                LOCATE COMP "{{port_name}}" SITE "{{pin_name}}";
                {% if attrs -%}
                IOBUF PORT "{{port_name}}"
                    {%- for key, value in attrs.items() %} {{key}}={{value}}{% endfor %};
                {% endif %}
            {% endfor %}
            {{get_override("add_preferences")|default("# (add_preferences placeholder)")}}
        """,
        "{{name}}.sdc": r"""
            set_hierarchy_separator {/}
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                create_clock -name {{signal.name|tcl_quote("Diamond")}} -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("/")|tcl_quote("Diamond")}}]
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                create_clock -name {{port.name|tcl_quote("Diamond")}} -period {{1000000000/frequency}} [get_ports {{port.name|tcl_quote("Diamond")}}]
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """,
    }
    _diamond_command_templates_ecp5 = [
        # These don't have any usable command-line option overrides.
        r"""
        {{invoke_tool("pnmainc")}}
            {{name}}.tcl
        """,
        r"""
        {{invoke_tool("ddtcmd")}}
            -oft -bit
            -if {{name}}_impl/{{name}}_impl.bit -of {{name}}.bit
        """,
        r"""
        {{invoke_tool("ddtcmd")}}
            -oft -svfsingle -revd -op "Fast Program"
            -if {{name}}_impl/{{name}}_impl.bit -of {{name}}.svf
        """,
    ]
    _diamond_command_templates_machxo2 = [
        # These don't have any usable command-line option overrides.
        r"""
        {{invoke_tool("pnmainc")}}
            {{name}}.tcl
        """,
        r"""
        {{invoke_tool("ddtcmd")}}
            -oft -bit
            -if {{name}}_impl/{{name}}_impl.bit -of {{name}}.bit
        """,
        r"""
        {{invoke_tool("ddtcmd")}}
            -oft -jed
            -dev {{platform.device}}-{{platform.speed}}{{platform.package}}{{platform.grade}}
            -if {{name}}_impl/{{name}}_impl.jed -of {{name}}.jed
        """,
        r"""
        {{invoke_tool("ddtcmd")}}
            -oft -svfsingle -revd -op "FLASH Erase,Program,Verify"
            -if {{name}}_impl/{{name}}_impl.jed -of {{name}}_flash.svf
        """,
        r"""
        {{invoke_tool("ddtcmd")}}
            -oft -svfsingle -revd -op "SRAM Fast Program"
            -if {{name}}_impl/{{name}}_impl.bit -of {{name}}_sram.svf
        """,
    ]

    # Radiant templates

    _radiant_required_tools = [
        "radiantc",
    ]
    _radiant_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
            # {{autogenerated}}
            set -e{{verbose("x")}}
            if [ -z "$BASH" ] ; then exec /bin/bash "$0" "$@"; fi
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
            prj_create -name {{name}} -impl impl \
                -dev {{platform.device}}-{{platform.speed}}{{platform.package}}{{platform.grade}} \
                -synthesis synplify
            {% for file in platform.iter_files(".v", ".sv", ".vhd", ".vhdl") -%}
                prj_add_source {{file|tcl_quote}}
            {% endfor %}
            prj_add_source {{name}}.v
            prj_add_source {{name}}.sdc
            prj_add_source {{name}}.pdc
            prj_set_impl_opt top \"{{name}}\"
            {{get_override("script_project")|default("# (script_project placeholder)")}}
            prj_save
            prj_run Synthesis -impl impl -forceOne
            prj_run Map -impl impl
            prj_run PAR -impl impl
            prj_run Export -impl impl -task Bitgen
            {{get_override("script_after_export")|default("# (script_after_export placeholder)")}}
        """,
        # Pre-synthesis SDC constraints
        "{{name}}.sdc": r"""
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                create_clock -name {{signal.name|tcl_quote}} -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("/")|tcl_quote}}]
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                create_clock -name {{port.name|tcl_quote}} -period {{1000000000/frequency}} [get_ports {{port.name|tcl_quote}}]
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """,
        # Physical PDC contraints
        "{{name}}.pdc": r"""
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                ldc_set_location -site "{{pin_name}}" [get_ports {{port_name|tcl_quote}}]
                {% if attrs -%}
                ldc_set_port -iobuf { {%- for key, value in attrs.items() %} {{key}}={{value}}{% endfor %} } [get_ports {{port_name|tcl_quote}}]
                {% endif %}
            {% endfor %}
            {{get_override("add_preferences")|default("# (add_preferences placeholder)")}}
        """,
    }
    _radiant_command_templates = [
        # These don't have any usable command-line option overrides.
        r"""
        {{invoke_tool("radiantc")}}
            {{name}}.tcl
        """,
    ]

    # Common logic

    def __init__(self, *, toolchain=None):
        super().__init__()

        device = self.device.lower()
        if device.startswith(("lfe5", "lae5")):
            self.family = "ecp5"
        elif device.startswith(("lcmxo2-", "lcmxo3l", "lcmxo3d", "lamxo2-", "lamxo3l", "lamxo3d",
                                "lfmnx-")):
            self.family = "machxo2"
        elif device.startswith(("lifcl-", "lfcpnx-", "lfd2nx-", "lfmxo5-", "ut24c")):
            self.family = "nexus"
        else:
            raise ValueError(f"Device '{self.device}' is not recognized")

        if toolchain is None:
            if self.family == "nexus":
                toolchain = "Oxide"
            elif self.family == "ecp5":
                toolchain = "Trellis"
            else:
                toolchain = "Diamond"

        if self.family == "nexus":
            assert toolchain in ("Oxide", "Radiant")
        else:
            assert toolchain in ("Trellis", "Diamond")
        self.toolchain = toolchain

    @property
    def required_tools(self):
        if self.toolchain == "Trellis":
            if self.family == "ecp5":
                return self._trellis_required_tools_ecp5
            elif self.family == "machxo2":
                return self._trellis_required_tools_machxo2
        if self.toolchain == "Oxide":
            return self._oxide_required_tools
        if self.toolchain == "Diamond":
            return self._diamond_required_tools
        if self.toolchain == "Radiant":
            return self._radiant_required_tools
        assert False

    @property
    def file_templates(self):
        if self.toolchain == "Trellis":
            return self._trellis_file_templates
        if self.toolchain == "Oxide":
            return self._oxide_file_templates
        if self.toolchain == "Diamond":
            return self._diamond_file_templates
        if self.toolchain == "Radiant":
            return self._radiant_file_templates
        assert False

    @property
    def command_templates(self):
        if self.toolchain == "Trellis":
            return self._trellis_command_templates
        if self.toolchain == "Oxide":
            return self._oxide_command_templates
        if self.toolchain == "Diamond":
            if self.family == "ecp5":
                return self._diamond_command_templates_ecp5
            if self.family == "machxo2":
                return self._diamond_command_templates_machxo2
        if self.toolchain == "Radiant":
            return self._radiant_command_templates
        assert False

    # These numbers were extracted from
    # "MachXO2 sysCLOCK PLL Design and Usage Guide"
    _supported_osch_freqs = [
        2.08, 2.15, 2.22, 2.29, 2.38, 2.46, 2.56, 2.66, 2.77, 2.89,
        3.02, 3.17, 3.33, 3.50, 3.69, 3.91, 4.16, 4.29, 4.43, 4.59,
        4.75, 4.93, 5.12, 5.32, 5.54, 5.78, 6.05, 6.33, 6.65, 7.00,
        7.39, 7.82, 8.31, 8.58, 8.87, 9.17, 9.50, 9.85, 10.23, 10.64,
        11.08, 11.57, 12.09, 12.67, 13.30, 14.00, 14.78, 15.65, 15.65, 16.63,
        17.73, 19.00, 20.46, 22.17, 24.18, 26.60, 29.56, 33.25, 38.00, 44.33,
        53.20, 66.50, 88.67, 133.00
    ]

    @property
    def default_clk_constraint(self):
        if self.default_clk == "OSCG":
            # Internal high-speed oscillator on ECP5 devices.
            return Clock(310e6 / self.oscg_div)
        if self.default_clk == "OSCH":
            # Internal high-speed oscillator on MachXO2/MachXO3L devices.
            # It can have a range of frequencies.
            assert self.osch_frequency in self._supported_osch_freqs
            return Clock(int(self.osch_frequency * 1e6))
        if self.default_clk == "OSCA":
            # Internal high-speed oscillator on Nexus devices.
            return Clock(450e6 / self.osca_div)
        # Otherwise, use the defined Clock resource.
        return super().default_clk_constraint

    def create_missing_domain(self, name):
        # Lattice devices have two global set/reset signals: PUR, which is driven at startup
        # by the configuration logic and unconditionally resets every storage element, and GSR,
        # which is driven by user logic and each storage element may be configured as affected or
        # unaffected by GSR. PUR is purely asynchronous, so even though it is a low-skew global
        # network, its deassertion may violate a setup/hold constraint with relation to a user
        # clock. To avoid this, a GSR/SGSR instance should be driven synchronized to user clock.
        if name == "sync" and self.default_clk is not None:
            using_osch = False
            m = Module()
            if self.default_clk == "OSCG":
                if not hasattr(self, "oscg_div"):
                    raise ValueError(
                        "OSCG divider (oscg_div) must be an integer between 2 and 128")
                if not isinstance(self.oscg_div, int) or self.oscg_div < 2 or self.oscg_div > 128:
                    raise ValueError(
                        f"OSCG divider (oscg_div) must be an integer between 2 and 128, "
                        f"not {self.oscg_div!r}")
                clk_i = Signal()
                m.submodules += Instance("OSCG", p_DIV=self.oscg_div, o_OSC=clk_i)
            elif self.default_clk == "OSCH":
                osch_freq = self.osch_frequency
                if osch_freq not in self._supported_osch_freqs:
                    raise ValueError(
                        f"Frequency {osch_freq!r} is not valid for OSCH clock. "
                        f"Valid frequencies are {self._supported_osch_freqs!r}")
                osch_freq_param = f"{float(osch_freq):.2f}"
                clk_i = Signal()
                m.submodules += Instance("OSCH",
                    p_NOM_FREQ=osch_freq_param,
                    i_STDBY=Const(0),
                    o_OSC=clk_i,
                    o_SEDSTDBY=Signal()
                )
            elif self.default_clk == "OSCA":
                if not hasattr(self, "osca_div"):
                    raise ValueError(
                        f"OSCA divider (osca_div) must be an integer between 2 and 256")
                if not isinstance(self.osca_div, int) or self.osca_div < 2 or self.osca_div > 256:
                    raise ValueError(
                        f"OSCA divider (osca_div) must be an integer between 2 and 256, "
                        f"not {self.osca_div!r}")
                clk_i = Signal()
                m.submodules += Instance("OSCA",
                    p_HF_CLK_DIV=str(self.osca_div - 1),
                    i_HFOUTEN=Const(1),
                    i_HFSDSCEN=Const(0),  # HFSDSCEN used for SED/SEC detector
                    o_HFCLKOUT=clk_i,
                )
            else:
                clk_io = self.request(self.default_clk, dir="-")
                m.submodules.clk_buf = clk_buf = io.Buffer("i", clk_io)
                clk_i = clk_buf.i

            if self.default_rst is not None:
                rst_io = self.request(self.default_rst, dir="-")
                m.submodules.rst_buf = rst_buf = io.Buffer("i", rst_io)
                rst_i = rst_buf.i
            else:
                rst_i = Const(0)

            gsr0 = Signal()
            gsr1 = Signal()
            # There is no end-of-startup signal on Lattice, but PUR is released after IOB enable, so
            # a simple reset synchronizer (with PUR as the asynchronous reset) does the job.
            if self.family == "nexus":
                # On Nexus all the D-type FFs have either an synchronous or asynchronous preset.
                # Here we build a simple reset synchronizer from D-type FFs with a positive-level
                # asynchronous preset which we tie low
                m.submodules += [
                    Instance("FD1P3BX",
                        p_GSR="DISABLED",
                        i_CK=clk_i,
                        i_D=~rst_i,
                        i_SP=Const(1),
                        i_PD=Const(0),
                        o_Q=gsr0,
                    ),
                    Instance("FD1P3BX",
                        p_GSR="DISABLED",
                        i_CK=clk_i,
                        i_D=gsr0,
                        i_SP=Const(1),
                        i_PD=Const(0),
                        o_Q=gsr1,
                    ),
                    Instance("GSR", p_SYNCMODE="SYNC", i_CLK=clk_i, i_GSR_N=gsr1),
                ]
            else:
                m.submodules += [
                    Instance("FD1S3AX", p_GSR="DISABLED", i_CK=clk_i, i_D=~rst_i, o_Q=gsr0),
                    Instance("FD1S3AX", p_GSR="DISABLED", i_CK=clk_i, i_D=gsr0,   o_Q=gsr1),
                    # Although we already synchronize the reset input to user clock, SGSR has
                    # dedicated clock routing to the center of the FPGA; use that just in case it
                    # turns out to be more reliable. (None of this is documented.)
                    Instance("SGSR", i_CLK=clk_i, i_GSR=gsr1),
                ]
            # GSR implicitly connects to every appropriate storage element. As such, the sync
            # domain is reset-less; domains driven by other clocks would need to have dedicated
            # reset circuitry or otherwise meet setup/hold constraints on their own.
            m.domains += ClockDomain("sync", reset_less=True)
            m.d.comb += ClockSignal("sync").eq(clk_i)
            return m

    def get_io_buffer(self, buffer):
        if isinstance(buffer, io.Buffer):
            result = IOBuffer(buffer.direction, buffer.port)
        elif isinstance(buffer, io.FFBuffer):
            if self.family in ("ecp5", "machxo2"):
                result = FFBufferECP5(buffer.direction, buffer.port,
                                      i_domain=buffer.i_domain,
                                      o_domain=buffer.o_domain)
            elif self.family == "nexus":
                result = FFBufferNexus(buffer.direction, buffer.port,
                                       i_domain=buffer.i_domain,
                                       o_domain=buffer.o_domain)
            else:
                raise NotImplementedError # :nocov:
        elif isinstance(buffer, io.DDRBuffer):
            if self.family == "ecp5":
                result = DDRBufferECP5(buffer.direction, buffer.port,
                                       i_domain=buffer.i_domain,
                                       o_domain=buffer.o_domain)
            elif self.family == "machxo2":
                result = DDRBufferMachXO2(buffer.direction, buffer.port,
                                          i_domain=buffer.i_domain,
                                          o_domain=buffer.o_domain)
            elif self.family == "nexus":
                result = DDRBufferNexus(buffer.direction, buffer.port,
                                        i_domain=buffer.i_domain,
                                        o_domain=buffer.o_domain)
            else:
                raise NotImplementedError # :nocov:
        else:
            raise TypeError(f"Unsupported buffer type {buffer!r}") # :nocov:
        if buffer.direction is not io.Direction.Output:
            result.i = buffer.i
        if buffer.direction is not io.Direction.Input:
            result.o = buffer.o
            result.oe = buffer.oe
        return result

    # CDC primitives are not currently specialized for Lattice.
    # While Diamond supports false path constraints; nextpnr-ecp5 does not.
