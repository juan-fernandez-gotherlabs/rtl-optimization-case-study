/*
 * serv_bufreg.v : SERV buffer register for load/store address and shift data
 *
 * SPDX-FileCopyrightText: 2019 Olof Kindgren <olof@award-winning.me>
 * SPDX-License-Identifier: ISC
 */
module serv_bufreg #(
      parameter [0:0] MDU = 0,
      parameter W = 1,
      parameter B = W-1
)(
   input wire 	      i_clk,
   //State
   input wire 	      i_cnt0,
   input wire 	      i_cnt1,
   input wire 	      i_cnt_done,
   input wire 	      i_en,
   input wire 	      i_init,
   input wire           i_mdu_op,
   output wire [1:0]    o_lsb,
   //Control
   input wire 	      i_rs1_en,
   input wire 	      i_imm_en,
   input wire 	      i_clr_lsb,
   input wire 	      i_shift_op,
   input wire 	      i_right_shift_op,
   input wire [2:0]   i_shamt,
   input wire 	      i_sh_signed,
   //Data
   input wire [B:0] i_rs1,
   input wire [B:0] i_imm,
   output wire [B:0] o_q,
   //External
   output wire [31:0] o_dbus_adr,
   //Extension
   output wire [31:0] o_ext_rs1);

   wire		      c;
   wire [B:0]	      q;
   reg [B:0]	      c_r;
   wire [31:0] data;
   wire [B:0]	      clr_lsb;

   assign clr_lsb[0] = i_cnt0 & i_clr_lsb;

   generate
      if (W > 1) begin : gen_clr_lsb_w_gt_1
         assign  clr_lsb[B:1] = {B{1'b0}};
      end
   endgenerate

   assign {c,q} = {1'b0,(i_rs1 & {W{i_rs1_en}})} + {1'b0,(i_imm & {W{i_imm_en}} & ~clr_lsb)} + c_r;

   always @(posedge i_clk) begin
      //Make sure carry is cleared before loading new data
      c_r    <= {W{1'b0}};
      c_r[0] <= c & i_en;
   end

   generate
      if (W == 1) begin : gen_w_eq_1
         reg [31:0] physical_address_code;
         wire [31:0] address_code;
         wire [31:0] physical_next;
         wire [31:0] address_next = {
            i_en ? {i_init ? q : {W{data[31] & i_sh_signed}},data[31:3]} : data[31:2],
            (i_init ? (i_cnt0 | i_cnt1) : i_en) ? {i_init ? q : data[2],data[1]} : data[1:0]};
         wire [31:0] encoded_next;
      assign data[12] = address_code[12] ^ address_code[13] ^ address_code[14] ^ address_code[15];
      assign encoded_next[12] = address_next[12] ^ address_next[13];
      assign data[13] = address_code[13] ^ address_code[14] ^ address_code[15];
      assign encoded_next[13] = address_next[13] ^ address_next[14];
      assign data[14] = address_code[14] ^ address_code[15];
      assign encoded_next[14] = address_next[14] ^ address_next[15];
      assign data[15] = address_code[15];
      assign encoded_next[15] = address_next[15];
      assign data[18] = address_code[19];
      assign encoded_next[18] = address_next[18] ^ address_next[19];
      assign data[19] = address_code[18] ^ address_code[19];
      assign encoded_next[19] = address_next[18];
      assign data[24] = address_code[25];
      assign encoded_next[24] = address_next[24] ^ address_next[25];
      assign data[25] = address_code[24] ^ address_code[25];
      assign encoded_next[25] = address_next[24];
      assign data[0] = address_code[0];
      assign encoded_next[0] = address_next[0];
      assign data[1] = address_code[1];
      assign encoded_next[1] = address_next[1];
      assign data[2] = address_code[2];
      assign encoded_next[2] = address_next[2];
      assign data[3] = address_code[3];
      assign encoded_next[3] = address_next[3];
      assign data[4] = address_code[4];
      assign encoded_next[4] = address_next[4];
      assign data[5] = address_code[5];
      assign encoded_next[5] = address_next[5];
      assign data[6] = address_code[6];
      assign encoded_next[6] = address_next[6];
      assign data[7] = address_code[7];
      assign encoded_next[7] = address_next[7];
      assign data[8] = address_code[8];
      assign encoded_next[8] = address_next[8];
      assign data[9] = address_code[9];
      assign encoded_next[9] = address_next[9];
      assign data[10] = address_code[10];
      assign encoded_next[10] = address_next[10];
      assign data[11] = address_code[11];
      assign encoded_next[11] = address_next[11];
      assign data[16] = address_code[16];
      assign encoded_next[16] = address_next[16];
      assign data[17] = address_code[17];
      assign encoded_next[17] = address_next[17];
      assign data[20] = address_code[20];
      assign encoded_next[20] = address_next[20];
      assign data[21] = address_code[21];
      assign encoded_next[21] = address_next[21];
      assign data[22] = address_code[22];
      assign encoded_next[22] = address_next[22];
      assign data[23] = address_code[23];
      assign encoded_next[23] = address_next[23];
      assign data[26] = address_code[26];
      assign encoded_next[26] = address_next[26];
      assign data[27] = address_code[27];
      assign encoded_next[27] = address_next[27];
      assign data[28] = address_code[28];
      assign encoded_next[28] = address_next[28];
      assign data[29] = address_code[29];
      assign encoded_next[29] = address_next[29];
      assign data[30] = address_code[30];
      assign encoded_next[30] = address_next[30];
      assign data[31] = address_code[31];
      assign encoded_next[31] = address_next[31];
         assign address_code[0] = physical_address_code[0];
         assign physical_next[0] = encoded_next[0];
         assign address_code[1] = physical_address_code[1];
         assign physical_next[1] = encoded_next[1];
         assign address_code[2] = physical_address_code[2];
         assign physical_next[2] = encoded_next[2];
         assign address_code[3] = physical_address_code[3];
         assign physical_next[3] = encoded_next[3];
         assign address_code[4] = physical_address_code[4];
         assign physical_next[4] = encoded_next[4];
         assign address_code[5] = physical_address_code[5];
         assign physical_next[5] = encoded_next[5];
         assign address_code[6] = physical_address_code[6];
         assign physical_next[6] = encoded_next[6];
         assign address_code[7] = physical_address_code[7];
         assign physical_next[7] = encoded_next[7];
         assign address_code[8] = physical_address_code[8];
         assign physical_next[8] = encoded_next[8];
         assign address_code[9] = physical_address_code[9];
         assign physical_next[9] = encoded_next[9];
         assign address_code[10] = physical_address_code[10];
         assign physical_next[10] = encoded_next[10];
         assign address_code[11] = physical_address_code[11];
         assign physical_next[11] = encoded_next[11];
         assign address_code[12] = physical_address_code[12];
         assign physical_next[12] = encoded_next[12];
         assign address_code[13] = physical_address_code[13];
         assign physical_next[13] = encoded_next[13];
         assign address_code[14] = physical_address_code[14] ^ (physical_address_code[13] & physical_address_code[15]);
         assign physical_next[14] = encoded_next[14] ^ (encoded_next[13] & encoded_next[15]);
         assign address_code[15] = physical_address_code[15];
         assign physical_next[15] = encoded_next[15];
         assign address_code[16] = physical_address_code[16];
         assign physical_next[16] = encoded_next[16];
         assign address_code[17] = physical_address_code[17];
         assign physical_next[17] = encoded_next[17];
         assign address_code[18] = physical_address_code[18];
         assign physical_next[18] = encoded_next[18];
         assign address_code[19] = physical_address_code[19];
         assign physical_next[19] = encoded_next[19];
         assign address_code[20] = physical_address_code[20];
         assign physical_next[20] = encoded_next[20];
         assign address_code[21] = physical_address_code[21];
         assign physical_next[21] = encoded_next[21];
         assign address_code[22] = physical_address_code[22];
         assign physical_next[22] = encoded_next[22];
         assign address_code[23] = physical_address_code[23];
         assign physical_next[23] = encoded_next[23];
         assign address_code[24] = physical_address_code[24];
         assign physical_next[24] = encoded_next[24];
         assign address_code[25] = physical_address_code[25];
         assign physical_next[25] = encoded_next[25];
         assign address_code[26] = physical_address_code[26];
         assign physical_next[26] = encoded_next[26];
         assign address_code[27] = physical_address_code[27];
         assign physical_next[27] = encoded_next[27];
         assign address_code[28] = physical_address_code[28];
         assign physical_next[28] = encoded_next[28];
         assign address_code[29] = physical_address_code[29];
         assign physical_next[29] = encoded_next[29];
         assign address_code[30] = physical_address_code[30];
         assign physical_next[30] = encoded_next[30];
         assign address_code[31] = physical_address_code[31];
         assign physical_next[31] = encoded_next[31];
         always @(posedge i_clk) physical_address_code <= physical_next;
	 assign o_lsb = (MDU & i_mdu_op) ? 2'b00 : data[1:0];
	 assign o_q = data[0] & {W{i_en}};
      end else if (W == 4) begin : gen_lsb_w_4
         reg [31:0] data_plain;
         assign data = data_plain;
	 reg [1:0] lsb;
	 reg [W-2:0] data_tail;

	 wire [2:0] shift_amount
	   = !i_shift_op ? 3'd3 :
	     i_right_shift_op ? (3'd3+{1'b0,i_shamt[1:0]}) :
	     ({1'b0,~i_shamt[1:0]});

	 always @(posedge i_clk) begin
            if (i_en)
              if (i_cnt0) lsb <= q[1:0];
	    if (i_en)
              data_plain <= {i_init ? q : {W{i_sh_signed & data[31]}}, data[31:W]};
	    if (i_en)
	      data_tail <= data[B:1] & {B{~i_cnt_done}};
	 end

	 wire [2*W+B-2:0] muxdata = {data[W+B-1:0],data_tail};
	 wire [B:0]	  muxout = muxdata[{1'b0,shift_amount}+:W];

	 assign o_lsb = (MDU & i_mdu_op) ? 2'b00 : lsb;
	 assign o_q = i_en ? muxout : {W{1'b0}};
      end
   endgenerate


   assign o_dbus_adr = {data[31:2], 2'b00};
   assign o_ext_rs1  = data;

endmodule
