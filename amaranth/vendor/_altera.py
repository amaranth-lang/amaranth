from abc import abstractmethod

from ..hdl import *
from ..hdl import _ast
from ..hdl._ir import RequirePosedge
from ..lib import io, wiring
from ..build import *


# The altiobuf_* and altddio_* primitives are explained in the following Intel documents:
# * https://www.intel.com/content/dam/www/programmable/us/en/pdfs/literature/ug/ug_altiobuf.pdf
# * https://www.intel.com/content/dam/www/programmable/us/en/pdfs/literature/ug/ug_altddio.pdf
# See also errata mentioned in: https://www.intel.com/content/www/us/en/programmable/support/support-resources/knowledge-base/solutions/rd11192012_735.html.


# Horrible hack here. To get Quartus to pack FFs into IOEs, the port needs to have an
# ``useioff`` attribute. Unfortunately, this means that FF packing can only be controlled
# with port granularity, not bit granularity. However, Quartus doesn't seem to mind
# this attribute being set when it's not possible to pack a FF — it's just ignored with
# a warning. So, we just set it on whatever is passed to ``FFBuffer`` — at worst, we'll
# cause some extra random FFs to be opportunistically packed into the IOE for other bits
# of a sliced port.
#
# This function is also used by ``DDRBuffer`` to pack the output enable FF.
def _add_useioff(value):
    if isinstance(value, _ast.IOPort):
        value.attrs["useioff"] = 1
    elif isinstance(value, _ast.IOConcat):
        for part in value.parts:
            _add_useioff(part)
    elif isinstance(value, _ast.IOSlice):
        _add_useioff(value.value)
    else:
        raise NotImplementedError # :nocov:


class InnerBuffer(wiring.Component):
    """A private component used to implement ``lib.io`` buffers.

    Works like ``lib.io.Buffer``, with the following differences:

    - ``port.invert`` is ignored (handling the inversion is the outer buffer's responsibility)
    - output enable is per-pin
    """
    def __init__(self, direction, port, *, useioff=False):
        self.direction = direction
        self.port = port
        members = {}
        if direction is not io.Direction.Output:
            members["i"] = wiring.In(len(port))
        if direction is not io.Direction.Input:
            members["o"] = wiring.Out(len(port))
            members["oe"] = wiring.Out(len(port))
        super().__init__(wiring.Signature(members).flip())
        if useioff:
            if isinstance(port, io.SingleEndedPort):
                _add_useioff(port.io)
            elif isinstance(port, io.DifferentialPort):
                _add_useioff(port.p)
                _add_useioff(port.n)

    def elaborate(self, platform):
        kwargs = dict(
            p_enable_bus_hold="FALSE",
            p_number_of_channels=len(self.port),
        )
        if isinstance(self.port, io.SingleEndedPort):
            kwargs["p_use_differential_mode"] = "FALSE"
        elif isinstance(self.port, io.DifferentialPort):
            kwargs["p_use_differential_mode"] = "TRUE"
        else:
            raise TypeError(f"Unknown port type {self.port!r}")

        if self.direction is io.Direction.Input:
            if isinstance(self.port, io.SingleEndedPort):
                kwargs["i_datain"] = self.port.io
            else:
                kwargs["i_datain"] = self.port.p,
                kwargs["i_datain_b"] = self.port.n,
            return Instance("altiobuf_in",
                o_dataout=self.i,
                **kwargs,
            )
        elif self.direction is io.Direction.Output:
            if isinstance(self.port, io.SingleEndedPort):
                kwargs["o_dataout"] = self.port.io
            else:
                kwargs["o_dataout"] = self.port.p,
                kwargs["o_dataout_b"] = self.port.n,
            return Instance("altiobuf_out",
                p_use_oe="TRUE",
                i_datain=self.o,
                i_oe=self.oe,
                **kwargs,
            )
        elif self.direction is io.Direction.Bidir:
            if isinstance(self.port, io.SingleEndedPort):
                kwargs["io_dataio"] = self.port.io
            else:
                kwargs["io_dataio"] = self.port.p,
                kwargs["io_dataio_b"] = self.port.n,
            return Instance("altiobuf_bidir",
                i_datain=self.o,
                i_oe=self.oe,
                o_dataout=self.i,
                **kwargs,
            )
        else:
            assert False # :nocov:


class IOBuffer(io.Buffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.d.comb += self.i.eq(buf.i ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.d.comb += buf.o.eq(self.o ^ inv_mask)
            m.d.comb += buf.oe.eq(self.oe.replicate(len(self.port)))

        return m


class FFBuffer(io.FFBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port, useioff=True)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            i_inv = Signal.like(self.i)
            m.d[self.i_domain] += i_inv.eq(buf.i)
            m.d.comb += self.i.eq(i_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.d[self.o_domain] += buf.o.eq(self.o ^ inv_mask)
            m.d[self.o_domain] += buf.oe.eq(self.oe.replicate(len(self.port)))

        return m


class DDRBuffer(io.DDRBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port, useioff=True)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            m.submodules += RequirePosedge(self.i_domain)
            i0_reg = Signal(len(self.port))
            i0_inv = Signal(len(self.port))
            i1_inv = Signal(len(self.port))
            m.submodules.i_ddr = Instance("altddio_in",
                p_width=len(self.port),
                i_datain=buf.i,
                i_inclock=ClockSignal(self.i_domain),
                o_dataout_h=i0_inv,
                o_dataout_l=i1_inv,
            )
            m.d[self.i_domain] += i0_reg.eq(i0_inv)
            m.d.comb += self.i[0].eq(i0_reg ^ inv_mask)
            m.d.comb += self.i[1].eq(i1_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            m.submodules.o_ddr = Instance("altddio_out",
                p_width=len(self.port),
                o_dataout=buf.o,
                i_outclock=ClockSignal(self.o_domain),
                i_datain_h=self.o[0] ^ inv_mask,
                i_datain_l=self.o[1] ^ inv_mask,
            )
            m.d[self.o_domain] += buf.oe.eq(self.oe.replicate(len(self.port)))

        return m


class AlteraPlatform(TemplatedPlatform):
    """
    .. rubric:: Quartus toolchain

    Required tools:
        * ``quartus_map``
        * ``quartus_fit``
        * ``quartus_asm``
        * ``quartus_sta``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_QUARTUS``, if present.

    Available overrides:
        * ``add_settings``: inserts commands at the end of the QSF file.
        * ``add_constraints``: inserts commands at the end of the SDC file.
        * ``nproc``: sets the number of cores used by all tools.
        * ``quartus_map_opts``: adds extra options for ``quartus_map``.
        * ``quartus_fit_opts``: adds extra options for ``quartus_fit``.
        * ``quartus_asm_opts``: adds extra options for ``quartus_asm``.
        * ``quartus_sta_opts``: adds extra options for ``quartus_sta``.

    Build products:
        * ``*.rpt``: toolchain reports.
        * ``{{name}}.sof``: bitstream as SRAM object file.
        * ``{{name}}.rbf``: bitstream as raw binary file.


    .. rubric:: Mistral toolchain

    Required tools:
        * ``yosys``
        * ``nextpnr-mistral``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_MISTRAL``, if present.

        * ``verbose``: enables logging of informational messages to standard error.
        * ``read_verilog_opts``: adds options for ``read_verilog`` Yosys command.
        * ``synth_opts``: adds options for ``synth_intel_alm`` Yosys command.
        * ``script_after_read``: inserts commands after ``read_ilang`` in Yosys script.
        * ``script_after_synth``: inserts commands after ``synth_intel_alm`` in Yosys script.
        * ``yosys_opts``: adds extra options for ``yosys``.
        * ``nextpnr_opts``: adds extra options for ``nextpnr-mistral``.
    """

    toolchain = None # selected when creating platform

    device  = property(abstractmethod(lambda: None))
    package = property(abstractmethod(lambda: None))
    speed   = property(abstractmethod(lambda: None))
    suffix  = ""

    # Quartus templates

    quartus_suppressed_warnings = [
        10264,  # All case item expressions in this case statement are onehot
        10270,  # Incomplete Verilog case statement has no default case item
        10335,  # Unrecognized synthesis attribute
        10763,  # Verilog case statement has overlapping case item expressions with non-constant or don't care bits
        10935,  # Verilog casex/casez overlaps with a previous casex/vasez item expression
        12125,  # Using design file which is not specified as a design file for the current project, but contains definitions used in project
        18236,  # Number of processors not specified in QSF
        176225, # Can't pack node <node> to I/O pin
        176250, # Ignoring invalid fast I/O register assignments.
        176272, # Can't pack node <node> and I/O cell
        292013, # Feature is only available with a valid subscription license
    ]

    quartus_required_tools = [
        "quartus_map",
        "quartus_fit",
        "quartus_asm",
        "quartus_sta",
    ]

    quartus_file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
            #!/bin/sh
            # {{autogenerated}}
            if [ -n "${{platform._toolchain_env_var}}" ]; then
                QUARTUS_ROOTDIR=$(dirname $(dirname "${{platform._toolchain_env_var}}"))
                # Quartus' qenv.sh does not work with `set -e`.
                . "${{platform._toolchain_env_var}}"
            fi
            set -e{{verbose("x")}}
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
        "{{name}}.qsf": r"""
            # {{autogenerated}}
            {% if get_override("nproc") -%}
                set_global_assignment -name NUM_PARALLEL_PROCESSORS {{get_override("nproc")}}
            {% endif %}

            {% for file in platform.iter_files(".v") -%}
                set_global_assignment -name VERILOG_FILE {{file|tcl_quote}}
            {% endfor %}
            {% for file in platform.iter_files(".sv") -%}
                set_global_assignment -name SYSTEMVERILOG_FILE {{file|tcl_quote}}
            {% endfor %}
            {% for file in platform.iter_files(".vhd", ".vhdl") -%}
                set_global_assignment -name VHDL_FILE {{file|tcl_quote}}
            {% endfor %}
            set_global_assignment -name VERILOG_FILE {{name}}.v
            set_global_assignment -name TOP_LEVEL_ENTITY {{name}}

            set_global_assignment -name DEVICE {{platform.device}}{{platform.package}}{{platform.speed}}{{platform.suffix}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                set_location_assignment -to {{port_name|tcl_quote}} PIN_{{pin_name}}
                {% for key, value in attrs.items() -%}
                    set_instance_assignment -to {{port_name|tcl_quote}} -name {{key}} {{value|tcl_quote}}
                {% endfor %}
            {% endfor %}

            set_global_assignment -name GENERATE_RBF_FILE ON

            {{get_override("add_settings")|default("# (add_settings placeholder)")}}
        """,
        "{{name}}.sdc": r"""
            {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
                create_clock -name {{signal.name|tcl_quote}} -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("|")|tcl_quote}}]
            {% endfor %}
            {% for port, frequency in platform.iter_port_clock_constraints() -%}
                create_clock -name {{port.name|tcl_quote}} -period {{1000000000/frequency}} [get_ports {{port.name|tcl_quote}}]
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """,
        "{{name}}.srf": r"""
            {% for warning in platform.quartus_suppressed_warnings %}
            { "" "" "" "{{name}}.v" {  } {  } 0 {{warning}} "" 0 0 "Design Software" 0 -1 0 ""}
            {% endfor %}
        """,
    }
    quartus_command_templates = [
        r"""
        {{invoke_tool("quartus_map")}}
            {{get_override("quartus_map_opts")|options}}
            --rev={{name}} {{name}}
        """,
        r"""
        {{invoke_tool("quartus_fit")}}
            {{get_override("quartus_fit_opts")|options}}
            --rev={{name}} {{name}}
        """,
        r"""
        {{invoke_tool("quartus_asm")}}
            {{get_override("quartus_asm_opts")|options}}
            --rev={{name}} {{name}}
        """,
        r"""
        {{invoke_tool("quartus_sta")}}
            {{get_override("quartus_sta_opts")|options}}
            --rev={{name}} {{name}}
        """,
    ]


    # Mistral templates

    mistral_required_tools = [
        "yosys",
        "nextpnr-mistral"
    ]
    mistral_file_templates = {
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
            synth_intel_alm {{get_override("synth_opts")|options}} -top {{name}}
            {{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
            write_json {{name}}.json
        """,
        "{{name}}.qsf": r"""
            # {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                set_location_assignment -to {{port_name|tcl_quote}} PIN_{{pin_name}}
                {% for key, value in attrs.items() -%}
                    set_instance_assignment -to {{port_name|tcl_quote}} -name {{key}} {{value|tcl_quote}}
                {% endfor %}
            {% endfor %}
        """,

    }
    mistral_command_templates = [
        r"""
        {{invoke_tool("yosys")}}
            {{quiet("-q")}}
            {{get_override("yosys_opts")|options}}
            -l {{name}}.rpt
            {{name}}.ys
        """,
        r"""
        {{invoke_tool("nextpnr-mistral")}}
            {{quiet("--quiet")}}
            {{get_override("nextpnr_opts")|options}}
            --log {{name}}.tim
            --device {{platform.device}}{{platform.package}}{{platform.speed}}{{platform.suffix}}
            --json {{name}}.json
            --qsf {{name}}.qsf
            --rbf {{name}}.rbf
        """
    ]

    # Common logic

    def __init__(self, *, toolchain="Quartus"):
        super().__init__()

        assert toolchain in ("Quartus", "Mistral")
        self.toolchain = toolchain

    @property
    def required_tools(self):
        if self.toolchain == "Quartus":
            return self.quartus_required_tools
        if self.toolchain == "Mistral":
            return self.mistral_required_tools
        assert False

    @property
    def file_templates(self):
        if self.toolchain == "Quartus":
            return self.quartus_file_templates
        if self.toolchain == "Mistral":
            return self.mistral_file_templates
        assert False

    @property
    def command_templates(self):
        if self.toolchain == "Quartus":
            return self.quartus_command_templates
        if self.toolchain == "Mistral":
            return self.mistral_command_templates
        assert False

    def add_clock_constraint(self, clock, frequency):
        super().add_clock_constraint(clock, frequency)
        clock.attrs["keep"] = "true"

    @property
    def default_clk_constraint(self):
        # Internal high-speed oscillator on Cyclone V devices.
        # It is specified to not be faster than 100MHz, but the actual
        # frequency seems to vary a lot between devices. Measurements
        # of 78 to 84 MHz have been observed.
        if self.default_clk == "cyclonev_oscillator":
            assert self.device.startswith("5C")
            return Clock(100e6)
        # Otherwise, use the defined Clock resource.
        return super().default_clk_constraint

    def create_missing_domain(self, name):
        if name == "sync" and self.default_clk == "cyclonev_oscillator":
            # Use the internal high-speed oscillator for Cyclone V devices
            assert self.device.startswith("5C")
            m = Module()
            m.domains += ClockDomain("sync")
            m.submodules += Instance("cyclonev_oscillator",
                                     i_oscena=Const(1),
                                     o_clkout=ClockSignal("sync"))
            return m
        else:
            return super().create_missing_domain(name)

    def get_io_buffer(self, buffer):
        if isinstance(buffer, io.Buffer):
            result = IOBuffer(buffer.direction, buffer.port)
        elif isinstance(buffer, io.FFBuffer):
            result = FFBuffer(buffer.direction, buffer.port,
                              i_domain=buffer.i_domain,
                              o_domain=buffer.o_domain)
        elif isinstance(buffer, io.DDRBuffer):
            result = DDRBuffer(buffer.direction, buffer.port,
                               i_domain=buffer.i_domain,
                               o_domain=buffer.o_domain)
        else:
            raise TypeError(f"Unsupported buffer type {buffer!r}") # :nocov:
        if buffer.direction is not io.Direction.Output:
            result.i = buffer.i
        if buffer.direction is not io.Direction.Input:
            result.o = buffer.o
            result.oe = buffer.oe
        return result

    # The altera_std_synchronizer{,_bundle} megafunctions embed SDC constraints that mark false
    # paths, so use them instead of our default implementation.

    def get_ff_sync(self, ff_sync):
        return Instance("altera_std_synchronizer_bundle",
            p_width=len(ff_sync.i),
            p_depth=ff_sync._stages,
            i_clk=ClockSignal(ff_sync._o_domain),
            i_reset_n=Const(1),
            i_din=ff_sync.i,
            o_dout=ff_sync.o,
        )

    def get_async_ff_sync(self, async_ff_sync):
        m = Module()
        sync_output = Signal()
        m.submodules += RequirePosedge(async_ff_sync._o_domain)
        if async_ff_sync._edge == "pos":
            m.submodules += Instance("altera_std_synchronizer",
                p_depth=async_ff_sync._stages,
                i_clk=ClockSignal(async_ff_sync._o_domain),
                i_reset_n=~async_ff_sync.i,
                i_din=Const(1),
                o_dout=sync_output,
            )
        else:
            m.submodules += Instance("altera_std_synchronizer",
                p_depth=async_ff_sync._stages,
                i_clk=ClockSignal(async_ff_sync._o_domain),
                i_reset_n=async_ff_sync.i,
                i_din=Const(1),
                o_dout=sync_output,
            )
        m.d.comb += async_ff_sync.o.eq(~sync_output)
        return m
