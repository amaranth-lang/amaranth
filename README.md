# Amaranth HDL (previously nMigen)

The Amaranth project provides an open-source toolchain for developing hardware based on synchronous digital logic using the Python programming language, as well as [evaluation board definitions][amaranth-boards], a [System on Chip toolkit][amaranth-soc], and more. It aims to be easy to learn and use, reduce or eliminate common coding mistakes, and simplify the design of complex hardware with reusable components.

The Amaranth toolchain consists of the Amaranth hardware definition language, the standard library, the simulator, and the build system, covering all steps of a typical FPGA development workflow. At the same time, it does not restrict the designer’s choice of tools: existing industry-standard (System)Verilog or VHDL code can be integrated into an Amaranth-based design flow, or, conversely, Amaranth code can be integrated into an existing Verilog-based design flow.

[amaranth-boards]: https://github.com/amaranth-lang/amaranth-boards
[amaranth-soc]: https://github.com/amaranth-lang/amaranth-soc

The development of Amaranth has been supported by [SymbioticEDA][], [LambdaConcept][], and [ChipEleven][].

[yosys]: https://yosyshq.net/yosys/
[symbioticeda]: https://www.symbioticeda.com/
[lambdaconcept]: http://lambdaconcept.com/
[chipeleven]: https://chipeleven.com/

## Introduction

See the [Introduction](https://amaranth-lang.org/docs/amaranth/latest/intro.html) section of the documentation.

## Installation

See the [Installation](https://amaranth-lang.org/docs/amaranth/latest/install.html) section of the documentation.

## Supported devices

Amaranth can be used to target any FPGA or ASIC process that accepts behavioral Verilog-2001 as input. It also offers extended support for many FPGA families, providing toolchain integration, abstractions for device-specific primitives, and more. Specifically:

  * Lattice iCE40 (toolchains: **Yosys+nextpnr**, LSE-iCECube2, Synplify-iCECube2);
  * Lattice MachXO2 (toolchains: Diamond);
  * Lattice MachXO3L (toolchains: Diamond);
  * Lattice ECP5 (toolchains: **Yosys+nextpnr**, Diamond);
  * Xilinx Spartan 3A (toolchains: ISE);
  * Xilinx Spartan 6 (toolchains: ISE);
  * Xilinx 7-series (toolchains: Vivado);
  * Xilinx UltraScale (toolchains: Vivado);
  * Intel (toolchains: Quartus);
  * Quicklogic EOS S3 (toolchains: **Yosys+VPR**).

FOSS toolchains are listed in **bold**.

## Migration from Migen

If you have existing Migen code, you can use a comprehensive Migen compatibility layer provided in Amaranth. An existing Migen design can be synthesized and simulated with Amaranth in three steps:

  1. Replace all `from migen import <...>` statements with `from amaranth.compat import <...>`.
  2. Replace every explicit mention of the default `sys` clock domain with the new default `sync` clock domain. E.g. `ClockSignal("sys")` is changed to `ClockSignal("sync")`.
  3. Migrate from Migen build/platform system to Amaranth build/platform system. Amaranth does not provide a build/platform compatibility layer because both the board definition files and the platform abstraction differ too much.

Note that Amaranth will **not** produce the exact same RTL as Migen did. Amaranth has been built to allow you to take advantage of the new and improved functionality it has (such as producing hierarchical RTL) while making migration as painless as possible.

Once your design passes verification with Amaranth, you can migrate it to the Amaranth syntax one module at a time. Migen modules can be added to Amaranth modules and vice versa, so there is no restriction on the order of migration, either.

## Community

Amaranth has a dedicated IRC channel, [#amaranth-lang at libera.chat](https://web.libera.chat/#amaranth-lang). Feel free to join to ask questions about using Amaranth or discuss ongoing development of Amaranth and its related projects.

## License

Amaranth is released under the very permissive [two-clause BSD license](LICENSE.txt). Under the terms of this license, you are authorized to use Amaranth for closed-source proprietary designs.
