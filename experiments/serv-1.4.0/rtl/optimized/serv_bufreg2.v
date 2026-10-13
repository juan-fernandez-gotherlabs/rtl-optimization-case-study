/*
 * serv_bufreg2.v : SERV buffer register for load/store data and shift amount
 *
 * SPDX-FileCopyrightText: 2022 Olof Kindgren <olof@award-winning.me>
 * SPDX-License-Identifier: ISC
 */
module serv_bufreg2
  #(parameter [1:0] WORD_BANK_ENABLE_FORM = 0,
    parameter BUFFER_CONTROL_FORM = 0,
    parameter W = 1,
    //Internally calculated. Do not touch
    parameter B=W-1)
  (
   input wire	      i_clk,
   //State
   input wire	      i_en,
   input wire	      i_init,
   input wire	      i_cnt7,
   input wire	      i_cnt_done,
   input wire	      i_sh_right,
   input wire [1:0]   i_lsb,
   input wire [1:0]   i_bytecnt,
   output wire	      o_sh_done,
   //Control
   input wire	      i_op_b_sel,
   input wire	      i_shift_op,
   //Data
   input wire [B:0]   i_rs2,
   input wire [B:0]   i_imm,
   output wire [B:0]  o_op_b,
   output wire [B:0]  o_q,
   //External
   output wire [31:0] o_dat,
   input wire	      i_load,
   input wire [31:0]  i_dat);

   // High and low data words form a 32-bit word
   reg [7:0] 	 dhi;
   reg [23:0] 	 dlo;

   /*
    Before a store operation, the data to be written needs to be shifted into
    place. Depending on the address alignment, we need to shift different
    amounts. One formula for calculating this is to say that we shift when
    i_lsb + i_bytecnt < 4. Unfortunately, the synthesis tools don't seem to be
    clever enough so the hideous expression below is used to achieve the same
    thing in a more optimal way.
    */
   wire byte_valid
     = (!i_lsb[0] & !i_lsb[1])         |
       (!i_bytecnt[0] & !i_bytecnt[1]) |
       (!i_bytecnt[1] & !i_lsb[1])     |
       (!i_bytecnt[1] & !i_lsb[0])     |
       (!i_bytecnt[0] & !i_lsb[1]);

   assign o_op_b = i_op_b_sel ? i_rs2 : i_imm;

   wire 	 shift_en = i_shift_op ? (i_en & i_init & (i_bytecnt == 2'b00)) : (i_en & byte_valid);

   wire		 cnt_en = (i_shift_op & (!i_init | (i_cnt_done & i_sh_right)));

   /* The dat register has three different use cases for store, load and
    shift operations.
    store : Data to be written is shifted to the correct position in dat during
            init by shift_en and is presented on the data bus as o_wb_dat
    load  : Data from the bus gets latched into dat during i_wb_ack and is then
            shifted out at the appropriate time to end up in the correct
            position in rd
    shift : Data is shifted in during init. After that, the six LSB are used as
            a downcounter (with bit 5 initially set to 0) that trigger
            o_sh_done when they wrap around to indicate that
            the requested number of shifts have been performed
    */

   wire [7:0]	 cnt_next;
   generate
      if (W == 1) begin : gen_cnt_w_eq_1
         wire [5:0] boolean_decrement_w1;
         assign boolean_decrement_w1[0] = !dhi[0];
         assign boolean_decrement_w1[1] = dhi[1] ^ !(|dhi[0:0]);
         assign boolean_decrement_w1[2] = dhi[2] ^ !(|dhi[1:0]);
         assign boolean_decrement_w1[3] = dhi[3] ^ !(|dhi[2:0]);
         assign boolean_decrement_w1[4] = dhi[4] ^ !(|dhi[3:0]);
         assign boolean_decrement_w1[5] = dhi[5] ^ !(|dhi[4:0]);
	 assign cnt_next = {o_op_b, dhi[7], boolean_decrement_w1};
      end else if (W == 4) begin : gen_cnt_w_eq_4
         wire [5:0] boolean_decrement_w4;
         assign boolean_decrement_w4[0] = dhi[0];
         assign boolean_decrement_w4[1] = dhi[1];
         assign boolean_decrement_w4[2] = !dhi[2];
         assign boolean_decrement_w4[3] = dhi[3] ^ !(|dhi[2:2]);
         assign boolean_decrement_w4[4] = dhi[4] ^ !(|dhi[3:2]);
         assign boolean_decrement_w4[5] = dhi[5] ^ !(|dhi[4:2]);
	 assign cnt_next = {o_op_b[3:2], boolean_decrement_w4};
      end
   endgenerate

   wire [7:0] dat_shamt = cnt_en ?
	      //Down counter mode
	      cnt_next :
	      //Shift reg mode
	      {o_op_b, dhi[7:W]};

   assign o_sh_done = dat_shamt[5];

   assign o_q =
	       ({W{(i_lsb == 2'd3)}} & o_dat[W+23:24]) |
	       ({W{(i_lsb == 2'd2)}} & o_dat[W+15:16]) |
	       ({W{(i_lsb == 2'd1)}} & o_dat[W+7:8])   |
	       ({W{(i_lsb == 2'd0)}} & o_dat[W-1:0]);

   assign o_dat = {dhi,dlo};

   wire private_byte_valid;
   wire private_shift_enable;
   wire private_count_enable;
   wire private_initial_byte = i_init & !(|i_bytecnt);
   generate if (BUFFER_CONTROL_FORM > 0 && BUFFER_CONTROL_FORM <= 4 && W == 1) begin : gen_private_controls
      if (BUFFER_CONTROL_FORM == 1) begin : gen_form_1
         assign private_byte_valid = (!i_lsb[1] & (!i_lsb[0] | !i_bytecnt[1] | !i_bytecnt[0])) | (!i_bytecnt[1] & (!i_bytecnt[0] | !i_lsb[0]));
         assign private_shift_enable = i_en & (i_shift_op ? (i_init & !(|i_bytecnt)) : private_byte_valid);
         assign private_count_enable = i_shift_op & (!i_init | (i_cnt_done & i_sh_right));
      end else if (BUFFER_CONTROL_FORM == 2) begin : gen_form_2
         assign private_byte_valid = (!i_bytecnt[1] & (!i_bytecnt[0] | !i_lsb[1] | !i_lsb[0])) | (!i_lsb[1] & (!i_lsb[0] | !i_bytecnt[0]));
         assign private_shift_enable = i_en & (!i_shift_op ? private_byte_valid : (i_init & !(|i_bytecnt)));
         assign private_count_enable = i_shift_op & !(i_init & (!i_cnt_done | !i_sh_right));
      end else if (BUFFER_CONTROL_FORM == 3) begin : gen_form_3
         assign private_byte_valid = (!i_lsb[1] & (!i_lsb[0] | !i_bytecnt[1] | !i_bytecnt[0])) | (!i_bytecnt[1] & (!i_bytecnt[0] | !i_lsb[0]));
         assign private_shift_enable = i_en & ((i_shift_op & private_initial_byte) | (!i_shift_op & private_byte_valid) | (private_initial_byte & private_byte_valid));
         assign private_count_enable = (i_shift_op & !i_init) | (i_shift_op & i_cnt_done & i_sh_right);
      end else if (BUFFER_CONTROL_FORM == 4) begin : gen_form_4
         assign private_byte_valid = !((i_lsb[0] | i_lsb[1]) & (i_bytecnt[0] | i_bytecnt[1]) & (i_bytecnt[1] | i_lsb[1]) & (i_bytecnt[1] | i_lsb[0]) & (i_bytecnt[0] | i_lsb[1]));
         assign private_shift_enable = i_en & !( !(i_shift_op & private_initial_byte) & !(!i_shift_op & private_byte_valid) & !(private_initial_byte & private_byte_valid));
         assign private_count_enable = !(!i_shift_op | (i_init & (!i_cnt_done | !i_sh_right)));
      end
   end else begin : gen_literal_controls
      assign private_byte_valid = byte_valid;
      assign private_shift_enable = shift_en;
      assign private_count_enable = cnt_en;
   end endgenerate

   always @(posedge i_clk) begin
      if (i_load) dhi <= i_dat[31:24];
      else if (private_count_enable) dhi <= cnt_next;
      else if (private_shift_enable) dhi <= ({o_op_b, dhi[7:W]} & {2'b11, !(i_shift_op & i_cnt7), 5'b11111});
      if (WORD_BANK_ENABLE_FORM == 0) begin
if (private_shift_enable | i_load)
	dlo <= i_load ? i_dat[23:0] : {dhi[B:0], dlo[23:W]};
      end
      else if (WORD_BANK_ENABLE_FORM == 1) begin
      if (private_shift_enable) dlo <= i_load ? i_dat[23:0] : {dhi[B:0], dlo[23:W]};
      else if (i_load) dlo <= i_dat[23:0];
      end
      else if (WORD_BANK_ENABLE_FORM == 2) begin
      if (i_load) dlo <= i_dat[23:0];
      else if (private_shift_enable) dlo <= i_load ? i_dat[23:0] : {dhi[B:0], dlo[23:W]};
      end
      else if (WORD_BANK_ENABLE_FORM == 3) begin
      if (i_load | private_shift_enable) dlo <= private_shift_enable ? (i_load ? i_dat[23:0] : {dhi[B:0], dlo[23:W]}) : i_dat[23:0];
      end
   end

endmodule
