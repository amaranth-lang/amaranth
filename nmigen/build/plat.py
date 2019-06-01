from collections import OrderedDict
from abc import ABCMeta, abstractmethod, abstractproperty
import os
import sys
import subprocess
import textwrap
import re
import zipfile
import jinja2

from .. import __version__
from ..hdl.ast import *
from ..hdl.dsl import *
from ..hdl.ir import *
from ..back import rtlil, verilog
from .res import ConstraintManager


__all__ = ["Platform", "TemplatedPlatform"]


class BuildPlan:
    def __init__(self, script):
        self.script = script
        self.files  = OrderedDict()

    def add_file(self, filename, content):
        assert isinstance(filename, str) and filename not in self.files
        # Just to make sure we don't accidentally overwrite anything.
        assert not os.path.normpath(filename).startswith("..")
        self.files[filename] = content

    def execute(self, root="build", run_script=True):
        os.makedirs(root, exist_ok=True)
        cwd = os.getcwd()
        try:
            os.chdir(root)

            for filename, content in self.files.items():
                dirname = os.path.dirname(filename)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)

                mode = "wt" if isinstance(content, str) else "wb"
                with open(filename, mode) as f:
                    f.write(content)

            if run_script:
                if sys.platform.startswith("win32"):
                    subprocess.run(["cmd", "/c", "{}.bat".format(self.script)], check=True)
                else:
                    subprocess.run(["sh", "{}.sh".format(self.script)], check=True)

                return BuildProducts(os.getcwd())

        finally:
            os.chdir(cwd)

    def archive(self, file):
        with zipfile.ZipFile(file, "w") as archive:
            # Write archive members in deterministic order and with deterministic timestamp.
            for filename in sorted(self.files):
                archive.writestr(zipfile.ZipInfo(filename), self.files[filename])


class BuildProducts:
    def __init__(self, root):
        self._root = root

    def get(self, filename, mode="b"):
        assert mode in "bt"
        with open(os.path.join(self._root, filename), "r" + mode) as f:
            return f.read()


class Platform(ConstraintManager, metaclass=ABCMeta):
    resources = abstractproperty()
    clocks    = abstractproperty()

    def __init__(self):
        super().__init__(self.resources, self.clocks)

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

        pin_fragments = []
        for pin, port in self._se_pins:
            if pin.dir == "i":
                pin_fragments.append((pin.name, self.get_input(pin, port)))
            if pin.dir == "o":
                pin_fragments.append((pin.name, self.get_output(pin, port)))
            if pin.dir == "io":
                pin_fragments.append((pin.name, self.get_tristate(pin, port)))
        for pin, p_port, n_port in self._dp_pins:
            if pin.dir == "i":
                pin_fragments.append((pin.name, self.get_diff_input(pin, p_port, n_port)))
            if pin.dir == "o":
                pin_fragments.append((pin.name, self.get_diff_output(pin, p_port, n_port)))
            if pin.dir == "io":
                pin_fragments.append((pin.name, self.get_diff_tristate(pin, p_port, n_port)))

        for pin_name, pin_fragment in pin_fragments:
            pin_fragment = Fragment.get(pin_fragment, self)
            if not isinstance(pin_fragment, Instance):
                pin_fragment.flatten = True
            fragment.add_subfragment(pin_fragment, name="pin_{}".format(pin_name))

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

    def _check_feature(self, feature, pin, xdrs):
        if not xdrs:
            raise NotImplementedError("Platform {} does not support {}"
                                      .format(self.__class__.__name__, feature))
        elif pin.xdr not in xdrs:
            raise NotImplementedError("Platform {} does not support {} for XDR {}"
                                      .format(self.__class__.__name__, feature, pin.xdr))

    def get_input(self, pin, port):
        self._check_feature("single-ended input", pin, xdrs=(1,))

        m = Module()
        m.d.comb += pin.i.eq(port)
        return m

    def get_output(self, pin, port):
        self._check_feature("single-ended output", pin, xdrs=(1,))

        m = Module()
        m.d.comb += port.eq(pin.o)
        return m

    def get_tristate(self, pin, port):
        self._check_feature("single-ended tristate", pin, xdrs=(1,))

        m = Module()
        m.submodules += Instance("$tribuf",
            p_WIDTH=pin.width,
            i_EN=pin.oe,
            i_A=pin.o,
            o_Y=port,
        )
        m.d.comb += pin.i.eq(port)
        return m

    def get_diff_input(self, pin, p_port, n_port):
        self._check_feature("differential input", pin, xdrs=())

    def get_diff_output(self, pin, p_port, n_port):
        self._check_feature("differential output", pin, xdrs=())

    def get_diff_tristate(self, pin, p_port, n_port):
        self._check_feature("differential tristate", pin, xdrs=())


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
            {{emit_commands("bat")}}
        """,
    }

    def toolchain_prepare(self, fragment, name, **kwargs):
        # This notice serves a dual purpose: to explain that the file is autogenerated,
        # and to incorporate
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
                return os.environ[var_env]
            elif var in kwargs:
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
                          render(content_tpl, origin=filename_tpl))
        for filename, content in self.extra_files.items():
            plan.add_file(filename, content)
        return plan
