`timescale 1ns/1ps

// SHA-1 known-answer test for the corrected VTR-derived seed.  The expected
// digest is the FIPS 180-4 result for ASCII "abc".
module sha1_abc_tb;
  reg clk_i = 0;
  reg rst_i = 1;
  reg [31:0] text_i = 0;
  wire [31:0] text_o;
  reg [2:0] cmd_i = 0;
  reg cmd_w_i = 0;
  wire [3:0] cmd_o;
  reg [31:0] digest [0:4];
  reg [31:0] block_words [0:15];
  integer i;
  integer busy_cycles = 0;

  sha1 dut (.clk_i(clk_i), .rst_i(rst_i), .text_i(text_i), .text_o(text_o),
            .cmd_i(cmd_i), .cmd_w_i(cmd_w_i), .cmd_o(cmd_o));
  always #5 clk_i = ~clk_i;
  always @(negedge clk_i)
    if (!rst_i && cmd_o[3]) busy_cycles = busy_cycles + 1;

  initial begin
    repeat (2) @(negedge clk_i);
    rst_i = 0;
    block_words[0] = 32'h61626380;
    for (i = 1; i < 15; i = i + 1) block_words[i] = 32'h00000000;
    block_words[15] = 32'h00000018;
    // One padded SHA-1 block for ASCII "abc".  cmd[2:1]=01 starts a new block.
    // cmd is registered, so retain W0 for the cycle in which the SHA engine
    // observes the write command; subsequent words then stream each cycle.
    @(negedge clk_i); text_i = block_words[0]; cmd_i = 3'b010; cmd_w_i = 1;
    @(negedge clk_i); text_i = block_words[0]; cmd_i = 0; cmd_w_i = 0;
    for (i = 1; i < 16; i = i + 1) begin
      @(negedge clk_i); text_i = block_words[i];
    end
    wait (cmd_o[3] == 1'b0);
    @(negedge clk_i); cmd_i = 3'b001; cmd_w_i = 1;
    @(negedge clk_i); cmd_i = 0; cmd_w_i = 0;
    // cmd is registered; allow the read sequencer to load its five-word count.
    @(negedge clk_i);
    for (i = 0; i < 5; i = i + 1) begin
      @(negedge clk_i); digest[i] = text_o;
    end
    if ({digest[0], digest[1], digest[2], digest[3], digest[4]} !==
        160'ha9993e364706816aba3e25717850c26c9cd0d89d) begin
      $fatal(1, "SHA-1 abc KAT mismatch: %h %h %h %h %h", digest[0], digest[1], digest[2], digest[3], digest[4]);
    end
    $display("SHA1_ABC_KAT_PASS digest=%h busy_cycles=%0d",
             {digest[0], digest[1], digest[2], digest[3], digest[4]}, busy_cycles);
    $finish;
  end
endmodule
