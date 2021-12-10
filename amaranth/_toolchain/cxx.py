import tempfile
import sysconfig
import warnings
import os.path


__all__ = ["build_cxx"]


def build_cxx(*, cxx_sources, output_name, include_dirs, macros):
    build_dir = tempfile.TemporaryDirectory(prefix="amaranth_cxx_")

    cwd = os.getcwd()
    try:
        # Unforuntately, `ccompiler.compile` assumes the paths are relative, and interprets
        # the directory name of the source path specially. That makes it necessary to build in
        # the output directory directly.
        os.chdir(build_dir.name)

        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", category=DeprecationWarning)
            # This emits a DeprecationWarning on Python 3.6 and 3.10.
            from setuptools import distutils
            cc_driver = distutils.ccompiler.new_compiler()

        cc_driver.output_dir = "."

        cc = sysconfig.get_config_var("CC")
        cxx = sysconfig.get_config_var("CXX")
        cflags = sysconfig.get_config_var("CCSHARED")
        ld_flags = sysconfig.get_config_var("LDSHARED")
        ld_cxxflags = sysconfig.get_config_var("LDCXXSHARED")
        if ld_cxxflags is None:
            # PyPy doesn't have LDCXXSHARED. Glue it together from CXX and LDSHARED and hope that
            # the result actually works; not many good options here.
            ld_cxxflags = " ".join([cxx.split()[0], *ld_flags.split()[1:]])
        cc_driver.set_executables(
            compiler=f"{cc} {cflags}",
            compiler_so=f"{cc} {cflags}",
            compiler_cxx=f"{cxx} {cflags}",
            linker_so=ld_cxxflags,
        )

        # Sometimes CCompiler is modified to have additional executable entries for compiling and
        # linking CXX shared objects (e.g. on Gentoo). These executables have to be set then.
        try:
            cc_driver.set_executables(
                compiler_so_cxx=f"{cxx} {cflags}",
                linker_so_cxx=ld_cxxflags,
            )
        except:
            pass

        for include_dir in include_dirs:
            cc_driver.add_include_dir(include_dir)
        for macro in macros:
            cc_driver.define_macro(macro)
        for cxx_filename, cxx_source in cxx_sources.items():
            with open(cxx_filename, "w") as f:
                f.write(cxx_source)

        cxx_filenames = list(cxx_sources.keys())
        obj_filenames = cc_driver.object_filenames(cxx_filenames)
        so_filename = cc_driver.shared_object_filename(output_name)

        cc_driver.compile(cxx_filenames)
        cc_driver.link_shared_object(obj_filenames, output_filename=so_filename, target_lang="c++")

        return build_dir, so_filename

    finally:
        os.chdir(cwd)
