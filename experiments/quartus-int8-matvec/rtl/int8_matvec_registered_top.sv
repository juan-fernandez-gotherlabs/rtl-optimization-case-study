// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Evolther contributors
// Fixed register-to-register wrapper for the Quartus transfer experiment.
module int8_matvec_registered_top (
    input  logic clk,
    input  logic signed [7:0] x0,
    input  logic signed [7:0] x1,
    input  logic signed [7:0] x2,
    input  logic signed [7:0] x3,
    input  logic signed [7:0] w00,
    input  logic signed [7:0] w01,
    input  logic signed [7:0] w02,
    input  logic signed [7:0] w03,
    input  logic signed [7:0] w10,
    input  logic signed [7:0] w11,
    input  logic signed [7:0] w12,
    input  logic signed [7:0] w13,
    input  logic signed [7:0] w20,
    input  logic signed [7:0] w21,
    input  logic signed [7:0] w22,
    input  logic signed [7:0] w23,
    input  logic signed [7:0] w30,
    input  logic signed [7:0] w31,
    input  logic signed [7:0] w32,
    input  logic signed [7:0] w33,
    output logic signed [31:0] y0,
    output logic signed [31:0] y1,
    output logic signed [31:0] y2,
    output logic signed [31:0] y3
);

    logic signed [7:0] x0_q, x1_q, x2_q, x3_q;
    logic signed [7:0] w00_q, w01_q, w02_q, w03_q;
    logic signed [7:0] w10_q, w11_q, w12_q, w13_q;
    logic signed [7:0] w20_q, w21_q, w22_q, w23_q;
    logic signed [7:0] w30_q, w31_q, w32_q, w33_q;
    logic signed [31:0] y0_d, y1_d, y2_d, y3_d;

    always_ff @(posedge clk) begin
        x0_q <= x0;
        x1_q <= x1;
        x2_q <= x2;
        x3_q <= x3;
        w00_q <= w00;
        w01_q <= w01;
        w02_q <= w02;
        w03_q <= w03;
        w10_q <= w10;
        w11_q <= w11;
        w12_q <= w12;
        w13_q <= w13;
        w20_q <= w20;
        w21_q <= w21;
        w22_q <= w22;
        w23_q <= w23;
        w30_q <= w30;
        w31_q <= w31;
        w32_q <= w32;
        w33_q <= w33;
        y0 <= y0_d;
        y1 <= y1_d;
        y2 <= y2_d;
        y3 <= y3_d;
    end

    int8_matvec_4x4 dut (
        .x0(x0_q), .x1(x1_q), .x2(x2_q), .x3(x3_q),
        .w00(w00_q), .w01(w01_q), .w02(w02_q), .w03(w03_q),
        .w10(w10_q), .w11(w11_q), .w12(w12_q), .w13(w13_q),
        .w20(w20_q), .w21(w21_q), .w22(w22_q), .w23(w23_q),
        .w30(w30_q), .w31(w31_q), .w32(w32_q), .w33(w33_q),
        .y0(y0_d), .y1(y1_d), .y2(y2_d), .y3(y3_d)
    );

endmodule
