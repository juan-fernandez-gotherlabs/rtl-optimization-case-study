`timescale 1ns/1ps

// Frozen cycle-equivalence contract for the VTR SHA benchmark. The evaluator
// compiles this testbench with the candidate as sha1 and the corrected golden
// RTL, renamed mechanically to sha1_reference. Only sha.v may be edited.
module sha1_equivalence_tb;
  localparam integer CASE_COUNT = 16;
  localparam integer MAX_BUSY_CYCLES = 96;

  reg clk_i = 0;
  reg rst_i = 1;
  reg [31:0] text_i = 0;
  reg [2:0] cmd_i = 0;
  reg cmd_w_i = 0;
  wire [31:0] candidate_text_o;
  wire [31:0] reference_text_o;
  wire [3:0] candidate_cmd_o;
  wire [3:0] reference_cmd_o;
  reg [31:0] block_words [0:15];
  integer case_index;
  integer fuzz_index;
  integer completed_cases = 0;
  integer observable_checks = 0;
  reg [31:0] fuzz_state;

  sha1 candidate (
    .clk_i(clk_i), .rst_i(rst_i), .text_i(text_i),
    .text_o(candidate_text_o), .cmd_i(cmd_i),
    .cmd_w_i(cmd_w_i), .cmd_o(candidate_cmd_o)
  );

  sha1_reference reference (
    .clk_i(clk_i), .rst_i(rst_i), .text_i(text_i),
    .text_o(reference_text_o), .cmd_i(cmd_i),
    .cmd_w_i(cmd_w_i), .cmd_o(reference_cmd_o)
  );

  always #5 clk_i = ~clk_i;

  // Compare every observable cycle, not only the final digest. This freezes
  // command/status timing, digest readout order, reset behavior and latency.
  always @(negedge clk_i) begin
    if (!rst_i) begin
      observable_checks = observable_checks + 1;
      if (candidate_cmd_o !== reference_cmd_o) begin
        $fatal(1, "cmd_o mismatch in case %0d at check %0d: candidate=%h reference=%h",
               case_index, observable_checks, candidate_cmd_o, reference_cmd_o);
      end
      if (candidate_text_o !== reference_text_o) begin
        $fatal(1, "text_o mismatch in case %0d at check %0d: candidate=%h reference=%h",
               case_index, observable_checks, candidate_text_o, reference_text_o);
      end
    end
  end

  function [31:0] lfsr_next;
    input [31:0] value;
    begin
      lfsr_next = {value[30:0], value[31] ^ value[21] ^ value[1] ^ value[0]};
    end
  endfunction

  task reset_pair;
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

  // Exercise the complete cycle-visible contract, including command/reset
  // sequences outside the normal digest workflow.  Formal equivalence makes
  // no legal-protocol assumption, so mutation coverage must also observe
  // state that is visible through read-after-reset and interrupted operation.
  task run_protocol_edges;
    begin
      case_index = -2;

      // Read the reset state before a compression command initializes H0..H4.
      reset_pair;
      cmd_i = 3'b001;
      cmd_w_i = 1;
      @(negedge clk_i);
      cmd_i = 0;
      cmd_w_i = 0;
      repeat (8) @(negedge clk_i);

      // A continuation command immediately after reset exposes the reset H
      // chaining state before any first-block command overwrites it.
      reset_pair;
      run_block(-3, 1'b1);
      completed_cases = completed_cases - 1;

      // Reset while an operation is in flight, then read the reset state.
      text_i = 32'h01234567;
      cmd_i = 3'b010;
      cmd_w_i = 1;
      @(negedge clk_i);
      cmd_i = 0;
      cmd_w_i = 0;
      repeat (11) begin
        @(negedge clk_i);
        text_i = lfsr_next(text_i);
      end
      rst_i = 1;
      repeat (2) @(negedge clk_i);
      rst_i = 0;
      cmd_i = 3'b001;
      cmd_w_i = 1;
      @(negedge clk_i);
      cmd_i = 0;
      cmd_w_i = 0;
      repeat (8) @(negedge clk_i);

      // Deterministic adversarial traffic covers overlapping read/start bits,
      // repeated writes, idle gaps and periodic synchronous resets.
      reset_pair;
      fuzz_state = 32'hc001d00d;
      for (fuzz_index = 0; fuzz_index < 1024; fuzz_index = fuzz_index + 1) begin
        @(negedge clk_i);
        fuzz_state = lfsr_next(fuzz_state ^ fuzz_index);
        text_i = fuzz_state;
        cmd_i = fuzz_state[4:2];
        cmd_w_i = fuzz_state[0] ^ fuzz_state[7];
        rst_i = (fuzz_index == 257 || fuzz_index == 641);
      end
      reset_pair;
    end
  endtask

  task prepare_case;
    input integer selected_case;
    integer word_index;
    reg [31:0] state;
    begin
      case (selected_case)
        0: begin
          block_words[0] = 32'h61626380;
          for (word_index = 1; word_index < 15; word_index = word_index + 1)
            block_words[word_index] = 32'h00000000;
          block_words[15] = 32'h00000018;
        end
        1: begin
          block_words[0] = 32'h80000000;
          for (word_index = 1; word_index < 16; word_index = word_index + 1)
            block_words[word_index] = 32'h00000000;
        end
        2: begin
          for (word_index = 0; word_index < 16; word_index = word_index + 1)
            block_words[word_index] = 32'h00000000;
        end
        3: begin
          for (word_index = 0; word_index < 16; word_index = word_index + 1)
            block_words[word_index] = 32'hffffffff;
        end
        4: begin
          for (word_index = 0; word_index < 16; word_index = word_index + 1)
            block_words[word_index] = word_index[0] ? 32'haaaaaaaa : 32'h55555555;
        end
        5: begin
          for (word_index = 0; word_index < 16; word_index = word_index + 1)
            block_words[word_index] = 32'h00000001 << word_index;
        end
        default: begin
          state = 32'h1badc0de ^ selected_case;
          for (word_index = 0; word_index < 16; word_index = word_index + 1) begin
            state = lfsr_next(state);
            block_words[word_index] = state;
          end
        end
      endcase
    end
  endtask

  task run_block;
    input integer selected_case;
    input internal_round;
    integer word_index;
    integer busy_cycles;
    begin
      case_index = selected_case;
      prepare_case(selected_case);

      @(negedge clk_i);
      text_i = block_words[0];
      cmd_i = internal_round ? 3'b110 : 3'b010;
      cmd_w_i = 1;
      @(negedge clk_i);
      text_i = block_words[0];
      cmd_i = 0;
      cmd_w_i = 0;
      for (word_index = 1; word_index < 16; word_index = word_index + 1) begin
        @(negedge clk_i);
        text_i = block_words[word_index];
      end

      busy_cycles = 0;
      while (candidate_cmd_o[3] !== 1'b0 && busy_cycles < MAX_BUSY_CYCLES) begin
        @(negedge clk_i);
        busy_cycles = busy_cycles + 1;
      end
      if (busy_cycles >= MAX_BUSY_CYCLES)
        $fatal(1, "busy timeout in case %0d", selected_case);

      @(negedge clk_i);
      cmd_i = 3'b001;
      cmd_w_i = 1;
      @(negedge clk_i);
      cmd_i = 0;
      cmd_w_i = 0;
      repeat (6) @(negedge clk_i);
      completed_cases = completed_cases + 1;
    end
  endtask

  initial begin
    case_index = -1;
    run_protocol_edges;

    // Independent single-block cases.
    for (case_index = 0; case_index < 12; case_index = case_index + 1) begin
      reset_pair;
      run_block(case_index, 1'b0);
    end

    // One four-block chain exercises the internal-round command and state
    // continuation without reset.
    reset_pair;
    run_block(12, 1'b0);
    run_block(13, 1'b1);
    run_block(14, 1'b1);
    run_block(15, 1'b1);

    if (completed_cases != CASE_COUNT)
      $fatal(1, "incomplete equivalence corpus: %0d/%0d", completed_cases, CASE_COUNT);
    if (observable_checks < 1000)
      $fatal(1, "too few observable equivalence checks: %0d", observable_checks);
    $display("SHA_VTR_EQUIVALENCE_CONTRACT_PASS cases=%0d checks=%0d",
             completed_cases, observable_checks);
    $finish;
  end
endmodule
