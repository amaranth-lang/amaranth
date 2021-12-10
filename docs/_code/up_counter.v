(* generator = "Amaranth" *)
module top(clk, rst, en, ovf);
  (* src = "<amaranth-root>/amaranth/hdl/ir.py:526" *)
  input clk;
  (* src = "<amaranth-root>/amaranth/hdl/ir.py:526" *)
  input rst;
  (* src = "up_counter.py:26" *)
  input en;
  (* src = "up_counter.py:27" *)
  output ovf;
  (* src = "up_counter.py:30" *)
  reg [15:0] count = 16'h0000;
  (* src = "up_counter.py:30" *)
  reg [15:0] \count$next ;
  (* src = "up_counter.py:35" *)
  wire \$1 ;
  (* src = "up_counter.py:41" *)
  wire [16:0] \$3 ;
  (* src = "up_counter.py:41" *)
  wire [16:0] \$4 ;
  assign \$1  = count == (* src = "up_counter.py:35" *) 5'h19;
  assign \$4  = count + (* src = "up_counter.py:41" *) 1'h1;
  always @(posedge clk)
      count <= \count$next ;
  always @* begin
    \count$next  = count;
    (* src = "up_counter.py:37" *)
    casez (en)
      /* src = "up_counter.py:37" */
      1'h1:
          (* src = "up_counter.py:38" *)
          casez (ovf)
            /* src = "up_counter.py:38" */
            1'h1:
                \count$next  = 16'h0000;
            /* src = "up_counter.py:40" */
            default:
                \count$next  = \$3 [15:0];
          endcase
    endcase
    (* src = "<amaranth-root>/amaranth/hdl/xfrm.py:518" *)
    casez (rst)
      1'h1:
          \count$next  = 16'h0000;
    endcase
  end
  assign \$3  = \$4 ;
  assign ovf = \$1 ;
endmodule
