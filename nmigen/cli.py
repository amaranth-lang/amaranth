import argparse

from .hdl.ir import Fragment
from .back import rtlil, verilog, pysim


__all__ = ["main"]


def main_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    p_action = parser.add_subparsers(dest="action")

    p_generate = p_action.add_parser("generate",
        help="generate RTLIL or Verilog from the design")
    p_generate.add_argument("-t", "--type", dest="generate_type",
        metavar="LANGUAGE", choices=["il", "v"],
        default="v",
        help="generate LANGUAGE (il for RTLIL, v for Verilog; default: %(default)s)")
    p_generate.add_argument("generate_file",
        metavar="FILE", type=argparse.FileType("w"), nargs="?",
        help="write generated code to FILE")

    p_simulate = p_action.add_parser(
        "simulate", help="simulate the design")
    p_simulate.add_argument("-v", "--vcd-file",
        metavar="VCD-FILE", type=argparse.FileType("w"),
        help="write execution trace to VCD-FILE")
    p_simulate.add_argument("-w", "--gtkw-file",
        metavar="GTKW-FILE", type=argparse.FileType("w"),
        help="write GTKWave configuration to GTKW-FILE")
    p_simulate.add_argument("-p", "--period", dest="sync_period",
        metavar="TIME", type=float, default=1e-6,
        help="set 'sync' clock domain period to TIME (default: %(default)s)")
    p_simulate.add_argument("-c", "--clocks", dest="sync_clocks",
        metavar="COUNT", type=int, required=True,
        help="simulate for COUNT 'sync' clock periods")

    return parser


def main_runner(parser, args, design, platform=None, name="top", ports=()):
    if args.action == "generate":
        fragment = Fragment.get(design, platform)
        generate_type = args.generate_type
        if generate_type is None and args.generate_file:
            if args.generate_file.name.endswith(".v"):
                generate_type = "v"
            if args.generate_file.name.endswith(".il"):
                generate_type = "il"
        if generate_type is None:
            parser.error("specify file type explicitly with -t")
        if generate_type == "il":
            output = rtlil.convert(fragment, name=name, ports=ports)
        if generate_type == "v":
            output = verilog.convert(fragment, name=name, ports=ports)
        if args.generate_file:
            args.generate_file.write(output)
        else:
            print(output)

    if args.action == "simulate":
        fragment = Fragment.get(design, platform)
        with pysim.Simulator(fragment,
                vcd_file=args.vcd_file,
                gtkw_file=args.gtkw_file,
                traces=ports) as sim:
            sim.add_clock(args.sync_period)
            sim.run_until(args.sync_period * args.sync_clocks, run_passive=True)


def main(*args, **kwargs):
    parser = main_parser()
    main_runner(parser, parser.parse_args(), *args, **kwargs)
