"""
This file is not a part of the Amaranth module tree because the CLI needs to emit Make-style
dependency files as a part of the generation process. In order for `from amaranth import *`
to work as a prelude, it has to load several of the files under `amaranth/`, which means
these will not be loaded later in the process, and not recorded as dependencies.
"""

import importlib
import argparse
import stat
import sys
import os
import re


def _build_parser():
    def component(reference):
        from amaranth import Elaboratable

        if m := re.match(r"(\w+(?:\.\w+)*):(\w+(?:\.\w+)*)", reference, re.IGNORECASE|re.ASCII):
            mod_name, qual_name = m[1], m[2]
            try:
                obj = importlib.import_module(mod_name)
            except ImportError as e:
                raise argparse.ArgumentTypeError(f"{mod_name!r} does not refer to "
                                 "an importable Python module") from e
            try:
                for attr in qual_name.split("."):
                    obj = getattr(obj, attr)
            except AttributeError as e:
                raise argparse.ArgumentTypeError(f"{qual_name!r} does not refer to an object "
                                 f"within the {mod_name!r} module") from e
            if not issubclass(obj, Elaboratable):
                raise argparse.ArgumentTypeError(f"'{qual_name}:{mod_name}' refers to an object that is not elaboratable")
            return obj
        else:
            raise argparse.ArgumentTypeError(f"{reference!r} can not be parsed as a Python object reference, "
                                             "expecting a name like: 'path.to.module:ObjectInModule'")

    parser = argparse.ArgumentParser(
        "amaranth", description="""
        Amaranth HDL command line interface.
        """)
    operation = parser.add_subparsers(
        metavar="OPERATION", help="operation to perform",
        dest="operation", required=True)

    op_generate = operation.add_parser(
        "generate", help="generate code in a different language from Amaranth code",
        aliases=("gen", "g"))
    op_generate.add_argument(
        metavar="COMPONENT", help="Amaranth component to convert, e.g. `pkg.mod:Cls`",
        dest="component", type=component)
    op_generate.add_argument(
        "-n", "--name", metavar="NAME", help="name of the toplevel module, also prefixed to others",
        dest="name", type=str, default=None)
    op_generate.add_argument(
        "-p", "--param", metavar=("NAME", "VALUE"), help="parameter(s) for the component",
        dest="params", nargs=2, type=str, action="append", default=[])
    gen_language = op_generate.add_subparsers(
        metavar="LANGUAGE", help="language to generate code in",
        dest="language", required=True)

    lang_verilog = gen_language.add_parser(
        "verilog", help="generate Verilog code")
    lang_verilog.add_argument(
        "-v", metavar="VERILOG-FILE", help="Verilog file to write",
        dest="verilog_file", type=argparse.FileType("w"))
    lang_verilog.add_argument(
        "-d", metavar="DEP-FILE", help="Make-style dependency file to write",
        dest="dep_file", type=argparse.FileType("w"))

    return parser


def main(args=None):
    # Hook the `open()` function to find out which files are being opened by Amaranth code.
    files_being_opened = set()
    special_file_opened = False
    def dep_audit_hook(event, args):
        nonlocal special_file_opened
        if files_being_opened is not None and event == "open":
            filename, mode, flags = args
            if mode is None or "r" in mode or "+" in mode:
                if isinstance(filename, bytes):
                    filename = filename.decode("utf-8")
                if isinstance(filename, str) and stat.S_ISREG(os.stat(filename).st_mode):
                    files_being_opened.add(filename)
                else:
                    special_file_opened = True
    sys.addaudithook(dep_audit_hook)

    # Parse arguments and instantiate components
    args = _build_parser().parse_args(args)
    if args.operation in ("generate", "gen", "g"):
        params = dict(args.params)
        params = {name: cls(params[name])
                  for name, cls in args.component.__init__.__annotations__.items()}
        component = args.component(**params)

    # Capture the set of opened files, as well as the loaded Python modules.
    files_opened, files_being_opened = files_being_opened, None
    modules_after = list(sys.modules.values())

    # Remove *.pyc files from the set of open files and replace them with their *.py equivalents.
    dep_files = set()
    dep_files.update(files_opened)
    for module in modules_after:
        if getattr(module, "__spec__", None) is None:
            continue
        if module.__spec__.cached in dep_files:
            dep_files.discard(module.__spec__.cached)
            dep_files.add(module.__spec__.origin)

    if args.operation in ("generate", "gen", "g"):
        if args.language == "verilog":
            # Generate Verilog file with `-v` or without arguments.
            if args.verilog_file or not (args.verilog_file or args.dep_file):
                from amaranth.back.verilog import convert
                code = convert(component, name=(args.name or args.component.__name__),)
                (args.verilog_file or sys.stdout).write(code)

            # Generate dependency file with `-d`.
            if args.verilog_file and args.dep_file:
                args.dep_file.write(f"{args.verilog_file.name}:")
                if not special_file_opened:
                    for file in sorted(dep_files):
                        args.dep_file.write(f" \\\n  {file}")
                    args.dep_file.write("\n")
                else:
                    args.dep_file.write(f"\n.PHONY: {args.verilog_file.name}\n")
