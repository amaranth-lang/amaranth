import tempfile
import sysconfig
import os.path
from distutils import ccompiler


__all__ = ["build_cxx"]


def build_cxx(*, cxx_sources, output_name, include_dirs, macros):
    build_dir = tempfile.TemporaryDirectory(prefix="nmigen_cxx_")

    cwd = os.getcwd()
    try:
        # Unforuntately, `ccompiler.compile` assumes the paths are relative, and interprets
        # the directory name of the source path specially. That makes it necessary to build in
        # the output directory directly.
        os.chdir(build_dir.name)

        cc_driver = ccompiler.new_compiler()
        cc_driver.output_dir = "."

        cc = sysconfig.get_config_var("CC")
        cxx = sysconfig.get_config_var("CXX")
        cflags = sysconfig.get_config_var("CCSHARED")
        ld_ldflags = sysconfig.get_config_var("LDCXXSHARED")
        cc_driver.set_executables(
            compiler=f"{cc} {cflags}",
            compiler_so=f"{cc} {cflags}",
            compiler_cxx=f"{cxx} {cflags}",
            linker_so=ld_ldflags,
        )

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
