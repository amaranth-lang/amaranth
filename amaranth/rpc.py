import sys
import json
import argparse
import importlib

from .hdl import Signal, Record, Elaboratable
from .back import rtlil


__all__ = ["main"]


def _collect_modules(names):
    modules = {}
    for name in names:
        py_module_name, py_class_name = name.rsplit(".", 1)
        py_module = importlib.import_module(py_module_name)
        if py_class_name == "*":
            for py_class_name in py_module.__all__:
                py_class = py_module.__dict__[py_class_name]
                if not issubclass(py_class, Elaboratable):
                    continue
                modules[f"{py_module_name}.{py_class_name}"] = py_class
        else:
            py_class = py_module.__dict__[py_class_name]
            if not isinstance(py_class, type) or not issubclass(py_class, Elaboratable):
                raise TypeError("{}.{} is not a class inheriting from Elaboratable"
                                .format(py_module_name, py_class_name))
            modules[name] = py_class
    return modules


def _serve_yosys(modules):
    while True:
        request_json = sys.stdin.readline()
        if not request_json: break
        request = json.loads(request_json)

        if request["method"] == "modules":
            response = {"modules": list(modules.keys())}

        elif request["method"] == "derive":
            module_name = request["module"]

            args, kwargs = [], {}
            for parameter_name, parameter in request["parameters"].items():
                if parameter["type"] == "unsigned":
                    parameter_value = int(parameter["value"], 2)
                elif parameter["type"] == "signed":
                    width = len(parameter["value"])
                    parameter_value = int(parameter["value"], 2)
                    if parameter_value & (1 << (width - 1)):
                        parameter_value = -((1 << width) - parameter_value)
                elif parameter["type"] == "string":
                    parameter_value = parameter["value"]
                elif parameter["type"] == "real":
                    parameter_value = float(parameter["value"])
                else:
                    raise NotImplementedError("Unrecognized parameter type {}"
                                              .format(parameter_name))
                if parameter_name.startswith("$"):
                    index = int(parameter_name[1:])
                    while len(args) < index:
                        args.append(None)
                    args[index] = parameter_value
                if parameter_name.startswith("\\"):
                    kwargs[parameter_name[1:]] = parameter_value

            try:
                elaboratable = modules[module_name](*args, **kwargs)
                ports = []
                # By convention, any public attribute that is a Signal or a Record is
                # considered a port.
                for port_name, port in vars(elaboratable).items():
                    if not port_name.startswith("_") and isinstance(port, (Signal, Record)):
                        ports += port._lhs_signals()
                rtlil_text = rtlil.convert(elaboratable, name=module_name, ports=ports)
                response = {"frontend": "ilang", "source": rtlil_text}
            except Exception as error:
                response = {"error": f"{type(error).__qualname__}: {str(error)}"}

        else:
            return {"error": "Unrecognized method {!r}".format(request["method"])}

        sys.stdout.write(json.dumps(response))
        sys.stdout.write("\n")
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=r"""
    The Amaranth RPC server allows a HDL synthesis program to request an Amaranth module to
    be elaborated on demand using the parameters it provides. For example, using Yosys together
    with the Amaranth RPC server allows instantiating parametric Amaranth modules directly
    from Verilog.
    """)
    def add_modules_arg(parser):
        parser.add_argument("modules", metavar="MODULE", type=str, nargs="+",
            help="import and provide MODULES")
    protocols = parser.add_subparsers(metavar="PROTOCOL", dest="protocol", required=True)
    protocol_yosys = protocols.add_parser("yosys", help="use Yosys JSON-based RPC protocol")
    add_modules_arg(protocol_yosys)

    args = parser.parse_args()
    modules = _collect_modules(args.modules)
    if args.protocol == "yosys":
        _serve_yosys(modules)


if __name__ == "__main__":
    main()
