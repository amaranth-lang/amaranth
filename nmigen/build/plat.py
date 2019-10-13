from collections import OrderedDict
from abc import ABCMeta, abstractmethod, abstractproperty
import os
import textwrap
import re
import jinja2

from .. import __version__
from .._toolchain import *
from ..hdl import *
from ..lib.cdc import ResetSynchronizer
from ..back import rtlil, verilog
from .res import *
from .run import *


__all__ = ["Platform", "TemplatedPlatform"]


class Platform(ResourceManager, metaclass=ABCMeta):
    resources      = abstractproperty()
    connectors     = abstractproperty()
    default_clk    = None
    default_rst    = None
    required_tools = abstractproperty()

    def __init__(self):
        super().__init__(self.resources, self.connectors)

        self.extra_files = OrderedDict()

        self._prepared   = False

    @property
    def default_clk_constraint(self):
        if self.default_clk is None:
            raise AttributeError("Platform '{}' does not define a default clock"
                                 .format(type(self).__name__))
        return self.lookup(self.default_clk).clock

    @property
    def default_clk_frequency(self):
        constraint = self.default_clk_constraint
        if constraint is None:
            raise AttributeError("Platform '{}' does not constrain its default clock"
                                 .format(type(self).__name__))
        return constraint.frequency

    def add_file(self, filename, content):
        if not isinstance(filename, str):
            raise TypeError("File name must be a string")
        if filename in self.extra_files:
            raise ValueError("File {} already exists"
                             .format(filename))
        if hasattr(content, "read"):
            content = content.read()
        elif not isinstance(content, (str, bytes)):
            raise TypeError("File contents must be str, bytes, or a file-like object")
        self.extra_files[filename] = content

    @property
    def _toolchain_env_var(self):
        return f"NMIGEN_ENV_{self.toolchain}"

    def build(self, elaboratable, name="top",
              build_dir="build", do_build=True,
              program_opts=None, do_program=False,
              **kwargs):
        if self._toolchain_env_var not in os.environ:
            for tool in self.required_tools:
                require_tool(tool)

        plan = self.prepare(elaboratable, name, **kwargs)
        if not do_build:
            return plan

        products = plan.execute_local(build_dir)
        if not do_program:
            return products

        self.toolchain_program(products, name, **(program_opts or {}))

    def has_required_tools(self):
        if self._toolchain_env_var in os.environ:
            return True
        return all(has_tool(name) for name in self.required_tools)

    def create_missing_domain(self, name):
        # Simple instantiation of a clock domain driven directly by the board clock and reset.
        # This implementation uses a single ResetSynchronizer to ensure that:
        #   * an external reset is definitely synchronized to the system clock;
        #   * release of power-on reset, which is inherently asynchronous, is synchronized to
        #     the system clock.
        # Many device families provide advanced primitives for tackling reset. If these exist,
        # they should be used instead.
        if name == "sync" and self.default_clk is not None:
            clk_i = self.request(self.default_clk).i
            if self.default_rst is not None:
                rst_i = self.request(self.default_rst).i
            else:
                rst_i = Const(0)

            m = Module()
            m.domains += ClockDomain("sync")
            m.d.comb += ClockSignal("sync").eq(clk_i)
            m.submodules.reset_sync = ResetSynchronizer(rst_i, domain="sync")
            return m

    def prepare(self, elaboratable, name="top", **kwargs):
        assert not self._prepared
        self._prepared = True

        fragment = Fragment.get(elaboratable, self)
        fragment.create_missing_domains(self.create_missing_domain, platform=self)

        def add_pin_fragment(pin, pin_fragment):
            pin_fragment = Fragment.get(pin_fragment, self)
            if not isinstance(pin_fragment, Instance):
                pin_fragment.flatten = True
            fragment.add_subfragment(pin_fragment, name="pin_{}".format(pin.name))

        for pin, port, attrs, invert in self.iter_single_ended_pins():
            if pin.dir == "i":
                add_pin_fragment(pin, self.get_input(pin, port, attrs, invert))
            if pin.dir == "o":
                add_pin_fragment(pin, self.get_output(pin, port, attrs, invert))
            if pin.dir == "oe":
                add_pin_fragment(pin, self.get_tristate(pin, port, attrs, invert))
            if pin.dir == "io":
                add_pin_fragment(pin, self.get_input_output(pin, port, attrs, invert))

        for pin, p_port, n_port, attrs, invert in self.iter_differential_pins():
            if pin.dir == "i":
                add_pin_fragment(pin, self.get_diff_input(pin, p_port, n_port, attrs, invert))
            if pin.dir == "o":
                add_pin_fragment(pin, self.get_diff_output(pin, p_port, n_port, attrs, invert))
            if pin.dir == "oe":
                add_pin_fragment(pin, self.get_diff_tristate(pin, p_port, n_port, attrs, invert))
            if pin.dir == "io":
                add_pin_fragment(pin,
                    self.get_diff_input_output(pin, p_port, n_port, attrs, invert))

        fragment = fragment.prepare(ports=self.iter_ports(), missing_domain=lambda name: None)
        return self.toolchain_prepare(fragment, name, **kwargs)

    @abstractmethod
    def toolchain_prepare(self, fragment, name, **kwargs):
        """
        Convert the ``fragment`` and constraints recorded in this :class:`Platform` into
        a :class:`BuildPlan`.
        """
        raise NotImplementedError # :nocov:

    def toolchain_program(self, products, name, **kwargs):
        """
        Extract bitstream for fragment ``name`` from ``products`` and download it to a target.
        """
        raise NotImplementedError("Platform '{}' does not support programming"
                                  .format(type(self).__name__))

    def _check_feature(self, feature, pin, attrs, valid_xdrs, valid_attrs):
        if not valid_xdrs:
            raise NotImplementedError("Platform '{}' does not support {}"
                                      .format(type(self).__name__, feature))
        elif pin.xdr not in valid_xdrs:
            raise NotImplementedError("Platform '{}' does not support {} for XDR {}"
                                      .format(type(self).__name__, feature, pin.xdr))

        if not valid_attrs and attrs:
            raise NotImplementedError("Platform '{}' does not support attributes for {}"
                                      .format(type(self).__name__, feature))

    @staticmethod
    def _invert_if(invert, value):
        if invert:
            return ~value
        else:
            return value

    def get_input(self, pin, port, attrs, invert):
        self._check_feature("single-ended input", pin, attrs,
                            valid_xdrs=(0,), valid_attrs=None)

        m = Module()
        m.d.comb += pin.i.eq(self._invert_if(invert, port))
        return m

    def get_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended output", pin, attrs,
                            valid_xdrs=(0,), valid_attrs=None)

        m = Module()
        m.d.comb += port.eq(self._invert_if(invert, pin.o))
        return m

    def get_tristate(self, pin, port, attrs, invert):
        self._check_feature("single-ended tristate", pin, attrs,
                            valid_xdrs=(0,), valid_attrs=None)

        m = Module()
        m.submodules += Instance("$tribuf",
            p_WIDTH=pin.width,
            i_EN=pin.oe,
            i_A=self._invert_if(invert, pin.o),
            o_Y=port,
        )
        return m

    def get_input_output(self, pin, port, attrs, invert):
        self._check_feature("single-ended input/output", pin, attrs,
                            valid_xdrs=(0,), valid_attrs=None)

        m = Module()
        m.submodules += Instance("$tribuf",
            p_WIDTH=pin.width,
            i_EN=pin.oe,
            i_A=self._invert_if(invert, pin.o),
            o_Y=port,
        )
        m.d.comb += pin.i.eq(self._invert_if(invert, port))
        return m

    def get_diff_input(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input", pin, attrs,
                            valid_xdrs=(), valid_attrs=None)

    def get_diff_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential output", pin, attrs,
                            valid_xdrs=(), valid_attrs=None)

    def get_diff_tristate(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential tristate", pin, attrs,
                            valid_xdrs=(), valid_attrs=None)

    def get_diff_input_output(self, pin, p_port, n_port, attrs, invert):
        self._check_feature("differential input/output", pin, attrs,
                            valid_xdrs=(), valid_attrs=None)


class TemplatedPlatform(Platform):
    toolchain         = abstractproperty()
    file_templates    = abstractproperty()
    command_templates = abstractproperty()

    build_script_templates = {
        "build_{{name}}.sh": """
            # {{autogenerated}}
            set -e{{verbose("x")}}
            [ -n "${{platform._toolchain_env_var}}" ] && . "${{platform._toolchain_env_var}}"
            {{emit_commands("sh")}}
        """,
        "build_{{name}}.bat": """
            @rem {{autogenerated}}
            {{quiet("@echo off")}}
            if defined {{platform._toolchain_env_var}} call %{{platform._toolchain_env_var}}%
            {{emit_commands("bat")}}
        """,
    }

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

        rtlil_text, name_map = rtlil.convert_fragment(fragment, name=name)

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
            return separator.join(name_map[signal][1:])

        def verbose(arg):
            if "NMIGEN_verbose" in os.environ:
                return arg
            else:
                return jinja2.Undefined(name="quiet")

        def quiet(arg):
            if "NMIGEN_verbose" in os.environ:
                return jinja2.Undefined(name="quiet")
            else:
                return arg

        def render(source, origin, syntax=None):
            try:
                source   = textwrap.dedent(source).strip()
                compiled = jinja2.Template(source, trim_blocks=True, lstrip_blocks=True)
                compiled.environment.filters["options"] = options
                compiled.environment.filters["hierarchy"] = hierarchy
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

    def iter_extra_files(self, *endswith):
        return (f for f in self.extra_files if f.endswith(endswith))
