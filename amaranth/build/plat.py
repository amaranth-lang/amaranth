from collections import OrderedDict
from collections.abc import Iterable
from abc import ABCMeta, abstractmethod
import os
import textwrap
import re
import jinja2

from .. import __version__
from .._toolchain import *
from ..hdl import *
from ..hdl._ir import IOBufferInstance, Design
from ..hdl._xfrm import DomainLowerer
from ..lib.cdc import ResetSynchronizer
from ..lib import io
from ..back import rtlil, verilog
from .res import *
from .run import *


__all__ = ["Platform", "TemplatedPlatform"]


class Platform(ResourceManager, metaclass=ABCMeta):
    resources      = property(abstractmethod(lambda: None))
    connectors     = property(abstractmethod(lambda: None))
    default_clk    = None
    default_rst    = None
    required_tools = property(abstractmethod(lambda: None))

    def __init__(self):
        super().__init__(self.resources, self.connectors)

        self.extra_files = OrderedDict()

        self._prepared   = False
        self._design     = None

    @property
    def default_clk_constraint(self):
        if self.default_clk is None:
            raise AttributeError("Platform '{}' does not define a default clock"
                                 .format(type(self).__qualname__))
        return self.lookup(self.default_clk).clock

    @property
    def default_clk_frequency(self):
        constraint = self.default_clk_constraint
        if constraint is None:
            raise AttributeError("Platform '{}' does not constrain its default clock"
                                 .format(type(self).__qualname__))
        return constraint.frequency

    def add_file(self, filename, content):
        if not isinstance(filename, str):
            raise TypeError("File name must be a string, not {!r}"
                            .format(filename))
        if hasattr(content, "read"):
            content = content.read()
        elif not isinstance(content, (str, bytes)):
            raise TypeError("File contents must be str, bytes, or a file-like object, not {!r}"
                            .format(content))
        if filename in self.extra_files:
            if self.extra_files[filename] != content:
                raise ValueError("File {!r} already exists"
                                 .format(filename))
        else:
            self.extra_files[filename] = content

    def iter_files(self, *suffixes):
        for filename in self.extra_files:
            if filename.endswith(suffixes):
                yield filename

    @property
    def _toolchain_env_var(self):
        return f"AMARANTH_ENV_{tool_env_var(self.toolchain)}"

    def build(self, elaboratable, name="top",
              build_dir="build", do_build=True,
              program_opts=None, do_program=False,
              **kwargs):
        # The following code performs a best-effort check for presence of required tools upfront,
        # before performing any build actions, to provide a better diagnostic. It does not handle
        # several corner cases:
        #  1. `require_tool` does not source toolchain environment scripts, so if such a script
        #     is used, the check is skipped, and `execute_local()` may fail;
        #  2. if the design is not built (do_build=False), most of the tools are not required and
        #     in fact might not be available if the design will be built manually with a different
        #     environment script specified, or on a different machine; however, Yosys is required
        #     by virtually every platform anyway, to provide debug Verilog output, and `prepare()`
        #     may fail.
        # This is OK because even if `require_tool` succeeds, the toolchain might be broken anyway.
        # The check only serves to catch common errors earlier.
        if do_build and self._toolchain_env_var not in os.environ:
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
            m = Module()

            clk_io = self.request(self.default_clk, dir="-")
            m.submodules.clk_buf = clk_buf = io.Buffer("i", clk_io)

            if self.default_rst is not None:
                rst_io = self.request(self.default_rst, dir="-")
                m.submodules.rst_buf = rst_buf = io.Buffer("i", rst_io)
                rst_i = rst_buf.i
            else:
                rst_i = Const(0)

            m.domains += ClockDomain("sync")
            m.d.comb += ClockSignal("sync").eq(clk_buf.i)
            m.submodules.reset_sync = ResetSynchronizer(rst_i, domain="sync")

            return m

    def prepare(self, elaboratable, name="top", **kwargs):
        assert not self._prepared
        self._prepared = True

        fragment = Fragment.get(elaboratable, self)
        fragment._propagate_domains(self.create_missing_domain, platform=self)
        fragment = DomainLowerer()(fragment)

        def missing_domain_error(name):
            raise RuntimeError("Missing domain in pin fragment")

        for pin, port, buffer in self.iter_pins():
            buffer = Fragment.get(buffer, self)
            buffer._propagate_domains(missing_domain_error)
            buffer = DomainLowerer()(buffer)
            fragment.add_subfragment(buffer, name=f"pin_{pin.name}")

        self._design = Design(fragment, [], hierarchy=(name,))
        return self.toolchain_prepare(self._design, name, **kwargs)

    def iter_port_constraints_bits(self):
        for (name, port, _dir) in self._design.ports:
            if len(port) == 1:
                yield name, port.metadata[0].name, port.metadata[0].attrs
            else:
                for bit, meta in enumerate(port.metadata):
                    yield f"{name}[{bit}]", meta.name, meta.attrs

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
                                  .format(type(self).__qualname__))


class TemplatedPlatform(Platform):
    toolchain         = property(abstractmethod(lambda: None))
    file_templates    = property(abstractmethod(lambda: None))
    command_templates = property(abstractmethod(lambda: None))

    build_script_templates = {
        "build_{{name}}.sh": """
            #!/bin/sh
            # {{autogenerated}}
            set -e{{verbose("x")}}
            [ -n "${{platform._toolchain_env_var}}" ] && . "${{platform._toolchain_env_var}}"
            {{emit_commands("sh")}}
        """,
        "build_{{name}}.bat": """
            @rem {{autogenerated}}
            {{quiet("@echo off")}}
            SetLocal EnableDelayedExpansion
            if defined {{platform._toolchain_env_var}} call "%{{platform._toolchain_env_var}}%"
            {{emit_commands("bat")}}
        """,
    }

    def iter_signal_clock_constraints(self):
        for signal, frequency in super().iter_signal_clock_constraints():
            # Skip any clock constraints placed on signals that are never used in the design.
            # Otherwise, it will cause a crash in the vendor platform if it supports clock
            # constraints on non-port nets.
            if signal not in self._name_map:
                continue
            yield signal, frequency

    def toolchain_prepare(self, fragment, name, *, emit_src=True, **kwargs):
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
        # and to incorporate the Amaranth version into generated code.
        autogenerated = f"Automatically generated by Amaranth {__version__}. Do not edit."

        rtlil_text, self._name_map = rtlil.convert_fragment(fragment, name=name,
                                                            emit_src=emit_src, propagate_domains=False)

        # Retrieve an override specified in either the environment or as a kwarg.
        # expected_type parameter is used to assert the type of kwargs, passing `None` will disable
        # type checking.
        def _extract_override(var, *, expected_type):
            var_env = f"AMARANTH_{var}"
            if var_env in os.environ:
                # On Windows, there is no way to define an "empty but set" variable; it is tempting
                # to use a quoted empty string, but it doesn't do what one would expect. Recognize
                # this as a useful pattern anyway, and treat `set VAR=""` on Windows the same way
                # `export VAR=` is treated on Linux.
                if var_env in os.environ:
                    var_env_value = os.environ[var_env]
                return re.sub(r'^\"\"$', "", var_env_value)
            elif var in kwargs:
                kwarg = kwargs[var]
                if issubclass(expected_type, str) and not isinstance(kwarg, str) and isinstance(kwarg, Iterable):
                    kwarg = " ".join(kwarg)
                if not isinstance(kwarg, expected_type) and not expected_type is None:
                    raise TypeError(f"Override '{var}' must be a {expected_type.__qualname__}, not {kwarg!r}")
                return kwarg
            else:
                return jinja2.Undefined(name=var)

        def get_override(var):
            value = _extract_override(var, expected_type=str)
            return value

        def get_override_flag(var):
            value = _extract_override(var, expected_type=bool)
            if isinstance(value, str):
                value = value.lower()
                if value in ("0", "no", "n", "false", ""):
                    return False
                if value in ("1", "yes", "y", "true"):
                    return True
                else:
                    raise ValueError("Override '{}' must be one of "
                                     "(\"0\", \"n\", \"no\", \"false\", \"\") "
                                     "or "
                                     "(\"1\", \"y\", \"yes\", \"true\"), not {!r}"
                                     .format(var, value))
            return value

        def emit_rtlil():
            return rtlil_text

        def emit_verilog(opts=()):
            return verilog._convert_rtlil_text(rtlil_text,
                strip_internal_attrs=True, write_verilog_opts=opts)

        def emit_debug_verilog(opts=()):
            if not get_override_flag("debug_verilog"):
                return "/* Debug Verilog generation was disabled. */"
            else:
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
                        "if [!{env_var}!] equ [\"\"] set {env_var}=\n" \
                        "if [!{env_var}!] equ [] set {env_var}={name}"
                else:
                    assert False
                commands.append(template.format(env_var=env_var, name=name))

            for index, command_tpl in enumerate(self.command_templates):
                command = render(command_tpl, origin=f"<command#{index + 1}>",
                                 syntax=syntax)
                command = re.sub(r"\s+", " ", command)
                if syntax == "sh":
                    commands.append(command)
                elif syntax == "bat":
                    commands.append(command + " || exit /b")
                else:
                    assert False

            return "\n".join(commands) + "\n"

        @jinja2.pass_context
        def invoke_tool(context, name):
            env_var = tool_env_var(name)
            if context.parent["syntax"] == "sh":
                return f"\"${env_var}\""
            elif context.parent["syntax"] == "bat":
                return f"\"%{env_var}%\""
            else:
                assert False

        def options(opts):
            if isinstance(opts, str):
                return opts
            else:
                return " ".join(opts)

        def hierarchy(net, separator):
            if isinstance(net, IOPort):
                return net.name
            else:
                return separator.join(self._name_map[net][1:])

        def ascii_escape(string):
            def escape_one(match):
                if match.group(1) is None:
                    return match.group(2)
                else:
                    return f"_{ord(match.group(1)[0]):02x}_"
            return "".join(escape_one(m) for m in re.finditer(r"([^A-Za-z0-9_])|(.)", string))

        def tcl_quote(string, quirk=None):
            escaped = '"' + re.sub(r"([$[\\])", r"\\\1", string) + '"'
            if quirk == "Diamond":
                # Diamond seems to assign `clk\$2` as a name for the Verilog net `\clk$2 `, and
                # `clk\\\$2` as a name for the Verilog net `\clk\$2 `.
                return escaped.replace("\\", "\\\\")
            else:
                assert quirk is None
                return escaped

        def verbose(arg):
            if get_override_flag("verbose"):
                return arg
            else:
                return jinja2.Undefined(name="quiet")

        def quiet(arg):
            if get_override_flag("verbose"):
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
                compiled.environment.filters["tcl_quote"] = tcl_quote
            except jinja2.TemplateSyntaxError as e:
                e.args = (f"{e.message} (at {origin}:{e.lineno})",)
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
                "get_override_flag": get_override_flag,
                "verbose": verbose,
                "quiet": quiet,
                "autogenerated": autogenerated,
            })

        plan = BuildPlan(script=f"build_{name}")
        for filename_tpl, content_tpl in self.file_templates.items():
            plan.add_file(render(filename_tpl, origin=filename_tpl),
                          render(content_tpl, origin=content_tpl))
        for filename, content in self.extra_files.items():
            plan.add_file(filename, content)
        return plan
