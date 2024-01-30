(* generator = "Amaranth" *)
module top(ovf, clk, rst, en);
  reg \$auto$verilog_backend.cc:2255:dump_module$1  = 0;
  (* src = "up_counter.py:36" *)
  wire \$1 ;
  (* src = "up_counter.py:42" *)
  wire [16:0] \$3 ;
  (* src = "up_counter.py:42" *)
  wire [16:0] \$4 ;
  (* src = "<site-packages>/amaranth/hdl/ir.py:509" *)
  input clk;
  wire clk;
  (* src = "up_counter.py:29" *)
  reg [15:0] count = 16'h0000;
  (* src = "up_counter.py:29" *)
  reg [15:0] \count$next ;
  (* src = "<site-packages>/amaranth/lib/wiring.py:1647" *)
  input en;
  wire en;
  (* src = "<site-packages>/amaranth/lib/wiring.py:1647" *)
  output ovf;
  wire ovf;
  (* src = "<site-packages>/amaranth/hdl/ir.py:509" *)
  input rst;
  wire rst;
  assign \$1  = count == (* src = "up_counter.py:36" *) 5'h19;
  assign \$4  = count + (* src = "up_counter.py:42" *) 1'h1;
  always @(posedge clk)
    count <= \count$next ;
  always @* begin
    if (\$auto$verilog_backend.cc:2255:dump_module$1 ) begin end
    \count$next  = count;
    (* src = "up_counter.py:38" *)
    if (en) begin
      (* full_case = 32'd1 *)
      (* src = "up_counter.py:39" *)
      if (ovf) begin
        \count$next  = 16'h0000;
      end else begin
        \count$next  = \$4 [15:0];
      end
    end
    (* src = "<site-packages>/amaranth/hdl/xfrm.py:534" *)
    if (rst) begin
      \count$next  = 16'h0000;
    end
  end
  assign \$3  = \$4 ;
  assign ovf = \$1 ;
endmodule
