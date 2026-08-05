`timescale 1ns/1ps

// Frozen byte-oriented NIST SHAVS regression for the corrected VTR-derived
// SHA-1 seed.  The corpus is generated outside the candidate boundary from
// the pinned official response files.
module sha1_nist_tb;
  localparam integer MAX_BUSY_CYCLES = 96;

  reg clk_i = 0;
  reg rst_i = 1;
  reg [31:0] text_i = 0;
  reg [2:0] cmd_i = 0;
  reg cmd_w_i = 0;
  wire [31:0] text_o;
  wire [3:0] cmd_o;
  reg [159:0] observed_digest;
  reg [159:0] expected_digest;
  reg [511:0] block_bits;
  string corpus_path;
  string magic;
  string source_name;
  integer corpus_fd;
  integer expected_cases;
  integer completed_cases = 0;
  integer length_bits;
  integer block_count;
  integer block_index;
  integer scan_status;

  sha1 dut (
    .clk_i(clk_i), .rst_i(rst_i), .text_i(text_i), .text_o(text_o),
    .cmd_i(cmd_i), .cmd_w_i(cmd_w_i), .cmd_o(cmd_o)
  );

  always #5 clk_i = ~clk_i;

  task reset_dut;
    begin
      rst_i = 1;
      text_i = 0;
      cmd_i = 0;
      cmd_w_i = 0;
      repeat (3) @(negedge clk_i);
      rst_i = 0;
      @(negedge clk_i);
    end
  endtask

  task run_block;
    input [511:0] selected_block;
    input internal_round;
    integer word_index;
    integer busy_cycles;
    begin
      @(negedge clk_i);
      text_i = selected_block[511 -: 32];
      cmd_i = internal_round ? 3'b110 : 3'b010;
      cmd_w_i = 1;
      @(negedge clk_i);
      text_i = selected_block[511 -: 32];
      cmd_i = 0;
      cmd_w_i = 0;
      for (word_index = 1; word_index < 16; word_index = word_index + 1) begin
        @(negedge clk_i);
        text_i = selected_block[511 - word_index * 32 -: 32];
      end
      @(negedge clk_i);
      text_i = 0;
      busy_cycles = 0;
      while (cmd_o[3] !== 1'b0 && busy_cycles < MAX_BUSY_CYCLES) begin
        @(negedge clk_i);
        busy_cycles = busy_cycles + 1;
      end
      if (busy_cycles >= MAX_BUSY_CYCLES)
        $fatal(1, "busy timeout in case %0d block %0d", completed_cases, block_index);
    end
  endtask

  task read_digest;
    integer word_index;
    begin
      @(negedge clk_i);
      cmd_i = 3'b001;
      cmd_w_i = 1;
      @(negedge clk_i);
      cmd_i = 0;
      cmd_w_i = 0;
      @(negedge clk_i);
      for (word_index = 0; word_index < 5; word_index = word_index + 1) begin
        @(negedge clk_i);
        observed_digest[159 - word_index * 32 -: 32] = text_o;
      end
    end
  endtask

  initial begin
    if (!$value$plusargs("CORPUS=%s", corpus_path))
      $fatal(1, "missing +CORPUS=<path>");
    corpus_fd = $fopen(corpus_path, "r");
    if (corpus_fd == 0)
      $fatal(1, "cannot open corpus %s", corpus_path);
    scan_status = $fscanf(corpus_fd, "%s %d\n", magic, expected_cases);
    if (scan_status != 2 || magic != "SHA1_BLOCK_CORPUS_V1")
      $fatal(1, "invalid SHA-1 block corpus header");

    while (completed_cases < expected_cases) begin
      scan_status = $fscanf(
        corpus_fd, "%s %d %d %h\n", source_name, length_bits, block_count, expected_digest
      );
      if (scan_status != 4 || block_count <= 0)
        $fatal(1, "invalid corpus record %0d", completed_cases);
      reset_dut;
      for (block_index = 0; block_index < block_count; block_index = block_index + 1) begin
        scan_status = $fscanf(corpus_fd, "%h\n", block_bits);
        if (scan_status != 1)
          $fatal(1, "missing block %0d in case %0d", block_index, completed_cases);
        run_block(block_bits, block_index != 0);
      end
      read_digest;
      if (observed_digest !== expected_digest)
        $fatal(
          1,
          "NIST mismatch case=%0d source=%s len=%0d expected=%h observed=%h",
          completed_cases,
          source_name,
          length_bits,
          expected_digest,
          observed_digest
        );
      completed_cases = completed_cases + 1;
    end

    $fclose(corpus_fd);
    $display("SHA1_NIST_SHAVS_PASS cases=%0d", completed_cases);
    $finish;
  end
endmodule
