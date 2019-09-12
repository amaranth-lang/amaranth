# nMigen

## A refreshed Python toolbox for building complex digital hardware

**Although nMigen is incomplete and in active development, it can already be used for real-world designs. The nMigen language (`nmigen.hdl.ast`, `nmigen.hdl.dsl`) will not undergo incompatible changes. The nMigen standard library (`nmigen.lib`) and build system (`nmigen.build`) will undergo minimal changes before their design is finalized.**

Despite being faster than schematics entry, hardware design with Verilog and VHDL remains tedious and inefficient for several reasons. The event-driven model introduces issues and manual coding that are unnecessary for synchronous circuits, which represent the lion's share of today's logic designs. Counterintuitive arithmetic rules result in steeper learning curves and provide a fertile ground for subtle bugs in designs. Finally, support for procedural generation of logic (metaprogramming) through "generate" statements is very limited and restricts the ways code can be made generic, reused and organized.

To address those issues, we have developed the *nMigen FHDL*, a library that replaces the event-driven paradigm with the notions of combinatorial and synchronous statements, has arithmetic rules that make integers always behave like mathematical integers, and most importantly allows the design's logic to be constructed by a Python program. This last point enables hardware designers to take advantage of the richness of the Python language—object oriented programming, function parameters, generators, operator overloading, libraries, etc.—to build well organized, reusable and elegant designs.

Other nMigen libraries are built on FHDL and provide various tools and logic cores. nMigen also contains a simulator that allows test benches to be written in Python.

See the [doc/](doc/) folder for more technical information.

nMigen is a direct descendant of [Migen][] rewritten from scratch to address many issues that became clear in the many years Migen has been used in production. nMigen provides an extensive compatibility layer that makes it possible to build and simulate most Migen designs unmodified, as well as integrate modules written for Migen and nMigen.

nMigen is designed for Python 3.6 and newer. nMigen's Verilog backend requires [Yosys][] 0.9 or a newer version.

Thanks [LambdaConcept][] for being a sponsor of this project! Contact sb [at] m-labs.hk if you also wish to support this work.

[migen]: https://m-labs.hk/migen
[yosys]: http://www.clifford.at/yosys/
[lambdaconcept]: http://lambdaconcept.com/

### HLS?

nMigen is *not* a "Python-to-FPGA" conventional high level synthesis (HLS) tool. It will *not* take a Python program as input and generate a hardware implementation of it. In nMigen, the Python program is executed by a regular Python interpreter, and it emits explicit statements in the FHDL domain-specific language.  Writing a conventional HLS tool that uses nMigen as an internal component might be a good idea, on the other hand :)

### Installation

nMigen requires [Yosys][] 0.9 or newer, as well as a device-specific toolchain.

    pip install git+https://github.com/m-labs/nmigen.git
    pip install git+https://github.com/m-labs/nmigen-boards.git

### Introduction

TBD

### Links

TBD

### License

nMigen is released under the very permissive two-clause BSD license. Under the terms of this license, you are authorized to use nMigen for closed-source proprietary designs.

Even though we do not require you to do so, these things are awesome, so please do them if possible:
  * tell us that you are using nMigen
  * put the [nMigen logo](doc/nmigen_logo.svg) on the page of a product using it, with a link to https://m-labs.hk
  * cite nMigen in publications related to research it has helped
  * send us feedback and suggestions for improvements
  * send us bug reports when something goes wrong
  * send us the modifications and improvements you have done to nMigen as pull requests on GitHub

See LICENSE file for full copyright and license info.

  "Electricity! It's like magic!"
