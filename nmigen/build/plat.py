from collections import OrderedDict
from abc import ABCMeta, abstractmethod, abstractproperty
import os
import textwrap
import re
import jinja2

from .. import __version__
from ..hdl.ast import *
from ..hdl.dsl import *
from ..hdl.ir import *
from ..back import rtlil, verilog
from .res import *
from .run import *


__all__ = ["Platform", "TemplatedPlatform"]


class Platform(ResourceManager, metaclass=ABCMeta):
    resources  = abstractproperty()
    connectors = abstractproperty()

    def __init__(self):
        super().__init__(self.resources, self.connectors)

        self.extra_files = OrderedDict()

        self._prepared   = False

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

    def build(self, fragment, name="top",
              build_dir="build", do_build=True,
              program_opts=None, do_program=False,
              **kwargs):
        plan = self.prepare(fragment, name, **kwargs)
        if not do_build:
            return plan

        products = plan.execute(build_dir)
        if not do_program:
            return products

        self.toolchain_program(products, name, **(program_opts or {}))

    def prepare(self, fragment, name="top", **kwargs):
        assert not self._prepared
        self._prepared = True

        fragment = Fragment.get(fragment, self)

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
        raise NotImplementedError("Platform {} does not support programming"
                                  .format(self.__class__.__name__))

    def _check_feature(self, feature, pin, attrs, valid_xdrs, valid_attrs):
        if not valid_xdrs:
            raise NotImplementedError("Platform {} does not support {}"
                                      .format(self.__class__.__name__, feature))
        elif pin.xdr not in valid_xdrs:
            raise NotImplementedError("Platform {} does not support {} for XDR {}"
                                      .format(self.__class__.__name__, feature, pin.xdr))

        if not valid_attrs and attrs:
            raise NotImplementedError("Platform {} does not support attributes for {}"
                                      .format(self.__class__.__name__, feature))

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
    file_templates    = abstractproperty()
    command_templates = abstractproperty()

    build_script_templates = {
        "build_{{name}}.sh": """
            # {{autogenerated}}
            set -e{{verbose("x")}}
            {{emit_commands("sh")}}
        """,
        "build_{{name}}.bat": """
            @rem {{autogenerated}}
            {{quiet("@echo off")}}
            {{emit_commands("bat")}}
        """,
    }

    def toolchain_prepare(self, fragment, name, **kwargs):
        # This notice serves a dual purpose: to explain that the file is autogenerated,
        # and to incorporate the nMigen version into generated code.
        autogenerated = "Automatically generated by nMigen {}. Do not edit.".format(__version__)

        def emit_design(backend):
            return {"rtlil": rtlil, "verilog": verilog}[backend].convert(
                fragment, name=name, platform=self, ports=list(self.iter_ports()),
                ensure_sync_exists=False)

        def emit_commands(format):
            commands = []
            for index, command_tpl in enumerate(self.command_templates):
                command = render(command_tpl, origin="<command#{}>".format(index + 1))
                command = re.sub(r"\s+", " ", command)
                if format == "sh":
                    commands.append(command)
                elif format == "bat":
                    commands.append(command + " || exit /b")
                else:
                    assert False
            return "\n".join(commands)

        def get_tool(tool):
            tool_env = tool.upper().replace("-", "_")
            return os.environ.get(tool_env, tool)

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

        def render(source, origin):
            try:
                source   = textwrap.dedent(source).strip()
                compiled = jinja2.Template(source, trim_blocks=True, lstrip_blocks=True)
            except jinja2.TemplateSyntaxError as e:
                e.args = ("{} (at {}:{})".format(e.message, origin, e.lineno),)
                raise
            return compiled.render({
                "name": name,
                "platform": self,
                "emit_design": emit_design,
                "emit_commands": emit_commands,
                "get_tool": get_tool,
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
