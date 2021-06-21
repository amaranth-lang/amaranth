from abc import abstractproperty

import textwrap
import re
import jinja2
import os

from .. import __version__
from .._toolchain import *
from ..hdl import *
from ..hdl.xfrm import SampleLowerer, DomainLowerer
from ..lib.cdc import ResetSynchronizer
from ..back import rtlil, verilog
from ..build.res import *
from ..build.run import *
from ..lib.cdc import ResetSynchronizer
from ..build import *

__all__ = ["OpenLANEPlatform"]

class OpenLANEPlatform(TemplatedPlatform):
    """
    OpenLANE ASIC Flow
    ------------------

    **NOTE:** See https://github.com/The-OpenROAD-Project/OpenLane#setting-up-openlane for
    information on how to setup OpenLANE.

    Required tools:
        * ``openlane``
        * ``docker``

    Build products:
        * ``config.tcl``: OpenLANE configuration script.
        * ``{{name}}.sdc``: Clock constraints.
        * ``{{name}}.v``: Design verilog
        * ``{{name}}.debug.v``: Design debug verilog
        * ``runs/*``: OpenLANE flow output

    """

    toolchain = "OpenLANE"

    _INVK_DIR = os.getcwd()
    _UID = os.getuid()
    _GID = os.getgid()

    openlane_root = abstractproperty()
    pdk = abstractproperty()
    cell_library = abstractproperty()

    settings = abstractproperty()

    required_tools = ["docker"]

    file_templates = {
        **TemplatedPlatform.build_script_templates,
        """build_{{name}}.sh""": r"""
            # {{autogenerated}}
            set -e{{verbose("x")}}
            if [ -z "$BASH" ] ; then exec /bin/bash "$0" "$@"; fi
            [ -n "${{platform._toolchain_env_var}}" ] && . "${{platform._toolchain_env_var}}"
            {{emit_commands("sh")}}
        """,
        """config.tcl""": r"""
            # {{autogenerated}}
            # Design Information
            set ::env(DESIGN_NAME) "{{name}}"
            set ::env(VERILOG_FILES) "/design_{{name}}/{{name}}.v"
            set ::env(SDC_FILE) "/design_{{name}}/{{name}}.sdc"
            {% if platform.default_clk %}
            # Clock Settings
            # TODO, use platform.default_clk_frequency() to calc CLOCK_PERIOD
            set ::env(CLOCK_PERIOD) "18.0"
            set ::env(CLOCK_PORT) "{{platform.default_clk}}"
            set ::env(CLOCK_NET) $::env(CLOCK_PORT)
            {% else %}
            # Disable the clock
            set ::env(CLOCK_TREE_SYNTH) 0
            set ::env(CLOCK_PORT) ""
            {% endif %}
            # PDK Settings
            set ::env(PDK) "{{platform.pdk}}"
            set ::env(STD_CELL_LIBRARY) "{{platform.cell_library}}"

            {% for s, v in platform.settings.items() %}
            set ::env({{s}}) {{v}}
            {% endfor %}

            # Pull in PDK specific settings
            set filename $::env(DESIGN_DIR)/$::env(PDK)_$::env(STD_CELL_LIBRARY)_config.tcl
            if { [file exists $filename] == 1} {
                source $filename
            }
        """,
        "{{name}}.v": r"""
            /* {{autogenerated}} */
            {{emit_verilog()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.sdc": r"""
            {% for net_signal, port_signal, frequency in platform.iter_clock_constraints() -%}
                {% if port_signal is not none -%}
                    create_clock -name {{port_signal.name|tcl_escape}} -period {{1000000000/frequency}} [get_ports {{port_signal.name|tcl_escape}}]
                {% else -%}
                    create_clock -name {{net_signal.name|tcl_escape}} -period {{1000000000/frequency}} [get_nets {{net_signal|hierarchy("/")|tcl_escape}}]
                {% endif %}
            {% endfor %}
            {{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
        """,
    }

    command_templates = [
        r"""
        {{invoke_tool("docker")}}
            run
            -it
            --rm
            -v {{platform.openlane_root}}:/openLANE_flow
            -v {{platform.openlane_root}}/pdks:/PDK
            -v {{platform._INVK_DIR}}/build:/design_{{name}}
            -e PDK_ROOT=/PDK
            -u {{platform._UID}}:{{platform._GID}}
            efabless/openlane:v0.12
            sh -c "./flow.tcl -design /design_{{name}}"
        """
    ]

    def __init__(self, *, toolchain="openLANE"):
        super().__init__()

    # This was lifted directly from the TemplatedPlatform because I needed to tweak it a bit
    def toolchain_prepare(self, fragment, name, **kwargs):
        # Restrict the name of the design to a strict alphanumeric character set. Platforms will
        # interpolate the name of the design in many different contexts: filesystem paths, Python
        # scripts, Tcl scripts, ad-hoc constraint files, and so on. It is not practical to add
        # escaping code that handles every one of their edge cases, so make sure we never hit them
        # in the first place.
        invalid_char = re.match(r"[^A-Za-z0-9_]", name)
        if invalid_char:
            raise ValueError("Design name {!r} contains invalid character {!r}; only alphanumeric "
                             "characters are valid in design names"
                             .format(name, invalid_char.group(0)))

        # This notice serves a dual purpose: to explain that the file is autogenerated,
        # and to incorporate the nMigen version into generated code.
        autogenerated = "Automatically generated by nMigen {}. Do not edit.".format(__version__)

        ports = kwargs.get('ports', ())

        rtlil_text, self._name_map = rtlil.convert2(fragment, name=name, ports=ports)
        # _, self._name_map = rtlil.convert_fragment(fragment, name=name)

        def emit_rtlil():
            return rtlil_text

        def emit_verilog(opts=()):
            return verilog._convert_rtlil_text(rtlil_text,
                strip_internal_attrs=True, write_verilog_opts=opts)

        def emit_debug_verilog(opts=()):
            return verilog._convert_rtlil_text(rtlil_text,
                strip_internal_attrs=False, write_verilog_opts=opts)

        def emit_commands(syntax):
            commands = []

            for name in self.required_tools:
                env_var = tool_env_var(name)
                if syntax == "sh":
                    template = ": ${{{env_var}:={name}}}"
                elif syntax == "bat":
                    template = \
                        "if [%{env_var}%] equ [\"\"] set {env_var}=\n" \
                        "if [%{env_var}%] equ [] set {env_var}={name}"
                else:
                    assert False
                commands.append(template.format(env_var=env_var, name=name))

            for index, command_tpl in enumerate(self.command_templates):
                command = render(command_tpl, origin="<command#{}>".format(index + 1),
                                 syntax=syntax)
                command = re.sub(r"\s+", " ", command)
                if syntax == "sh":
                    commands.append(command)
                elif syntax == "bat":
                    commands.append(command + " || exit /b")
                else:
                    assert False

            return "\n".join(commands)

        def get_override(var):
            var_env = "NMIGEN_{}".format(var)
            if var_env in os.environ:
                # On Windows, there is no way to define an "empty but set" variable; it is tempting
                # to use a quoted empty string, but it doesn't do what one would expect. Recognize
                # this as a useful pattern anyway, and treat `set VAR=""` on Windows the same way
                # `export VAR=` is treated on Linux.
                return re.sub(r'^\"\"$', "", os.environ[var_env])
            elif var in kwargs:
                if isinstance(kwargs[var], str):
                    return textwrap.dedent(kwargs[var]).strip()
                else:
                    return kwargs[var]
            else:
                return jinja2.Undefined(name=var)

        @jinja2.contextfunction
        def invoke_tool(context, name):
            env_var = tool_env_var(name)
            if context.parent["syntax"] == "sh":
                return "\"${}\"".format(env_var)
            elif context.parent["syntax"] == "bat":
                return "%{}%".format(env_var)
            else:
                assert False

        def options(opts):
            if isinstance(opts, str):
                return opts
            else:
                return " ".join(opts)

        def hierarchy(signal, separator):
            return separator.join(self._name_map[signal][1:])

        def ascii_escape(string):
            def escape_one(match):
                if match.group(1) is None:
                    return match.group(2)
                else:
                    return "_{:02x}_".format(ord(match.group(1)[0]))
            return "".join(escape_one(m) for m in re.finditer(r"([^A-Za-z0-9_])|(.)", string))

        def tcl_escape(string):
            return "{" + re.sub(r"([{}\\])", r"\\\1", string) + "}"

        def tcl_quote(string):
            return '"' + re.sub(r"([$[\\])", r"\\\1", string) + '"'

        def verbose(arg):
            if get_override("verbose"):
                return arg
            else:
                return jinja2.Undefined(name="quiet")

        def quiet(arg):
            if get_override("verbose"):
                return jinja2.Undefined(name="quiet")
            else:
                return arg

        def render(source, origin, syntax=None):
            try:
                source   = textwrap.dedent(source).strip()
                compiled = jinja2.Template(source,
                    trim_blocks=True, lstrip_blocks=True, undefined=jinja2.StrictUndefined)
                compiled.environment.filters["options"] = options
                compiled.environment.filters["hierarchy"] = hierarchy
                compiled.environment.filters["ascii_escape"] = ascii_escape
                compiled.environment.filters["tcl_escape"] = tcl_escape
                compiled.environment.filters["tcl_quote"] = tcl_quote
            except jinja2.TemplateSyntaxError as e:
                e.args = ("{} (at {}:{})".format(e.message, origin, e.lineno),)
                raise
            return compiled.render({
                "name": name,
                "platform": self,
                "emit_rtlil": emit_rtlil,
                "emit_verilog": emit_verilog,
                "emit_debug_verilog": emit_debug_verilog,
                "emit_commands": emit_commands,
                "syntax": syntax,
                "invoke_tool": invoke_tool,
                "get_override": get_override,
                "verbose": verbose,
                "quiet": quiet,
                "autogenerated": autogenerated,
            })

        plan = BuildPlan(script="build_{}".format(name))
        for filename_tpl, content_tpl in self.file_templates.items():
            plan.add_file(render(filename_tpl, origin=filename_tpl),
                          render(content_tpl, origin=content_tpl))
        for filename, content in self.extra_files.items():
            plan.add_file(filename, content)
        return plan

    def create_missing_domain(self, name):
        if name == "sync":
            m = Module()
            if self.default_clk is not None:
                clk_i = self.request(self.default_clk).i
            else:
                clk_i = Const(1)

            if self.default_rst is not None:
               rst_i = self.request(self.default_rst).i
            else:
               rst_i = Const(0)

            m.domains += ClockDomain("sync"),
            m.d.comb += ClockSignal("sync").eq(clk_i)
            m.submodules.reset_sync = ResetSynchronizer(rst_i, domain="sync")

            return m
