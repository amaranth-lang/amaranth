# Amaranth HDL (previously nMigen)

The Amaranth project provides an open-source toolchain for developing hardware based on synchronous digital logic using the Python programming language, as well as [evaluation board definitions][amaranth-boards], a [System on Chip toolkit][amaranth-soc], and more. It aims to be easy to learn and use, reduce or eliminate common coding mistakes, and simplify the design of complex hardware with reusable components.

The Amaranth toolchain consists of the Amaranth hardware definition language, the standard library, the simulator, and the build system, covering all steps of a typical FPGA development workflow. At the same time, it does not restrict the designer’s choice of tools: existing industry-standard (System)Verilog or VHDL code can be integrated into an Amaranth-based design flow, or, conversely, Amaranth code can be integrated into an existing Verilog-based design flow.

[amaranth-boards]: https://github.com/amaranth-lang/amaranth-boards
[amaranth-soc]: https://github.com/amaranth-lang/amaranth-soc

The development of Amaranth has been supported by [LambdaConcept][], [ChipEleven][], and [Chipflow][].

[yosys]: https://yosyshq.net/yosys/
[lambdaconcept]: http://lambdaconcept.com/
[chipeleven]: https://chipeleven.com/
[chipflow]: https://chipflow.io/

## Introduction

See the [Introduction](https://amaranth-lang.org/docs/amaranth/latest/intro.html) section of the documentation.

## Installation

See the [Installation](https://amaranth-lang.org/docs/amaranth/latest/install.html) section of the documentation.

## Usage

See the [Language guide](https://amaranth-lang.org/docs/amaranth/latest/guide.html) section of the documentation.

## Platform support

Amaranth can be used to target any FPGA or ASIC process that accepts behavioral Verilog-2001 as input. It also offers extended support for many FPGA families, providing toolchain integration, abstractions for device-specific primitives, and more. Specifically:

  * Lattice iCE40 (toolchains: **Yosys+nextpnr**, LSE-iCECube2, Synplify-iCECube2);
  * Lattice MachXO2, MachXO3L (toolchains: **Yosys+nextpnr**, Diamond);
  * Lattice ECP5 (toolchains: **Yosys+nextpnr**, Diamond);
  * Lattice Nexus (toolchains: **Yosys+nextpnr**, Radiant);
  * AMD Virtex, Virtex E, Spartan 2, Spartan 2E (toolchains: ISE);
  * AMD Virtex II, Virtex II Pro (toolchains: ISE);
  * AMD Spartan 3, Spartan 3E, Spartan 3A, Spartan 3AN, Spartan 3A DSP (toolchains: ISE);
  * AMD Virtex 4, Virtex 5, Virtex 6 (toolchains: ISE);
  * AMD Spartan 6 (toolchains: ISE);
  * AMD 7-series (toolchains: Vivado, ISE);
  * AMD UltraScale, UltraScale+ (toolchains: Vivado);
  * Altera (toolchains: Quartus);
  * Quicklogic EOS S3 (toolchains: **Yosys+VPR**).

FOSS toolchains are listed in **bold**.

## Community

Amaranth has a dedicated IRC channel, [#amaranth-lang at libera.chat](https://web.libera.chat/#amaranth-lang), which is _bridged_[^1] to Matrix at [#amaranth-lang:matrix.org](https://matrix.to/#/#amaranth-lang:matrix.org). Feel free to join to ask questions about using Amaranth or discuss ongoing development of Amaranth and its related projects.

[^1]: The same messages appear on IRC and on Matrix, and one can participate in the discussion equally using either communication system.

## License

Amaranth is released under the [two-clause BSD license](LICENSE.txt). You are permitted to use Amaranth for open-source and proprietary designs provided that the copyright notice in the license file is reproduced.
