import os


__all__ = ["get_tool"]


def get_tool(name):
    return os.environ.get(name.upper().replace("-", "_"), overrides.get(name, name))


# Packages for systems like Nix can inject full paths to certain tools by adding them in
# this dictionary, e.g. ``overrides = {"yosys": "/full/path/to/yosys"}``.
overrides = {}
