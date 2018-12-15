*The text below is the original nMigen implementation proposal. It is provided for illustrative and historical purposes only.*

This repository contains a proposal for the design of nMigen in form of an implementation. This implementation deviates from the existing design of Migen by making several observations of its drawbacks:

  * Migen is strongly tailored towards Verilog, yet translation of Migen to Verilog is not straightforward, leaves much semantics implicit (e.g. signedness, width extension, combinatorial assignments, sub-signal assignments...);
  * Hierarchical designs are useful for floorplanning and optimization, yet Migen does not support them at all;
  * Migen's syntax is not easily composable, and something like an FSM requires extending Migen's syntax in non-orthogonal ways;
  * Migen reimplements a lot of mature open-source tooling, such as conversion of RTL to Verilog (Yosys' Verilog backend), or simulation (Icarus Verilog, Verilator, etc.), and often lacks in features, speed, or corner case handling.
  * Migen requires awkward specials for some FPGA features such as asynchronous resets.

It also observes that Yosys' intermediate language, RTLIL, is an ideal target for Migen-style logic, as conversion of FHDL to RTLIL is essentially a 1:1 translation, with the exception of the related issues of naming and hierarchy.

This proposal makes several major changes to Migen that hopefully solve all of these drawbacks:

  * nMigen changes FHDL's internal representation to closely match that of RTLIL;
  * nMigen outputs RTLIL and relies on Yosys for conversion to Verilog, EDIF, etc;
  * nMigen uses an exact mapping between FHDL signals and RTLIL names to off-load logic simulation to Icarus Verilog, Verilator, etc;
  * nMigen uses an uniform, composable Python eHDL;
  * nMigen outputs hierarchical RTLIL, automatically threading signals through the hierarchy;
  * nMigen supports asynchronous reset directly;
  * nMigen makes driving a signal from multiple clock domains a precise, hard error.

This proposal keeps in mind but does not make the following major changes:

  * nMigen could be easily modified to flatten the hierarchy if a signal is driven simultaneously from multiple modules;
  * nMigen could be easily modified to support `x` values (invalid / don't care) by relying on RTLIL's ability to directly represent them;
  * nMigen could be easily modified to support negative edge triggered flip-flops by relying on RTLIL's ability to directly represent them;
  * nMigen could be easily modified to track Python source locations of primitives and export them to RTLIL/Verilog through the `src` attribute, displaying the Python source locations in timing reports directly.

This proposal also makes the following simplifications:
  * Specials are eliminated. Primitives such as memory ports are represented directly, and primitives such as tristate buffers are lowered to a selectable implementation via ordinary dependency injection (`f.submodules += platform.get_tristate(triple, io)`).

The internals of nMigen in this proposal are cleaned up, yet they are kept sufficiently close to Migen that \~all Migen code should be possible to run directly on nMigen using a syntactic compatibility layer.

One might reasonably expect that a roundtrip through RTLIL would result in unreadable Verilog.
However, this is not the case, e.g. consider the examples:

<details>
<summary>alu.v</summary>

```verilog
module \$1 (co, sel, a, b, o);
  wire [17:0] _04_;
  input [15:0] a;
  input [15:0] b;
  output co;
  reg \co$next ;
  output [15:0] o;
  reg [15:0] \o$next ;
  input [1:0] sel;
  assign _04_ = $signed(+ a) + $signed(- b);
  always @* begin
    \o$next  = 16'h0000;
    \co$next  = 1'h0;
    casez ({ 1'h1, sel == 2'h2, sel == 1'h1, sel == 0'b0 })
      4'bzzz1:
          \o$next  = a | b;
      4'bzz1z:
          \o$next  = a & b;
      4'bz1zz:
          \o$next  = a ^ b;
      4'b1zzz:
          { \co$next , \o$next  } = _04_[16:0];
    endcase
  end
  assign o = \o$next ;
  assign co = \co$next ;
endmodule
```
</details>

<details>
<summary>alu_hier.v</summary>

```verilog
module add(b, o, a);
  wire [16:0] _0_;
  input [15:0] a;
  input [15:0] b;
  output [15:0] o;
  reg [15:0] \o$next ;
  assign _0_ = a + b;
  always @* begin
    \o$next  = 16'h0000;
    \o$next  = _0_[15:0];
  end
  assign o = \o$next ;
endmodule

module sub(b, o, a);
  wire [16:0] _0_;
  input [15:0] a;
  input [15:0] b;
  output [15:0] o;
  reg [15:0] \o$next ;
  assign _0_ = a - b;
  always @* begin
    \o$next  = 16'h0000;
    \o$next  = _0_[15:0];
  end
  assign o = \o$next ;
endmodule

module top(a, b, o, add_o, sub_o, op);
  input [15:0] a;
  wire [15:0] add_a;
  reg [15:0] \add_a$next ;
  wire [15:0] add_b;
  reg [15:0] \add_b$next ;
  input [15:0] add_o;
  input [15:0] b;
  output [15:0] o;
  reg [15:0] \o$next ;
  input op;
  wire [15:0] sub_a;
  reg [15:0] \sub_a$next ;
  wire [15:0] sub_b;
  reg [15:0] \sub_b$next ;
  input [15:0] sub_o;
  add add (
    .a(add_a),
    .b(add_b),
    .o(add_o)
  );
  sub sub (
    .a(sub_a),
    .b(sub_b),
    .o(sub_o)
  );
  always @* begin
    \o$next  = 16'h0000;
    \add_a$next  = 16'h0000;
    \add_b$next  = 16'h0000;
    \sub_a$next  = 16'h0000;
    \sub_b$next  = 16'h0000;
    \add_a$next  = a;
    \sub_a$next  = a;
    \add_b$next  = b;
    \sub_b$next  = b;
    casez ({ 1'h1, op })
      2'bz1:
          \o$next  = sub_o;
      2'b1z:
          \o$next  = add_o;
    endcase
  end
  assign o = \o$next ;
  assign add_a = \add_a$next ;
  assign add_b = \add_b$next ;
  assign sub_a = \sub_a$next ;
  assign sub_b = \sub_b$next ;
endmodule
```
</details>
<details>
<summary>clkdiv.v</summary>

```verilog
module \$1 (sys_clk, o);
  wire [16:0] _0_;
  output o;
  reg \o$next ;
  input sys_clk;
  wire sys_rst;
  (* init = 16'hffff *)
  reg [15:0] v = 16'hffff;
  reg [15:0] \v$next ;
  assign _0_ = v + 1'h1;
  always @(posedge sys_clk)
      v <= \v$next ;
  always @* begin
    \o$next  = 1'h0;
    \v$next  = _0_[15:0];
    \o$next  = v[15];
    casez (sys_rst)
      1'h1:
          \v$next  = 16'hffff;
    endcase
  end
  assign o = \o$next ;
endmodule
```
</details>

<details>
<summary>arst.v</summary>

```verilog
module \$1 (o, sys_clk, sys_rst);
  wire [16:0] _0_;
  output o;
  reg \o$next ;
  input sys_clk;
  input sys_rst;
  (* init = 16'h0000 *)
  reg [15:0] v = 16'h0000;
  reg [15:0] \v$next ;
  assign _0_ = v + 1'h1;
  always @(posedge sys_clk or posedge sys_rst)
    if (sys_rst)
      v <= 16'h0000;
    else
      v <= \v$next ;
  always @* begin
    \o$next  = 1'h0;
    \v$next  = _0_[15:0];
    \o$next  = v[15];
  end
  assign o = \o$next ;
endmodule
```
</details>

<details>
<summary>pmux.v</summary>

```verilog
module \$1 (c, o, s, a, b);
  input [15:0] a;
  input [15:0] b;
  input [15:0] c;
  output [15:0] o;
  reg [15:0] \o$next ;
  input [2:0] s;
  always @* begin
    \o$next  = 16'h0000;
    casez (s)
      3'bzz1:
          \o$next  = a;
      3'bz1z:
          \o$next  = b;
      3'b1zz:
          \o$next  = c;
      3'hz:
          \o$next  = 16'h0000;
    endcase
  end
  assign o = \o$next ;
endmodule
```
</details>
