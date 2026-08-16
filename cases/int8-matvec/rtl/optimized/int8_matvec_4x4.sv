// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Evolther contributors
// Signed INT8 4x4 matrix-vector accelerator candidate.
module int8_matvec_4x4 (
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

    logic signed [15:0] p00, p01, p02, p03;
    logic signed [15:0] p10, p11, p12, p13;
    logic signed [15:0] p20, p21, p22, p23;
    logic signed [15:0] p30, p31, p32, p33;
    logic signed [16:0] s00, s01;
    logic signed [16:0] s10, s11;
    logic signed [16:0] s20, s21;
    logic signed [16:0] s30, s31;
    logic signed [17:0] d0, d1, d2, d3;

    always_comb begin
        p00 = w00 * x0;
        p01 = w01 * x1;
        p02 = w02 * x2;
        p03 = w03 * x3;
        p10 = w10 * x0;
        p11 = w11 * x1;
        p12 = w12 * x2;
        p13 = w13 * x3;
        p20 = w20 * x0;
        p21 = w21 * x1;
        p22 = w22 * x2;
        p23 = w23 * x3;
        p30 = w30 * x0;
        p31 = w31 * x1;
        p32 = w32 * x2;
        p33 = w33 * x3;

        s00 = {p00[15], p00} + {p01[15], p01};
        s01 = {p02[15], p02} + {p03[15], p03};
        s10 = {p10[15], p10} + {p11[15], p11};
        s11 = {p12[15], p12} + {p13[15], p13};
        s20 = {p20[15], p20} + {p21[15], p21};
        s21 = {p22[15], p22} + {p23[15], p23};
        s30 = {p30[15], p30} + {p31[15], p31};
        s31 = {p32[15], p32} + {p33[15], p33};

        d0 = {s00[16], s00} + {s01[16], s01};
        d1 = {s10[16], s10} + {s11[16], s11};
        d2 = {s20[16], s20} + {s21[16], s21};
        d3 = {s30[16], s30} + {s31[16], s31};

        y0 = {{14{d0[17]}}, d0};
        y1 = {{14{d1[17]}}, d1};
        y2 = {{14{d2[17]}}, d2};
        y3 = {{14{d3[17]}}, d3};
    end
endmodule
