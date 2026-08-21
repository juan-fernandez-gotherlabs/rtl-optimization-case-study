`timescale 1ns / 1ps

// Frozen from HWSec-CSIC/hope-mlkem at
// 72a90d80484d45d0bed1e0f9903bd0fb78cceb47 (rtl/cbd.v).
// SPDX-License-Identifier: MIT
module CBD #(
    parameter Q = 3329
    )(
    input clk,
    input rst,
    input load,
    input start,
    input   [1:0] eta,
    input   scnd,
    input [1087:0] in_shake,
    output reg end_op,
    output          en_write,
    output [23:0]   data_in_1,
    output [23:0]   data_in_2,
    output [7:0]    addr_1,
    output [7:0]    addr_2
    );

    // Keep the wide physical state on a fixed 24-bit shift. A two-bit byte
    // phase represents the 16-bit eta=2 advance without a 16/24 mux on every
    // flip-flop. reg_shake is the synthesized logical refinement view used by
    // the datapath and by sequential equivalence.
    reg [1095:0] shake_chunks;
    reg [1:0] shake_phase;
    reg [1095:0] reg_shake;
    always @* begin
        case (shake_phase)
            2'd0: reg_shake = shake_chunks;
            2'd1: reg_shake = shake_chunks >> 8;
            2'd2: reg_shake = shake_chunks >> 16;
            default: reg_shake = shake_chunks >> 24;
        endcase
    end

    always @(posedge clk) begin
        if(!rst) begin
            shake_chunks <= 0;
            shake_phase <= 0;
        end
        else begin
            if(load) begin
                if(scnd)                    shake_chunks <= {in_shake, reg_shake[7:0]};
                else                        shake_chunks <= {8'h00, in_shake};
                shake_phase <= 0;
            end
            else if(start & !end_op) begin
                if(eta == 2'b11) begin
                    shake_chunks <= shake_chunks >> 24;
                end
                else begin
                    if(shake_phase != 0)     shake_chunks <= shake_chunks >> 24;
                    if(shake_phase == 0)     shake_phase <= 2;
                    else                    shake_phase <= shake_phase - 1'b1;
                end
            end
        end
    end

    reg [7:0] counter_shake;
    always @(posedge clk) begin
        if(!rst | load) counter_shake <= 0;
        else begin
            if(start)   counter_shake <= counter_shake + 1;
            else        counter_shake <= counter_shake;
        end
    end

    wire [15:0] x_e_1;
    wire [15:0] y_e_1;
    wire [15:0] S_e_1;
    wire [15:0] d_e_1;
    assign x_e_1 = (eta == 2'b11) ? (reg_shake[0] + reg_shake[1] + reg_shake[2]) : (reg_shake[0] + reg_shake[1]);
    assign y_e_1 = (eta == 2'b11) ? (reg_shake[3] + reg_shake[4] + reg_shake[5]) : (reg_shake[2] + reg_shake[3]);
    assign S_e_1 = x_e_1 - y_e_1;
    assign d_e_1 = (S_e_1[15]) ? S_e_1 + Q : S_e_1;

    wire [15:0] x_e_2;
    wire [15:0] y_e_2;
    wire [15:0] S_e_2;
    wire [15:0] d_e_2;
    assign x_e_2 = (eta == 2'b11) ? (reg_shake[0+12] + reg_shake[1+12] + reg_shake[2+12]) : (reg_shake[0+8] + reg_shake[1+8]);
    assign y_e_2 = (eta == 2'b11) ? (reg_shake[3+12] + reg_shake[4+12] + reg_shake[5+12]) : (reg_shake[2+8] + reg_shake[3+8]);
    assign S_e_2 = x_e_2 - y_e_2;
    assign d_e_2 = (S_e_2[15]) ? S_e_2 + Q : S_e_2;

    wire [15:0] x_o_1;
    wire [15:0] y_o_1;
    wire [15:0] S_o_1;
    wire [15:0] d_o_1;
    assign x_o_1 = (eta == 2'b11) ? (reg_shake[0+6] + reg_shake[1+6] + reg_shake[2+6]) : (reg_shake[0+4] + reg_shake[1+4]);
    assign y_o_1 = (eta == 2'b11) ? (reg_shake[3+6] + reg_shake[4+6] + reg_shake[5+6]) : (reg_shake[2+4] + reg_shake[3+4]);
    assign S_o_1 = x_o_1 - y_o_1;
    assign d_o_1 = (S_o_1[15]) ? S_o_1 + Q : S_o_1;

    wire [15:0] x_o_2;
    wire [15:0] y_o_2;
    wire [15:0] S_o_2;
    wire [15:0] d_o_2;
    assign x_o_2 = (eta == 2'b11) ? (reg_shake[0+18] + reg_shake[1+18] + reg_shake[2+18]) : (reg_shake[0+12] + reg_shake[1+12]);
    assign y_o_2 = (eta == 2'b11) ? (reg_shake[3+18] + reg_shake[4+18] + reg_shake[5+18]) : (reg_shake[2+12] + reg_shake[3+12]);
    assign S_o_2 = x_o_2 - y_o_2;
    assign d_o_2 = (S_o_2[15]) ? S_o_2 + Q : S_o_2;

    assign en_write = start;

    reg [7:0] ad_wr;
    always @(posedge clk) begin
        if(!rst)                                ad_wr <= 0;
        else begin
            if(start & en_write & !end_op)      ad_wr <= ad_wr + 2;
            else                                ad_wr <= ad_wr;
        end
    end

    always @(posedge clk) begin
        if(!rst | load)                                             end_op <= 1'b0;
        else begin
            if(eta == 2'b10 & ad_wr == 124)                         end_op <= 1'b1;
       else if(eta == 2'b11 & (ad_wr == 124 | counter_shake == 44)) end_op <= 1'b1;
            else                                                    end_op <= end_op;
        end
    end

    assign data_in_1 = {d_o_1[11:0], d_e_1[11:0]};
    assign data_in_2 = {d_o_2[11:0], d_e_2[11:0]};

    assign addr_1   = ad_wr;
    assign addr_2   = ad_wr + 1;
endmodule
