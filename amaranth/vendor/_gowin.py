from abc import abstractproperty
from fractions import Fraction
import math
import re

from ..hdl import *
from ..hdl._ir import RequirePosedge
from ..lib import io, wiring
from ..lib.cdc import ResetSynchronizer
from ..build import *

# Acknowledgments:
#   Parts of this file originate from https://github.com/tcjie/Gowin


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
                    m.submodules[name] = Instance("TBUF",
                        i_OEN=self.t[bit],
                        i_I=self.o[bit],
                        o_O=self.port.io[bit],
                    )
                elif self.direction is io.Direction.Bidir:
                    m.submodules[name] = Instance("IOBUF",
                        i_OEN=self.t[bit],
                        i_I=self.o[bit],
                        o_O=self.i[bit],
                        io_IO=self.port.io[bit],
                    )
                else:
                    assert False # :nocov:
            elif isinstance(self.port, io.DifferentialPort):
                if self.direction is io.Direction.Input:
                    m.submodules[name] = Instance("TLVDS_IBUF",
                        i_I=self.port.p[bit],
                        i_IB=self.port.n[bit],
                        o_O=self.i[bit],
                    )
                elif self.direction is io.Direction.Output:
                    m.submodules[name] = Instance("TLVDS_TBUF",
                        i_OEN=self.t[bit],
                        i_I=self.o[bit],
                        o_O=self.port.p[bit],
                        o_OB=self.port.n[bit],
                    )
                elif self.direction is io.Direction.Bidir:
                    m.submodules[name] = Instance("TLVDS_IOBUF",
                        i_OEN=self.t[bit],
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


class FFBuffer(io.FFBuffer):
    def elaborate(self, platform):
        m = Module()

        m.submodules.buf = buf = InnerBuffer(self.direction, self.port)
        inv_mask = sum(inv << bit for bit, inv in enumerate(self.port.invert))

        if self.direction is not io.Direction.Output:
            i_inv = Signal.like(self.i)
            m.d[self.i_domain] += i_inv.eq(buf.i)
            m.d.comb += self.i.eq(i_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.d[self.o_domain] += buf.o.eq(self.o ^ inv_mask)
            m.d[self.o_domain] += buf.t.eq(~self.oe.replicate(len(self.port)))

        return m


class DDRBuffer(io.DDRBuffer):
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
                    i_CLK=ClockSignal(self.i_domain),
                    i_D=buf.i[bit],
                    o_Q0=i0_inv[bit],
                    o_Q1=i1_inv[bit],
                )
            m.d.comb += self.i[0].eq(i0_inv ^ inv_mask)
            m.d.comb += self.i[1].eq(i1_inv ^ inv_mask)

        if self.direction is not io.Direction.Input:
            m.submodules += RequirePosedge(self.o_domain)
            o0_inv = self.o[0] ^ inv_mask
            o1_inv = self.o[1] ^ inv_mask
            for bit in range(len(self.port)):
                m.submodules[f"o_ddr{bit}"] = Instance("ODDR",
                    p_TXCLK_POL=0, # default -> Q1 changes on posedge of CLK
                    i_CLK=ClockSignal(self.o_domain),
                    i_D0=o0_inv[bit],
                    i_D1=o1_inv[bit],
                    i_TX=~self.oe,
                    o_Q0=buf.o[bit],
                    o_Q1=buf.t[bit],
                )

        return m


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
        # Gowin is using neither Tcl nor the Synopsys code to parse SDC files, so the grammar
        # deviates from the usual (eg. no quotes, no nested braces).
        "{{name}}.sdc": r"""
        // {{autogenerated}}
        {% for signal, frequency in platform.iter_signal_clock_constraints() -%}
            create_clock -name {{ "{" }}{{signal.name}}{{ "}" }} -period {{1000000000/frequency}} [get_nets {{signal|hierarchy("/")|tcl_quote}}]
        {% endfor %}
        {% for port, frequency in platform.iter_port_clock_constraints() -%}
            create_clock -name {{ "{" }}{{port.name}}{{ "}" }} -period {{1000000000/frequency}} [get_ports
            {{ "{" }}{{port.name}}{{ "}" }}]
        {% endfor %}
        {{get_override("add_constraints")|default("// (add_constraints placeholder)")}}
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
                clk_io = self.request(self.default_clk, dir="-")
                m.submodules.clk_buf = clk_buf = io.Buffer("i", clk_io)
                clk_i = clk_buf.i

            if self.default_rst is not None:
                rst_io = self.request(self.default_rst, dir="-")
                m.submodules.rst_buf = rst_buf = io.Buffer("i", rst_io)
                rst_i = rst_buf.i
            else:
                rst_i = Const(0)

            m.submodules.reset_sync = ResetSynchronizer(rst_i, domain="sync")
            m.domains += ClockDomain("sync")
            m.d.comb += ClockSignal("sync").eq(clk_i)

            return m

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
