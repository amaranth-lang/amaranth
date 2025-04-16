from abc import abstractmethod

from ..hdl import *
from ..build import *


class IntelPlatform(TemplatedPlatform):
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
        * ``script_after_read``: inserts commands after ``read_rtlil`` in Yosys script.
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
            # {{autogenerated}}
            {% for var in platform._all_toolchain_env_vars %}
            if [ -n "${{var}}" ]; then
                QUARTUS_ROOTDIR=$(dirname $(dirname "${{var}}"))
                # Quartus' qenv.sh does not work with `set -e`.
                . "${{var}}"
            fi
            {% endfor %}
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
            {% for net_signal, port_signal, frequency in platform.iter_clock_constraints() -%}
                {% if port_signal is not none -%}
                    create_clock -name {{port_signal.name|tcl_quote}} -period {{1000000000/frequency}} [get_ports {{port_signal.name|tcl_quote}}]
                {% else -%}
                    create_clock -name {{net_signal.name|tcl_quote}} -period {{1000000000/frequency}} [get_nets {{net_signal|hierarchy("|")|tcl_quote}}]
                {% endif %}
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
                read_rtlil {{file}}
            {% endfor %}
            read_rtlil {{name}}.il
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

    # The altiobuf_* and altddio_* primitives are explained in the following Intel documents:
    # * https://www.intel.com/content/dam/www/programmable/us/en/pdfs/literature/ug/ug_altiobuf.pdf
    # * https://www.intel.com/content/dam/www/programmable/us/en/pdfs/literature/ug/ug_altddio.pdf
    # See also errata mentioned in: https://www.intel.com/content/www/us/en/programmable/support/support-resources/knowledge-base/solutions/rd11192012_735.html.

    @staticmethod
    def _get_ireg(m, pin, invert):
        def get_ineg(i):
            if invert:
                i_neg = Signal.like(i, name_suffix="_neg")
                m.d.comb += i.eq(~i_neg)
                return i_neg
            else:
                return i

        if pin.xdr == 0:
            return get_ineg(pin.i)
        elif pin.xdr == 1:
            i_sdr = Signal(pin.width, name="{}_i_sdr")
            m.submodules += Instance("$dff",
                p_CLK_POLARITY=1,
                p_WIDTH=pin.width,
                i_CLK=pin.i_clk,
                i_D=i_sdr,
                o_Q=get_ineg(pin.i),
            )
            return i_sdr
        elif pin.xdr == 2:
            i_ddr = Signal(pin.width, name=f"{pin.name}_i_ddr")
            m.submodules[f"{pin.name}_i_ddr"] = Instance("altddio_in",
                p_width=pin.width,
                i_datain=i_ddr,
                i_inclock=pin.i_clk,
                o_dataout_h=get_ineg(pin.i0),
                o_dataout_l=get_ineg(pin.i1),
            )
            return i_ddr
        assert False

    @staticmethod
    def _get_oreg(m, pin, invert):
        def get_oneg(o):
            if invert:
                o_neg = Signal.like(o, name_suffix="_neg")
                m.d.comb += o_neg.eq(~o)
                return o_neg
            else:
                return o

        if pin.xdr == 0:
            return get_oneg(pin.o)
        elif pin.xdr == 1:
            o_sdr = Signal(pin.width, name=f"{pin.name}_o_sdr")
            m.submodules += Instance("$dff",
                p_CLK_POLARITY=1,
                p_WIDTH=pin.width,
                i_CLK=pin.o_clk,
                i_D=get_oneg(pin.o),
                o_Q=o_sdr,
            )
            return o_sdr
        elif pin.xdr == 2:
            o_ddr = Signal(pin.width, name=f"{pin.name}_o_ddr")
            m.submodules[f"{pin.name}_o_ddr"] = Instance("altddio_out",
                p_width=pin.width,
                o_dataout=o_ddr,
                i_outclock=pin.o_clk,
                i_datain_h=get_oneg(pin.o0),
                i_datain_l=get_oneg(pin.o1),
            )
            return o_ddr
        assert False

    @staticmethod
    def _get_oereg(m, pin):
        # altiobuf_ requires an output enable signal for each pin, but pin.oe is 1 bit wide.
        if pin.xdr == 0:
            return pin.oe.replicate(pin.width)
        elif pin.xdr in (1, 2):
            oe_reg = Signal(pin.width, name=f"{pin.name}_oe_reg")
            oe_reg.attrs["useioff"] = "1"
            m.submodules += Instance("$dff",
                p_CLK_POLARITY=1,
                p_WIDTH=pin.width,
                i_CLK=pin.o_clk,
                i_D=pin.oe,
                o_Q=oe_reg,
            )
            return oe_reg
        assert False

    def get_input(self, pin, port, attrs, invert):
        self._check_feature("single-ended input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_in",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            i_datain=port.io,
            o_dataout=self._get_ireg(m, pin, invert)
        )
        return m

    def get_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            p_use_oe="FALSE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=port.io,
        )
        return m

    def get_tristate(self, pin, port, attrs, invert):
        self._check_feature("single-ended tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            p_use_oe="TRUE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=port.io,
            i_oe=self._get_oereg(m, pin)
        )
        return m

    def get_input_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_bidir",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="FALSE",
            i_datain=self._get_oreg(m, pin, invert),
            io_dataio=port.io,
            o_dataout=self._get_ireg(m, pin, invert),
            i_oe=self._get_oereg(m, pin),
        )
        return m

    def get_diff_input(self, pin, port, attrs, invert):
        self._check_feature("differential input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.p.attrs["useioff"] = 1
            port.n.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_in",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            i_datain=port.p,
            i_datain_b=port.n,
            o_dataout=self._get_ireg(m, pin, invert)
        )
        return m

    def get_diff_output(self, pin, port, attrs, invert):
        self._check_feature("differential output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.p.attrs["useioff"] = 1
            port.n.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            p_use_oe="FALSE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=port.p,
            o_dataout_b=port.n,
        )
        return m

    def get_diff_tristate(self, pin, port, attrs, invert):
        self._check_feature("differential tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.p.attrs["useioff"] = 1
            port.n.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_out",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            p_use_oe="TRUE",
            i_datain=self._get_oreg(m, pin, invert),
            o_dataout=port.p,
            o_dataout_b=port.n,
            i_oe=self._get_oereg(m, pin),
        )
        return m

    def get_diff_input_output(self, pin, port, attrs, invert):
        self._check_feature("differential input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        if pin.xdr == 1:
            port.p.attrs["useioff"] = 1
            port.n.attrs["useioff"] = 1

        m = Module()
        m.submodules[pin.name] = Instance("altiobuf_bidir",
            p_enable_bus_hold="FALSE",
            p_number_of_channels=pin.width,
            p_use_differential_mode="TRUE",
            i_datain=self._get_oreg(m, pin, invert),
            io_dataio=port.p,
            io_dataio_b=port.n,
            o_dataout=self._get_ireg(m, pin, invert),
            i_oe=self._get_oereg(m, pin),
        )
        return m

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
