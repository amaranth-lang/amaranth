import os
import shutil


__all__ = ["ToolNotFound", "get_tool", "has_tool", "require_tool"]


class ToolNotFound(Exception):
    pass


def _tool_env_var(name):
    return name.upper().replace("-", "_")


def get_tool(name):
    return os.environ.get(_tool_env_var(name), overrides.get(name, name))


def has_tool(name):
    return shutil.which(get_tool(name)) is not None


def require_tool(name):
    env_var = _tool_env_var(name)
    path = get_tool(name)
    if shutil.which(path) is None:
        if path == name:
            raise ToolNotFound("Could not find required tool {} in PATH. Place "
                               "it directly in PATH or specify path explicitly "
                               "via the {} environment variable".
                               format(name, env_var))
        else:
            if os.getenv(env_var):
                via = "the {} environment variable".format(env_var)
            else:
                via = "your packager's toolchain overrides. This is either an " \
                      "nMigen bug or a packaging error"
            raise ToolNotFound("Could not find required tool {} in {} as "
                               "specified via {}".format(name, path, via))
    return path


# Packages for systems like Nix can inject full paths to certain tools by adding them in
# this dictionary, e.g. ``overrides = {"yosys": "/full/path/to/yosys"}``.
overrides = {}
