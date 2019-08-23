from collections import OrderedDict
from contextlib import contextmanager
from abc import ABCMeta, abstractmethod
import os
import sys
import subprocess
import tempfile
import zipfile
import hashlib


__all__ = ["BuildPlan", "BuildProducts", "LocalBuildProducts"]


class BuildPlan:
    def __init__(self, script):
        """A build plan.

        Parameters
        ----------
        script : str
            The base name (without extension) of the script that will be executed.
        """
        self.script = script
        self.files  = OrderedDict()

    def add_file(self, filename, content):
        """
        Add ``content``, which can be a :class:`str`` or :class:`bytes`, to the build plan
        as ``filename``. The file name can be a relative path with directories separated by
        forward slashes (``/``).
        """
        assert isinstance(filename, str) and filename not in self.files
        self.files[filename] = content

    def digest(self, size=64):
        """
        Compute a `digest`, a short byte sequence deterministically and uniquely identifying
        this build plan.
        """
        hasher = hashlib.blake2b(digest_size=size)
        for filename in sorted(self.files):
            hasher.update(filename.encode("utf-8"))
            content = self.files[filename]
            if isinstance(content, str):
                content = content.encode("utf-8")
            hasher.update(content)
        hasher.update(self.script.encode("utf-8"))
        return hasher.digest()

    def archive(self, file):
        """
        Archive files from the build plan into ``file``, which can be either a filename, or
        a file-like object. The produced archive is deterministic: exact same files will
        always produce exact same archive.
        """
        with zipfile.ZipFile(file, "w") as archive:
            # Write archive members in deterministic order and with deterministic timestamp.
            for filename in sorted(self.files):
                archive.writestr(zipfile.ZipInfo(filename), self.files[filename])

    def execute_local(self, root="build", *, run_script=True):
        """
        Execute build plan using the local strategy. Files from the build plan are placed in
        the build root directory ``root``, and, if ``run_script`` is ``True``, the script
        appropriate for the platform (``{script}.bat`` on Windows, ``{script}.sh`` elsewhere) is
        executed in the build root.

        Returns :class:`LocalBuildProducts`.
        """
        os.makedirs(root, exist_ok=True)
        cwd = os.getcwd()
        try:
            os.chdir(root)

            for filename, content in self.files.items():
                filename = os.path.normpath(filename)
                # Just to make sure we don't accidentally overwrite anything outside of build root.
                assert not filename.startswith("..")
                dirname = os.path.dirname(filename)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)

                mode = "wt" if isinstance(content, str) else "wb"
                with open(filename, mode) as f:
                    f.write(content)

            if run_script:
                if sys.platform.startswith("win32"):
                    # Without "call", "cmd /c {}.bat" will return 0.
                    # See https://stackoverflow.com/a/30736987 for a detailed
                    # explanation of why, including disassembly/decompilation
                    # of relevant code in cmd.exe.
                    # Running the script manually from a command prompt is
                    # unaffected- i.e. "call" is not required.
                    subprocess.check_call(["cmd", "/c", "call {}.bat".format(self.script)])
                else:
                    subprocess.check_call(["sh", "{}.sh".format(self.script)])

                return LocalBuildProducts(os.getcwd())

        finally:
            os.chdir(cwd)

    def execute(self):
        """
        Execute build plan using the default strategy. Use one of the ``execute_*`` methods
        explicitly to have more control over the strategy.
        """
        return self.execute_local()


class BuildProducts(metaclass=ABCMeta):
    @abstractmethod
    def get(self, filename, mode="b"):
        """
        Extract ``filename`` from build products, and return it as a :class:`bytes` (if ``mode``
        is ``"b"``) or a :class:`str` (if ``mode`` is ``"t"``).
        """
        assert mode in ("b", "t")

    @contextmanager
    def extract(self, *filenames):
        """
        Extract ``filenames`` from build products, place them in an OS-specific temporary file
        location, with the extension preserved, and delete them afterwards. This method is used
        as a context manager, e.g.: ::

            with products.extract("bitstream.bin", "programmer.cfg") \
                    as bitstream_filename, config_filename:
                subprocess.check_call(["program", "-c", config_filename, bitstream_filename])
        """
        files = []
        try:
            for filename in filenames:
                # On Windows, a named temporary file (as created by Python) is not accessible to
                # others if it's still open within the Python process, so we close it and delete
                # it manually.
                file = tempfile.NamedTemporaryFile(prefix="nmigen_", suffix="_" + filename,
                                                   delete=False)
                files.append(file)
                file.write(self.get(filename))
                file.close()

            if len(files) == 0:
                return (yield)
            elif len(files) == 1:
                return (yield files[0].name)
            else:
                return (yield [file.name for file in files])
        finally:
            for file in files:
                os.unlink(file.name)


class LocalBuildProducts(BuildProducts):
    def __init__(self, root):
        # We provide no guarantees that files will be available on the local filesystem (i.e. in
        # any way other than through `products.get()`) in general, so downstream code must never
        # rely on this, even when we happen to use a local build most of the time.
        self.__root = root

    def get(self, filename, mode="b"):
        super().get(filename, mode)
        with open(os.path.join(self.__root, filename), "r" + mode) as f:
            return f.read()
