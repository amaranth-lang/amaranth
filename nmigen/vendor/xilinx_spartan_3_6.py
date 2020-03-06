from abc import abstractproperty

from ..hdl import *
from ..lib.cdc import ResetSynchronizer
from ..build import *


__all__ = ["XilinxSpartan3APlatform", "XilinxSpartan6Platform"]


# The interface to Spartan 3 and 6 are substantially the same. Handle
# differences internally using one class and expose user-aliases for
# convenience.
class XilinxSpartan3Or6Platform(TemplatedPlatform):
    """
    Required tools:
        * ISE toolchain:
            * ``xst``
            * ``ngdbuild``
            * ``map``
            * ``par``
            * ``bitgen``

    The environment is populated by running the script specified in the environment variable
    ``NMIGEN_ENV_ISE``, if present.

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
    """

    toolchain = "ISE"

    device  = abstractproperty()
    package = abstractproperty()
    speed   = abstractproperty()

    required_tools = [
        "yosys",
        "xst",
        "ngdbuild",
        "map",
        "par",
        "bitgen",
    ]

    @property
    def family(self):
        device = self.device.upper()
        if device.startswith("XC3S"):
            if device.endswith("A"):
                return "3A"
            elif device.endswith("E"):
                raise NotImplementedError("""Spartan 3E family is not supported
                                           as a nMigen platform.""")
            else:
                raise NotImplementedError("""Spartan 3 family is not supported
                                           as a nMigen platform.""")
        elif device.startswith("XC6S"):
            return "6"
        else:
            assert False

    file_templates = {
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
            {% for file in platform.iter_extra_files(".vhd", ".vhdl") -%}
                vhdl work {{file}}
            {% endfor %}
            {% for file in platform.iter_extra_files(".v") -%}
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
            {% if platform.family in ["3", "3E", "3A"] %}
            -use_new_parser yes
            {% endif %}
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
            {% for net_signal, port_signal, frequency in platform.iter_clock_constraints() -%}
                NET "{{net_signal|hierarchy("/")}}" TNM_NET="PRD{{net_signal|hierarchy("/")}}";
                TIMESPEC "TS{{net_signal|hierarchy("/")}}"=PERIOD "PRD{{net_signal|hierarchy("/")}}" {{1000000000/frequency}} ns HIGH 50%;
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """
    }
    command_templates = [
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

    def create_missing_domain(self, name):
        # Xilinx devices have a global write enable (GWE) signal that asserted during configuraiton
        # and deasserted once it ends. Because it is an asynchronous signal (GWE is driven by logic
        # syncronous to configuration clock, which is not used by most designs), even though it is
        # a low-skew global network, its deassertion may violate a setup/hold constraint with
        # relation to a user clock. The recommended solution is to use a BUFGCE driven by the EOS
        # signal (if available). For details, see:
        #   * https://www.xilinx.com/support/answers/44174.html
        #   * https://www.xilinx.com/support/documentation/white_papers/wp272.pdf
        if self.family != "6":
            # Spartan 3 lacks a STARTUP primitive with EOS output; use a simple ResetSynchronizer
            # in that case, as is the default.
            return super().create_missing_domain(name)

        if name == "sync" and self.default_clk is not None:
            clk_i = self.request(self.default_clk).i
            if self.default_rst is not None:
                rst_i = self.request(self.default_rst).i

            m = Module()
            eos = Signal()
            m.submodules += Instance("STARTUP_SPARTAN6", o_EOS=eos)
            m.domains += ClockDomain("sync", reset_less=self.default_rst is None)
            m.submodules += Instance("BUFGCE", i_CE=eos, i_I=clk_i, o_O=ClockSignal("sync"))
            if self.default_rst is not None:
                m.submodules.reset_sync = ResetSynchronizer(rst_i, domain="sync")
            return m

    def _get_xdr_buffer(self, m, pin, *, i_invert=False, o_invert=False):
        def get_dff(clk, d, q):
            # SDR I/O is performed by packing a flip-flop into the pad IOB.
            for bit in range(len(q)):
                m.submodules += Instance("FDCE",
                    a_IOB="TRUE",
                    i_C=clk,
                    i_CE=Const(1),
                    i_CLR=Const(0),
                    i_D=d[bit],
                    o_Q=q[bit]
                )

        def get_iddr(clk, d, q0, q1):
            for bit in range(len(q0)):
                m.submodules += Instance("IDDR2",
                    p_DDR_ALIGNMENT="C0",
                    p_SRTYPE="ASYNC",
                    p_INIT_Q0=0, p_INIT_Q1=0,
                    i_C0=clk, i_C1=~clk,
                    i_CE=Const(1),
                    i_S=Const(0), i_R=Const(0),
                    i_D=d[bit],
                    o_Q0=q0[bit], o_Q1=q1[bit]
                )

        def get_oddr(clk, d0, d1, q):
            for bit in range(len(q)):
                m.submodules += Instance("ODDR2",
                    p_DDR_ALIGNMENT="C0",
                    p_SRTYPE="ASYNC",
                    p_INIT=0,
                    i_C0=clk, i_C1=~clk,
                    i_CE=Const(1),
                    i_S=Const(0), i_R=Const(0),
                    i_D0=d0[bit], i_D1=d1[bit],
                    o_Q=q[bit]
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
            if "i" in pin.dir:
                get_dff(pin.i_clk, i, pin_i)
            if "o" in pin.dir:
                get_dff(pin.o_clk, pin_o, o)
            if pin.dir in ("oe", "io"):
                get_dff(pin.o_clk, ~pin.oe, t)
        elif pin.xdr == 2:
            if "i" in pin.dir:
                # Re-register first input before it enters fabric. This allows both inputs to
                # enter fabric on the same clock edge, and adds one cycle of latency.
                i0_ff = Signal.like(pin_i0, name_suffix="_ff")
                get_dff(pin.i_clk, i0_ff, pin_i0)
                get_iddr(pin.i_clk, i, i0_ff, pin_i1)
            if "o" in pin.dir:
                get_oddr(pin.o_clk, pin_o0, pin_o1, o)
            if pin.dir in ("oe", "io"):
                get_dff(pin.o_clk, ~pin.oe, t)
        else:
            assert False

        return (i, o, t)

    def get_input(self, pin, port, attrs, invert):
        self._check_feature("single-ended input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert)
        for bit in range(len(port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("IBUF",
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
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OBUF",
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
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OBUFT",
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
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("IOBUF",
                i_T=t,
                i_I=o[bit],
                o_O=i[bit],
                io_IO=port[bit]
            )
        return m

    def get_diff_input(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("IBUFDS",
                i_I=p_port[bit], i_IB=n_port[bit],
                o_O=i[bit]
            )
        return m

    def get_diff_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OBUFDS",
                i_I=o[bit],
                o_O=p_port[bit], o_OB=n_port[bit]
            )
        return m

    def get_diff_tristate(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential tristate", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, o_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("OBUFTDS",
                i_T=t,
                i_I=o[bit],
                o_O=p_port[bit], o_OB=n_port[bit]
            )
        return m

    def get_diff_input_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input/output", pin, attrs,
                            valid_xdrs=(0, 1, 2), valid_attrs=True)
        m = Module()
        i, o, t = self._get_xdr_buffer(m, pin, i_invert=invert, o_invert=invert)
        for bit in range(len(p_port)):
            m.submodules["{}_{}".format(pin.name, bit)] = Instance("IOBUFDS",
                i_T=t,
                i_I=o[bit],
                o_O=i[bit],
                io_IO=p_port[bit], io_IOB=n_port[bit]
            )
        return m

    # The synchronizer implementations below apply the ASYNC_REG attribute. This attribute
    # prevents inference of shift registers from synchronizer FFs, and constraints the FFs
    # to be placed as close as possible, ideally in one CLB. This attribute only affects
    # the synchronizer FFs themselves.

    def get_ff_sync(self, ff_sync):
        if ff_sync._max_input_delay is not None:
            raise NotImplementedError("Platform '{}' does not support constraining input delay "
                                      "for FFSynchronizer"
                                      .format(type(self).__name__))

        m = Module()
        flops = [Signal(ff_sync.i.shape(), name="stage{}".format(index),
                        reset=ff_sync._reset, reset_less=ff_sync._reset_less,
                        attrs={"ASYNC_REG": "TRUE"})
                 for index in range(ff_sync._stages)]
        for i, o in zip((ff_sync.i, *flops), flops):
            m.d[ff_sync._o_domain] += o.eq(i)
        m.d.comb += ff_sync.o.eq(flops[-1])
        return m

    def get_async_ff_sync(self, async_ff_sync):
        m = Module()
        m.domains += ClockDomain("async_ff", async_reset=True, local=True)
        flops = [Signal(1, name="stage{}".format(index), reset=1,
                        attrs={"ASYNC_REG": "TRUE"})
                 for index in range(async_ff_sync._stages)]
        for i, o in zip((0, *flops), flops):
            m.d.async_ff += o.eq(i)

        if self._edge == "pos":
            m.d.comb += ResetSignal("async_ff").eq(asnyc_ff_sync.i)
        else:
            m.d.comb += ResetSignal("async_ff").eq(~asnyc_ff_sync.i)

        m.d.comb += [
            ClockSignal("async_ff").eq(ClockSignal(asnyc_ff_sync._domain)),
            async_ff_sync.o.eq(flops[-1])
        ]

        return m

XilinxSpartan3APlatform = XilinxSpartan3Or6Platform
XilinxSpartan6Platform = XilinxSpartan3Or6Platform
