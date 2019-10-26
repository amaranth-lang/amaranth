from abc import abstractproperty

from ..hdl import *
from ..build import *


__all__ = ["LatticeMachXO2Platform"]


class LatticeMachXO2Platform(TemplatedPlatform):
    """
    Required tools:
        * ``pnmainc``
        * ``ddtcmd``

    The environment is populated by running the script specified in the environment variable
    ``NMIGEN_ENV_Diamond``, if present.

    Available overrides:
        * ``script_project``: inserts commands before ``prj_project save`` in Tcl script.
        * ``script_after_export``: inserts commands after ``prj_run Export`` in Tcl script.
        * ``add_preferences``: inserts commands at the end of the LPF file.
        * ``add_constraints``: inserts commands at the end of the XDC file.

    Build products:
        * ``{{name}}_impl/{{name}}_impl.htm``: consolidated log.
        * ``{{name}}.jed``: JEDEC fuse file.
        * ``{{name}}.svf``: JTAG programming vector.
    """

    toolchain = "Diamond"

    device  = abstractproperty()
    package = abstractproperty()
    speed   = abstractproperty()
    grade   = "C" # [C]ommercial, [I]ndustrial

    required_tools = [
        "yosys",
        "pnmainc",
        "ddtcmd"
    ]
    file_templates = {
        **TemplatedPlatform.build_script_templates,
        "build_{{name}}.sh": r"""
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
            prj_project new -name {{name}} -impl impl -impl_dir top_impl \
                -dev {{platform.device}}-{{platform.speed}}{{platform.package}}{{platform.grade}} \
                -lpf {{name}}.lpf \
                -synthesis synplify
            {% for file in platform.iter_extra_files(".v", ".sv", ".vhd", ".vhdl") -%}
                prj_src add "{{file}}"
            {% endfor %}
            prj_src add {{name}}.v
            prj_impl option top {{name}}
            prj_src add {{name}}.sdc
            {{get_override("script_project")|default("# (script_project placeholder)")}}
            prj_project save
            prj_run Synthesis -impl impl -forceAll
            prj_run Translate -impl impl -forceAll
            prj_run Map -impl impl -forceAll
            prj_run PAR -impl impl -forceAll
            prj_run Export -impl impl -forceAll -task Jedecgen
            {{get_override("script_after_export")|default("# (script_after_export placeholder)")}}
        """,
        "{{name}}.lpf": r"""
            # {{autogenerated}}
            BLOCK ASYNCPATHS;
            BLOCK RESETPATHS;
            {% for port_name, pin_name, extras in platform.iter_port_constraints_bits() -%}
                LOCATE COMP "{{port_name}}" SITE "{{pin_name}}";
                {% if extras -%}
                IOBUF PORT "{{port_name}}"
                    {%- for key, value in extras.items() %} {{key}}={{value}}{% endfor %};
                {% endif %}
            {% endfor %}
            {% for signal, frequency in platform.iter_clock_constraints() -%}
                FREQUENCY NET "{{signal|hierarchy("/")}}" {{frequency/1000000}} MHZ;
            {% endfor %}
            {{get_override("add_preferences")|default("# (add_preferences placeholder)")}}
        """,
        "{{name}}.sdc": r"""
            {% for signal, frequency in platform.iter_clock_constraints() -%}
                create_clock -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("/")}}]
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """,
    }
    command_templates = [
        # These don't have any usable command-line option overrides.
        r"""
        {{invoke_tool("pnmainc")}}
            {{name}}.tcl
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
            -if {{name}}_impl/{{name}}_impl.jed -of {{name}}.svf
        """,
    ]

    def create_missing_domain(self, name):
        # Lattice MachXO2 devices have two global set/reset signals: PUR, which is driven at
        # startup by the configuration logic and unconditionally resets every storage element,
        # and GSR, which is driven by user logic and each storage element may be configured as
        # affected or unaffected by GSR. PUR is purely asynchronous, so even though it is
        # a low-skew global network, its deassertion may violate a setup/hold constraint with
        # relation to a user clock. To avoid this, a GSR/SGSR instance should be driven
        # synchronized to user clock.
        if name == "sync" and self.default_clk is not None:
            clk_i = self.request(self.default_clk).i
            if self.default_rst is not None:
                rst_i = self.request(self.default_rst).i
            else:
                rst_i = Const(0)

            gsr0 = Signal()
            gsr1 = Signal()
            m = Module()
            # There is no end-of-startup signal on MachXO2, but PUR is released after IOB enable,
            # so a simple reset synchronizer (with PUR as the asynchronous reset) does the job.
            m.submodules += [
                Instance("FD1S3AX", p_GSR="DISABLED", i_CK=clk_i, i_D=~rst_i, o_Q=gsr0),
                Instance("FD1S3AX", p_GSR="DISABLED", i_CK=clk_i, i_D=gsr0,   o_Q=gsr1),
                # Although we already synchronize the reset input to user clock, SGSR has dedicated
                # clock routing to the center of the FPGA; use that just in case it turns out to be
                # more reliable. (None of this is documented.)
                Instance("SGSR", i_CLK=clk_i, i_GSR=gsr1),
            ]
            # GSR implicitly connects to every appropriate storage element. As such, the sync
            # domain is reset-less; domains driven by other clocks would need to have dedicated
            # reset circuitry or otherwise meet setup/hold constraints on their own.
            m.domains += ClockDomain("sync", reset_less=True)
            m.d.comb += ClockSignal("sync").eq(clk_i)
            return m

    _single_ended_io_types = [
        "PCI33", "LVTTL33", "LVCMOS33", "LVCMOS25", "LVCMOS18", "LVCMOS15", "LVCMOS12",
        "LVCMOS25R33", "LVCMOS18R33", "LVCMOS18R25", "LVCMOS15R33", "LVCMOS15R25", "LVCMOS12R33",
        "LVCMOS12R25", "LVCMOS10R33", "LVCMOS10R25", "SSTL25_I", "SSTL25_II", "SSTL18_I",
        "SSTL18_II", "HSTL18_I", "HSTL18_II",
    ]
    _differential_io_types = [
        "LVDS25", "LVDS25E", "RSDS25", "RSDS25E", "BLVDS25", "BLVDS25E", "MLVDS25", "MLVDS25E",
        "LVPECL33", "LVPECL33E", "SSTL25D_I", "SSTL25D_II", "SSTL18D_I", "SSTL18D_II",
        "HSTL18D_I", "HSTL18D_II", "LVTTL33D", "LVCMOS33D", "LVCMOS25D", "LVCMOS18D", "LVCMOS15D",
        "LVCMOS12D", "MIPI",
    ]

    def should_skip_port_component(self, port, attrs, component):
        # On ECP5, a differential IO is placed by only instantiating an IO buffer primitive at
        # the PIOA or PIOC location, which is always the non-inverting pin.
        if attrs.get("IO_TYPE", "LVCMOS25") in self._differential_io_types and component == "n":
            return True
        return False

    def _get_xdr_buffer(self, m, pin, *, i_invert=False, o_invert=False):
        def get_ireg(clk, d, q):
            for bit in range(len(q)):
                m.submodules += Instance("IFS1P3DX",
                    i_SCLK=clk,
                    i_SP=Const(1),
                    i_CD=Const(0),
                    i_D=d[bit],
                    o_Q=q[bit]
                )

        def get_oreg(clk, d, q):
            for bit in range(len(q)):
                m.submodules += Instance("OFS1P3DX",
                    i_SCLK=clk,
                    i_SP=Const(1),
                    i_CD=Const(0),
                    i_D=d[bit],
                    o_Q=q[bit]
                )

        def get_iddr(sclk, d, q0, q1):
            for bit in range(len(d)):
                m.submodules += Instance("IDDRXE",
                    i_SCLK=sclk,
                    i_RST=Const(0),
                    i_D=d[bit],
                    o_Q0=q0[bit], o_Q1=q1[bit]
                )

        def get_oddr(sclk, d0, d1, q):
            for bit in range(len(q)):
                m.submodules += Instance("ODDRXE",
                    i_SCLK=sclk,
                    i_RST=Const(0),
                    i_D0=d0[bit], i_D1=d1[bit],
                    o_Q=q[bit]
                )

        def get_ineg(z, invert):
            if invert:
                a = Signal.like(z, name_suffix="_n")
                m.d.comb += z.eq(~a)
                return a
            else:
                return z

        def get_oneg(a, invert):
            if invert:
                z = Signal.like(a, name_suffix="_n")
                m.d.comb += z.eq(~a)
                return z
            else:
                return a

        if "i" in pin.dir:
            if pin.xdr < 2:
                pin_i  = get_ineg(pin.i,  i_invert)
            elif pin.xdr == 2:
                pin_i0 = get_ineg(pin.i0, i_invert)
                pin_i1 = get_ineg(pin.i1, i_invert)
        if "o" in pin.dir:
            if pin.xdr < 2:
                pin_o  = get_oneg(pin.o,  o_invert)
            elif pin.xdr == 2:
                pin_o0 = get_oneg(pin.o0, o_invert)
                pin_o1 = get_oneg(pin.o1, o_invert)

        i = o = t = None
        if "i" in pin.dir:
            i = Signal(pin.width, name="{}_xdr_i".format(pin.name))
        if "o" in pin.dir:
            o = Signal(pin.width, name="{}_xdr_o".format(pin.name))
        if pin.dir in ("oe", "io"):
            t = Signal(1,         name="{}_xdr_t".format(pin.name))

        if pin.xdr == 0:
            if "i" in pin.dir:
                i = pin_i
            if "o" in pin.dir:
                o = pin_o
            if pin.dir in ("oe", "io"):
                t = ~pin.oe
        elif pin.xdr == 1:
            # Note that currently nextpnr will not pack an FF (*FS1P3DX) into the PIO.
            if "i" in pin.dir:
                get_ireg(pin.i_clk, i, pin_i)
            if "o" in pin.dir:
                get_oreg(pin.o_clk, pin_o, o)
            if pin.dir in ("oe", "io"):
                get_oreg(pin.o_clk, ~pin.oe, t)
        elif pin.xdr == 2:
            if "i" in pin.dir:
                get_iddr(pin.i_clk, i, pin_i0, pin_i1)
            if "o" in pin.dir:
                get_oddr(pin.o_clk, pin_o0, pin_o1, o)
            if pin.dir in ("oe", "io"):
                # It looks like Diamond will not pack an OREG as a tristate register in a DDR PIO.
                # It is not clear what is the recommended set of primitives for this task.
                # Similarly, nextpnr will not pack anything as a tristate register in a DDR PIO.
                get_oreg(pin.o_clk, ~pin.oe, t)
        else:
            assert False

        return (i, o, t)

    def get_input(self, pin, port, attrs, invert):
        self._check_feature("single-ended input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert)
        for bit in range(len(port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("IB",
                i_I=port[bit],
                o_O=i[bit]
            )
        return m

    def get_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(len(port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OB",
                i_I=o[bit],
                o_O=port[bit]
            )
        return m

    def get_tristate(self, pin, port, attrs, invert):
        self._check_feature("single-ended tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(len(port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OBZ",
                i_T=t,
                i_I=o[bit],
                o_O=port[bit]
            )
        return m

    def get_input_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert, o_invert=invert)
        for bit in range(len(port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("BB",
                i_T=t,
                i_I=o[bit],
                o_O=i[bit],
                io_B=port[bit]
            )
        return m

    def get_diff_input(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("IB",
                i_I=p_port[bit],
                o_O=i[bit]
            )
        return m

    def get_diff_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OB",
                i_I=o[bit],
                o_O=p_port[bit],
            )
        return m

    def get_diff_tristate(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OBZ",
                i_T=t,
                i_I=o[bit],
                o_O=p_port[bit],
            )
        return m

    def get_diff_input_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert, o_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("BB",
                i_T=t,
                i_I=o[bit],
                o_O=i[bit],
                io_B=p_port[bit],
            )
        return m

    # CDC primitives are not currently specialized for MachXO2.