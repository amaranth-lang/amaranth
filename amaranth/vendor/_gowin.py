from abc import abstractproperty
from fractions import Fraction
import math
import re

from ..hdl import *
from ..lib.cdc import ResetSynchronizer
from ..build import *

# Acknowledgments:
#   Parts of this file originate from https://github.com/tcjie/Gowin


class GowinPlatform(TemplatedPlatform):
    """
    .. rubric:: Apicula toolchain

    Required tools:
        * ``yosys``
        * ``nextpnr-gowin``
        * ``gowin_pack``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_APICULA``, if present.

    Build products:
        * ``{{name}}.fs``: binary bitstream.

    .. rubric:: Gowin toolchain

    Required tools:
        * ``gw_sh``

    The environment is populated by running the script specified in the environment variable
    ``AMARANTH_ENV_GOWIN``, if present.

    Build products:
        * ``{{name}}.fs``: binary bitstream.
    """

    toolchain = None # selected when creating platform

    part   = abstractproperty()
    family = abstractproperty()

    def parse_part(self):
        # These regular expressions match all >900 parts of Gowin device_info.csv
        reg_series    = r"(GW[12]{1}[AN]{1}[EFNRSZ]{0,3})-"
        reg_voltage   = r"(ZV|EV|LV|LX|UV|UX)"
        reg_size      = r"(1|2|4|9|18|55)"
        reg_subseries = r"(?:(B|C|S|X|P5)?)"
        reg_package   = r"((?:PG|UG|EQ|LQ|MG|M|QN|CS|FN)(?:\d+)(?:P?)(?:A|E|M|CF|C|D|G|H|F|S|T|U|X)?)"
        reg_speed     = r"((?:C\d{1}/I\d{1})|ES|A\d{1}|I\d{1})"

        match = re.match(reg_series+reg_voltage+reg_size+reg_subseries+reg_package+reg_speed+"$",
                         self.part)
        if not match:
            raise ValueError("Supplied part name is invalid")

        self.series    = match.group(1)
        self.voltage   = match.group(2)
        self.size      = match.group(3)
        self.subseries = match.group(4) or ""
        self.package   = match.group(5)
        self.speed     = match.group(6)

        match = re.match(reg_series+reg_size+reg_subseries+"$", self.family)
        if not match:
            raise ValueError("Supplied device family name is invalid")

        self.series_f    = match.group(1)
        self.size_f      = match.group(2)
        self.subseries_f = match.group(3) or ""

        # subseries_f is usually more reliable than subseries.

        if self.series != self.series_f:
            raise ValueError("Series extracted from supplied part name does not match "
                             "supplied family series")
        if self.size != self.size_f:
            raise ValueError("Size extracted from supplied part name does not match "
                             "supplied family size")

    # _chipdb_device is tied to available chipdb-*.bin files of nextpnr-gowin
    @property
    def _chipdb_device(self):
        # GW1NR series does not have its own chipdb file, but works with GW1N
        if self.series == "GW1NR":
            return f"GW1N-{self.size}{self.subseries_f}"
        return self.family

    _dev_osc_mapping = {
       "GW1N-1" : "OSCH",
       "GW1N-1P5" : "OSCO",
       "GW1N-1P5B" : "OSCO",
       "GW1N-1S" : "OSCH",
       "GW1N-2" : "OSCO",
       "GW1N-2B" : "OSCO",
       "GW1N-4" : "OSC",
       "GW1N-4B" : "OSC",
       "GW1N-9" : "OSC",
       "GW1N-9C" : "OSC",
       "GW1NR-1" : "OSCH",
       "GW1NR-2" : "OSCO",
       "GW1NR-2B" : "OSCO",
       "GW1NR-4" : "OSC",
       "GW1NR-4B" : "OSC",
       "GW1NR-9" : "OSC",
       "GW1NR-9C" : "OSC",
       "GW1NRF-4B" : "OSC",
       "GW1NS-2" : "OSCF",
       "GW1NS-2C" : "OSCF",
       "GW1NS-4" : "OSCZ",
       "GW1NS-4C" : "OSCZ",
       "GW1NSE-2C" : "OSCF",
       "GW1NSER-4C" : "OSCZ",
       "GW1NSR-2" : "OSCF",
       "GW1NSR-2C" : "OSCF",
       "GW1NSR-4" : "OSCZ",
       "GW1NSR-4C" : "OSCZ",
       "GW1NZ-1" : "OSCZ",
       "GW1NZ-1C" : "OSCZ",
       "GW2A-18" : "OSC",
       "GW2A-18C" : "OSC",
       "GW2A-55" : "OSC",
       "GW2A-55C" : "OSC",
       "GW2AN-18X" : "OSCW",
       "GW2AN-55C" : "OSC",
       "GW2AN-9X" : "OSCW",
       "GW2ANR-18C" : "OSC",
       "GW2AR-18" : "OSC",
       "GW2AR-18C" : "OSC"
    }

    @property
    def _osc_type(self):
        if self.family in self._dev_osc_mapping:
            return self._dev_osc_mapping[self.family]
        raise NotImplementedError("Device family {} does not have an assigned oscillator type"
                                  .format(self.family))

    @property
    def _osc_base_freq(self):
        osc = self._osc_type
        if osc == "OSC":
            if self.speed == 4 and self.subseries_f in ("B", "D"):
                return 210_000_000
            else:
                return 250_000_000
        elif osc in ("OSCZ", "OSCO"):
            if self.series == "GW1NSR" and self.speed == "C7/I6":
                return 260_000_000
            else:
                return 250_000_000
        elif osc in ("OSCF", "OSCH"):
            return 240_000_000
        elif osc == "OSCW":
            return 200_000_000
        else:
            assert False

    @property
    def _osc_div(self):
        div_range = range(2, 130, 2)
        div_frac  = Fraction(self._osc_base_freq, self.osc_frequency)

        # Check that the requested frequency is within 50 ppm. This takes care of small mismatches
        # arising due to rounding. The tolerance of a typical crystal oscillator is 50 ppm.
        if (abs(round(div_frac) - div_frac) > Fraction(50, 1_000_000) or
                int(div_frac) not in div_range):
            achievable = (
                min((frac for frac in div_range if frac > div_frac), default=None),
                max((frac for frac in div_range if frac < div_frac), default=None)
            )
            raise ValueError(
                f"On-chip oscillator frequency (platform.osc_frequency) must be chosen such that "
                f"the base frequency of {self._osc_base_freq} Hz is divided by an integer factor "
                f"between {div_range.start} and {div_range.stop} in steps of {div_range.step}; "
                f"the divider for the requested frequency of {self.osc_frequency} Hz was "
                f"calculated as ({div_frac.numerator}/{div_frac.denominator}), and the closest "
                f"achievable frequencies are " +
                ", ".join(str(self._osc_base_freq // frac) for frac in achievable if frac))

        return int(div_frac)

    # Common templates

    _common_file_templates = {
        "{{name}}.cst": r"""
            // {{autogenerated}}
            {% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
                IO_LOC "{{port_name}}" {{pin_name}};
                {% for attr_name, attr_value in attrs.items() -%}
                    IO_PORT "{{port_name}}" {{attr_name}}={{attr_value}};
                {% endfor %}
            {% endfor %}
        """,
    }

    # Apicula templates

    _apicula_required_tools = [
        "yosys",
        "nextpnr-gowin",
        "gowin_pack"
    ]
    _apicula_file_templates = {
        **TemplatedPlatform.build_script_templates,
        **_common_file_templates,
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
            synth_gowin {{get_override("synth_opts")|options}} -top {{name}} -json {{name}}.syn.json
            {{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
        """,
    }
    _apicula_command_templates = [
        r"""
        {{invoke_tool("yosys")}}
            {{quiet("-q")}}
            {{get_override("yosys_opts")|options}}
            -l {{name}}.rpt
            {{name}}.ys
        """,
        r"""
        {{invoke_tool("nextpnr-gowin")}}
            {{quiet("--quiet")}}
            {{get_override("nextpnr_opts")|options}}
            --log {{name}}.tim
            --device {{platform.part}}
            --family {{platform._chipdb_device}}
            --json {{name}}.syn.json
            --cst {{name}}.cst
            --write {{name}}.pnr.json
        """,
        r"""
        {{invoke_tool("gowin_pack")}}
            -d {{platform._chipdb_device}}
            -o {{name}}.fs
            {{get_override("gowin_pack_opts")|options}}
            {{name}}.pnr.json
        """
    ]

    # Vendor toolchain templates

    _gowin_required_tools = ["gw_sh"]
    _gowin_file_templates = {
        **TemplatedPlatform.build_script_templates,
        **_common_file_templates,
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_verilog()}}
        """,
        "{{name}}.tcl": r"""
            # {{autogenerated}}
            {% for file in platform.iter_files(".v",".sv",".vhd",".vhdl") -%}
                add_file {{file}}
            {% endfor %}
            add_file -type verilog {{name}}.v
            add_file -type cst {{name}}.cst
            add_file -type sdc {{name}}.sdc
            set_device -name {{platform.family}} {{platform.part}}
            set_option -verilog_std v2001 -print_all_synthesis_warning 1 -show_all_warn 1
            {{get_override("add_options")|default("# (add_options placeholder)")}}
            run all
            file delete -force {{name}}.fs
            file copy -force impl/pnr/project.fs {{name}}.fs
        """,
        "{{name}}.sdc": r"""
        // {{autogenerated}}
        {% for net_signal,port_signal,frequency in platform.iter_clock_constraints() -%}
            create_clock -name {{port_signal.name|tcl_escape}} -period {{1000000000/frequency}}  [get_ports {{port_signal.name|tcl_escape}}]
        {% endfor %}
        {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """,
    }
    _gowin_command_templates = [
        r"""
        {{invoke_tool("gw_sh")}}
            {{name}}.tcl
        """
    ]

    def __init__(self, *, toolchain="Apicula"):
        super().__init__()

        assert toolchain in ("Apicula", "Gowin")
        self.toolchain = toolchain

        self.parse_part()

    @property
    def required_tools(self):
        if self.toolchain == "Apicula":
            return self._apicula_required_tools
        elif self.toolchain == "Gowin":
            return self._gowin_required_tools
        assert False

    @property
    def file_templates(self):
        if self.toolchain == "Apicula":
            return self._apicula_file_templates
        elif self.toolchain == "Gowin":
            return self._gowin_file_templates
        assert False

    @property
    def command_templates(self):
        if self.toolchain == "Apicula":
            return self._apicula_command_templates
        elif self.toolchain == "Gowin":
            return self._gowin_command_templates
        assert False

    def add_clock_constraint(self, clock, frequency):
        super().add_clock_constraint(clock, frequency)
        clock.attrs["keep"] = "true"

    @property
    def default_clk_constraint(self):
        if self.default_clk == "OSC":
            if not hasattr(self, "osc_frequency"):
                raise AttributeError(
                    "Using the on-chip oscillator as the default clock source requires "
                    "the platform.osc_frequency attribute to be set")
            return Clock(self.osc_frequency)

        # Use the defined Clock resource.
        return super().default_clk_constraint

    def create_missing_domain(self, name):
        if name == "sync" and self.default_clk is not None:
            m = Module()

            if self.default_clk == "OSC":
                clk_i = Signal()
                if self._osc_type == "OSCZ":
                    m.submodules += Instance(self._osc_type,
                                             p_FREQ_DIV=self._osc_div,
                                             i_OSCEN=Const(1),
                                             o_OSCOUT=clk_i)
                elif self._osc_type == "OSCO":
                    # TODO: Make use of regulator configurable
                    m.submodules += Instance(self._osc_type,
                                             p_REGULATOR_EN=Const(1),
                                             p_FREQ_DIV=self._osc_div,
                                             i_OSCEN=Const(1),
                                             o_OSCOUT=clk_i)
                elif self._osc_type == "OSCF":
                    m.submodules += Instance(self._osc_type,
                                             p_FREQ_DIV=self._osc_div,
                                             o_OSCOUT30M=None,
                                             o_OSCOUT=clk_i)
                else:
                    m.submodules += Instance(self._osc_type,
                                             p_FREQ_DIV=self._osc_div,
                                             o_OSCOUT=clk_i)

            else:
                clk_i = self.request(self.default_clk).i

            if self.default_rst is not None:
                rst_i = self.request(self.default_rst).i
            else:
                rst_i = Const(0)

            m.submodules.reset_sync = ResetSynchronizer(rst_i, domain="sync")
            m.domains += ClockDomain("sync")
            m.d.comb += ClockSignal("sync").eq(clk_i)

            return m

    def _get_xdr_buffer(self, m, pin, i_invert=False, o_invert=False):

        def get_ireg(clk,d,q):
            for bit in range(len(q)):
                m.submodules += Instance("DFF",
                    i_CLK=clk,
                    i_D=d[bit],
                    o_Q=q[bit],
                )

        def get_oreg(clk,d,q):
            for bit in range(len(q)):
                m.submodules += Instance("DFF",
                    i_CLK=clk,
                    i_D=d[bit],
                    o_Q=q[bit]
                )

        def get_iddr(clk,d,q0,q1):
            for bit in range(len(d)):
                m.submodules += Instance("IDDR",
                    i_CLK=clk,
                    i_D=d[bit],
                    o_Q0=q0[bit],
                    o_Q1=q1[bit]
                )

        def get_oddr(clk,d0,d1,q):
            for bit in range(len(q)):
                m.submodules += Instance("ODDR",
                    p_TXCLK_POL=0, # default -> Q1 changes on posedge of CLK
                    i_CLK=clk,
                    i_D0=d0[bit],
                    i_D1=d1[bit],
                    o_Q0=q[bit]
                )

        def get_oeddr(clk,d0,d1,tx,q0,q1):
            for bit in range(len(q0)):
                m.submodules += Instance("ODDR",
                    p_TXCLK_POL=0, # default -> Q1 changes on posedge of CLK
                    i_CLK=clk,
                    i_D0=d0[bit],
                    i_D1=d1[bit],
                    i_TX=tx,
                    o_Q0=q0[bit],
                    o_Q1=q1
                )

        def get_ineg(y, invert):
            if invert:
                a = Signal.like(y, name_suffix="_n")
                m.d.comb += y.eq(~a)
                return a
            else:
                return y

        def get_oneg(a, invert):
            if invert:
                y = Signal.like(a, name_suffix="_n")
                m.d.comb += y.eq(~a)
                return y
            else:
                return a


        if "i" in pin.dir:
            if pin.xdr < 2:
                pin_i = get_ineg(pin.i, i_invert)
            elif pin.xdr == 2:
                pin_i0 = get_ineg(pin.i0, i_invert)
                pin_i1 = get_ineg(pin.i1, i_invert)
        if "o" in pin.dir:
            if pin.xdr < 2:
                pin_o = get_oneg(pin.o, o_invert)
            elif pin.xdr == 2:
                pin_o0 = get_oneg(pin.o0, o_invert)
                pin_o1 = get_oneg(pin.o1, o_invert)

        i = o = t = None

        if "i" in pin.dir:
            i = Signal(pin.width, name=f"{pin.name}_xdr_i")
        if "o" in pin.dir:
            o = Signal(pin.width, name=f"{pin.name}_xdr_o")
        if pin.dir in ("oe", "io"):
            t = Signal(1,         name=f"{pin.name}_xdr_t")

        if pin.xdr == 0:
            if "i" in pin.dir:
                i = pin_i
            if "o" in pin.dir:
                o = pin_o
            if pin.dir in ("oe", "io"):
                t = ~pin.oe
        elif pin.xdr == 1:
            if "i" in pin.dir:
                get_ireg(pin.i_clk, i, pin_i)
            if "o" in pin.dir:
                get_oreg(pin.o_clk, pin_o, o)
            if pin.dir in ("oe", "io"):
                get_oreg(pin.o_clk, ~pin.oe, t)
        elif pin.xdr == 2:
            if "i" in pin.dir:
                get_iddr(pin.i_clk, i, pin_i0, pin_i1)
            if pin.dir in ("o",):
                get_oddr(pin.o_clk, pin_o0, pin_o1, o)
            if pin.dir in ("oe", "io"):
                get_oeddr(pin.o_clk, pin_o0, pin_o1, ~pin.oe, o, t)
        else:
            assert False

        return (i, o, t)

    def get_input(self, pin, port, attrs, invert):
        self._check_feature("single-ended input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert)
        for bit in range(pin.width):
            m.submodules[f"{pin.name}_{bit}"] = Instance("IBUF",
                i_I=port.io[bit],
                o_O=i[bit]
            )
        return m

    def get_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, port.io, o_invert=invert)
        for bit in range(pin.width):
            m.submodules[f"{pin.name}_{bit}"] = Instance("OBUF",
                i_I=o[bit],
                o_O=port.io[bit]
            )
        return m

    def get_tristate(self, pin, port, attrs, invert):
        self._check_feature("single-ended tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(pin.width):
            m.submodules[f"{pin.name}_{bit}"] = Instance("TBUF",
                i_OEN=t,
                i_I=o[bit],
                o_O=port.io[bit]
            )
        return m

    def get_input_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert, o_invert=invert)
        for bit in range(pin.width):
            m.submodules[f"{pin.name}_{bit}"] = Instance("IOBUF",
                i_OEN=t,
                i_I=o[bit],
                o_O=i[bit],
                io_IO=port.io[bit]
            )
        return m

    def get_diff_input(self, pin, port, attrs, invert):
        self._check_feature("differential input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert)
        for bit in range(pin.wodth):
            m.submodules[f"{pin.name}_{bit}"] = Instance("TLVDS_IBUF",
                i_I=port.p[bit],
                i_IB=port.n[bit],
                o_O=i[bit]
            )
        return m

    def get_diff_output(self, pin, port, attrs, invert):
        self._check_feature("differential output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(pin.width):
            m.submodules[f"{pin.name}_{bit}"] = Instance("TLVDS_OBUF",
                i_I=o[bit],
                o_O=port.p[bit],
                o_OB=port.n[bit],
            )
        return m

    def get_diff_tristate(self, pin, port, attrs, invert):
        self._check_feature("differential tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(pin.width):
            m.submodules[f"{pin.name}_{bit}"] = Instance("TLVDS_TBUF",
                i_OEN=t,
                i_I=o[bit],
                o_O=port.p[bit],
                o_OB=port.n[bit]
            )
        return m

    def get_diff_input_output(self, pin, port, attrs, invert):
        self._check_feature("differential input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert, o_invert=invert)
        for bit in range(pin.width):
            m.submodules[f"{pin.name}_{bit}"] = Instance("TLVDS_IOBUF",
                i_OEN=t,
                i_I=o[bit],
                o_O=i[bit],
                io_IO=port.p[bit],
                io_IOB=port.n[bit]
            )
        return m
