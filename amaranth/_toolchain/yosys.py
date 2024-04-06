import os
import sys
import re
import subprocess
import warnings
import pathlib
from importlib import metadata as importlib_metadata
try:
    from importlib import resources as importlib_resources
    try:
        importlib_resources.files # py3.9+ stdlib
    except AttributeError:
        import importlib_resources # py3.8- shim
except ImportError:
    importlib_resources = None

from . import has_tool, require_tool


__all__ = ["YosysError", "YosysBinary", "find_yosys"]


class YosysError(Exception):
    pass


class YosysWarning(Warning):
    pass


class YosysBinary:
    @classmethod
    def available(cls):
        """Check for Yosys availability.

        Returns
        -------
        available : bool
            ``True`` if Yosys is installed, ``False`` otherwise. Installed binary may still not
            be runnable, or might be too old to be useful.
        """
        raise NotImplementedError

    @classmethod
    def version(cls):
        """Get Yosys version.

        Returns
        -------
        ``None`` if version number could not be determined, or a 3-tuple ``(major, minor, distance)`` if it could.

        major : int
            Major version.
        minor : int
            Minor version.
        distance : int
            Distance to last tag per ``git describe``. May not be exact for system Yosys.
        """
        raise NotImplementedError

    @classmethod
    def data_dir(cls):
        """Get Yosys data directory.

        Returns
        -------
        data_dir : pathlib.Path
            Yosys data directory (also known as "datdir").
        """
        raise NotImplementedError

    @classmethod
    def run(cls, args, stdin=""):
        """Run Yosys process.

        Parameters
        ----------
        args : list of str
            Arguments, not including the program name.
        stdin : str
            Standard input.

        Returns
        -------
        stdout : str
            Standard output.

        Exceptions
        ----------
        YosysError
            Raised if Yosys returns a non-zero code. The exception message is the standard error
            output.
        """
        raise NotImplementedError

    @classmethod
    def _process_result(cls, returncode, stdout, stderr, ignore_warnings, src_loc_at):
        if returncode:
            raise YosysError(stderr.strip())
        if not ignore_warnings:
            for match in re.finditer(r"(?ms:^Warning: (.+)\n$)", stderr):
                message = match.group(1).replace("\n", " ")
                warnings.warn(message, YosysWarning, stacklevel=3 + src_loc_at)
        return stdout


class _BuiltinYosys(YosysBinary):
    YOSYS_PACKAGE = "amaranth_yosys"

    @classmethod
    def available(cls):
        if importlib_metadata is None or importlib_resources is None:
            return False
        try:
            importlib_metadata.version(cls.YOSYS_PACKAGE)
            return True
        except importlib_metadata.PackageNotFoundError:
            return False

    @classmethod
    def version(cls):
        version = importlib_metadata.version(cls.YOSYS_PACKAGE)
        match = re.match(r"^(\d+)\.(\d+)\.(?:\d+)(?:\.(\d+))?(?:\.post(\d+))?", version)
        return (int(match[1]), int(match[2]), int(match[3] or 0), int(match[4] or 0))

    @classmethod
    def data_dir(cls):
        return importlib_resources.files(cls.YOSYS_PACKAGE) / "share"

    @classmethod
    def run(cls, args, stdin="", *, ignore_warnings=False, src_loc_at=0):
        popen = subprocess.Popen([sys.executable, "-m", cls.YOSYS_PACKAGE, *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8")
        stdout, stderr = popen.communicate(stdin)
        return cls._process_result(popen.returncode, stdout, stderr, ignore_warnings, src_loc_at)


class _SystemYosys(YosysBinary):
    YOSYS_BINARY = "yosys"

    @classmethod
    def available(cls):
        return has_tool(cls.YOSYS_BINARY)

    @classmethod
    def version(cls):
        version = cls.run(["-V"])
        match = re.match(r"^Yosys (\d+)\.(\d+)(?:\+(\d+))?", version)
        if match:
            return (int(match[1]), int(match[2]), int(match[3] or 0))
        else:
            return None

    @classmethod
    def data_dir(cls):
        popen = subprocess.Popen([require_tool(cls.YOSYS_BINARY) + "-config", "--datdir"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8")
        stdout, stderr = popen.communicate()
        if popen.returncode:
            raise YosysError(stderr.strip())
        return pathlib.Path(stdout.strip())

    @classmethod
    def run(cls, args, stdin="", *, ignore_warnings=False, src_loc_at=0):
        popen = subprocess.Popen([require_tool(cls.YOSYS_BINARY), *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8")
        stdout, stderr = popen.communicate(stdin)
        # If Yosys is built with an evaluation version of Verific, then Verific license
        # information is printed first. It consists of empty lines and lines starting with `--`,
        # which are not normally a part of Yosys output, and can be fairly safely removed.
        #
        # This is not ideal, but Verific license conditions rule out any other solution.
        stdout = re.sub(r"\A(-- .+\n|\n)*", "", stdout)
        return cls._process_result(popen.returncode, stdout, stderr, ignore_warnings, src_loc_at)


class _JavaScriptYosys(YosysBinary):
    """
    This toolchain proxy is compatible with Pyodide_. The JavaScript environment must include
    the following function:

    .. code::

        runAmaranthYosys(args: string[], stdin: string): (exit_code: int, stdout: string, stderr: string);

    .. _Pyodide: https://pyodide.org/
    """

    @classmethod
    def available(cls):
        try:
            return hasattr(__import__("js"), "runAmaranthYosys")
        except ImportError:
            return False

    @classmethod
    def version(cls):
        version = cls.run(["-V"])
        match = re.match(r"^Yosys (\d+)\.(\d+)(?:\+(\d+))?", version)
        if match:
            return (int(match[1]), int(match[2]), int(match[3] or 0))
        else:
            return None

    @classmethod
    def data_dir(cls):
        # Not yet clear how this could work in a design with Wasm components. Most likely,
        # the component would have to export its filesystem wholesale, and this method would
        # return some kind of non-filesystem path-like object.
        raise NotImplementedError

    @classmethod
    def run(cls, args, stdin="", *, ignore_warnings=False, src_loc_at=0):
        exit_code, stdout, stderr = __import__("js").runAmaranthYosys(args, stdin)
        return cls._process_result(exit_code, stdout, stderr, ignore_warnings, src_loc_at)


def find_yosys(requirement):
    """Find an available Yosys executable of required version.

    Parameters
    ----------
    requirement : function
        Version check. Should return ``True`` if the version is acceptable, ``False`` otherwise.

    Returns
    -------
    yosys_binary : subclass of YosysBinary
        Proxy for running the requested version of Yosys.

    Exceptions
    ----------
    YosysError
        Raised if required Yosys version is not found.
    """
    proxies = []
    clauses = os.environ.get("AMARANTH_USE_YOSYS", "system,builtin").split(",")
    for clause in clauses:
        if clause == "builtin":
            proxies.append(_BuiltinYosys)
        elif clause == "system":
            proxies.append(_SystemYosys)
        elif clause == "javascript":
            proxies.append(_JavaScriptYosys)
        else:
            raise YosysError("The AMARANTH_USE_YOSYS environment variable contains "
                             "an unrecognized clause {!r}"
                             .format(clause))
    for proxy in proxies:
        if proxy.available():
            version = proxy.version()
            if version is not None and requirement(version):
                return proxy
    else:
        if "AMARANTH_USE_YOSYS" in os.environ:
            raise YosysError("Could not find an acceptable Yosys binary. Searched: {}"
                             .format(", ".join(clauses)))
        else:
            raise YosysError("Could not find an acceptable Yosys binary. The `amaranth-yosys` PyPI "
                             "package, if available for this platform, can be used as fallback")
