/*
 * serv_rf_ram_if.v : Interface between SERV and SRAM-based RF storage
 *
 * SPDX-FileCopyrightText: 2019 Olof Kindgren <olof@award-winning.me>
 * SPDX-License-Identifier: ISC
 */
`default_nettype none
module serv_rf_ram_if
  #(parameter [3:0] RF_HIGH_PHASE_FORM = 0,
    //Data width. Adjust to preferred width of SRAM data interface
    parameter width=8,

    parameter W = 1,
    //Select reset strategy.
    // "MINI" for resetting minimally required FFs
    // "NONE" for relying on FFs having a defined value on startup
    parameter reset_strategy="MINI",

    //Number of CSR registers. These are allocated after the normal
    // GPR registers in the RAM.
    parameter csr_regs=4,

    //Internal parameters calculated from above values. Do not change
    parameter B=W-1,
    parameter raw=$clog2(32+csr_regs), //Register address width
    parameter l2w=$clog2(width), //log2 of width
    parameter aw=5+raw-l2w) //Address width
  (
   //SERV side
   input wire		   i_clk,
   input wire		   i_rst,
   input wire		   i_wreq,
   input wire		   i_rreq,
   output wire		   o_ready,
   input wire [raw-1:0]	   i_wreg0,
   input wire [raw-1:0]	   i_wreg1,
   input wire		   i_wen0,
   input wire		   i_wen1,
   input wire [B:0]	   i_wdata0,
   input wire [B:0]	   i_wdata1,
   input wire [raw-1:0]	   i_rreg0,
   input wire [raw-1:0]	   i_rreg1,
   output wire [B:0]	   o_rdata0,
   output wire [B:0]	   o_rdata1,
   //RAM side
   output wire [aw-1:0]	   o_waddr,
   output wire [width-1:0] o_wdata,
   output wire		   o_wen,
   output wire [aw-1:0]	   o_raddr,
   output wire		   o_ren,
   input wire [width-1:0]  i_rdata);

   localparam ratio = width/W;
   localparam CMSB = 4-$clog2(W); //Counter MSB
   localparam l2r  = $clog2(ratio);

   reg 				   rgnt;
   assign o_ready = rgnt | i_wreq;
   wire [CMSB:0] rcnt;

   reg 		  rtrig1;
   /*
    ********** Write side ***********
    */

   wire [CMSB:0] 	     wcnt;

   reg [width-1:0]   wdata0_r;
   reg [width+W-1:0]   wdata1_r;

   reg 		     wen0_r;
   reg 		     wen1_r;
   wire 	     wtrig0;
   wire 	     wtrig1;

   assign wtrig0 = rtrig1;

   generate if (ratio == 2) begin : gen_wtrig_ratio_eq_2
      assign wtrig1 =  wcnt[0];
   end else begin : gen_wtrig_ratio_neq_2
      reg wtrig0_r;
      always @(posedge i_clk) wtrig0_r <= wtrig0;
      assign wtrig1 = wtrig0_r;
   end
   endgenerate

   assign 	     o_wdata = wtrig1 ?
			       wdata1_r[width-1:0] :
			       wdata0_r;

   wire [raw-1:0] wreg  = wtrig1 ? i_wreg1 : i_wreg0;
   generate if (width == 32) begin : gen_w_eq_32
      assign o_waddr = wreg;
   end else begin : gen_w_neq_32
      assign o_waddr = {wreg, wcnt[CMSB:l2r]};
   end
   endgenerate

   assign o_wen = (wtrig0 & wen0_r) | (wtrig1 & wen1_r);

   generate if (W == 1) begin : gen_mixed_counter
      reg [1:0] low_state;
      wire [1:0] low_count = low_state;
      wire low_last = &low_state;
      reg [3:0] high_state;
      wire [2:0] high_count = {high_state[3],high_state[3] ^ high_state[1],^high_state};
      wire [2:0] write_high = {!high_state[0],!(high_state[2] ^ high_state[0]),!(^high_state)};
      assign rcnt = {high_count,low_count};
      assign wcnt = {write_high,low_count};
      if(RF_HIGH_PHASE_FORM > 0 && RF_HIGH_PHASE_FORM <= 12)begin : gen_three_bit_high_phase
         reg [2:0] private_physical_phase;
         wire [3:0] private_decoded_high;
         wire [2:0] private_next_phase;
         wire [2:0] private_reset_phase;
         if(RF_HIGH_PHASE_FORM == 1)begin : gen_code_1
            assign private_decoded_high[0]=(private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[2]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[0]);
            assign private_next_phase[1]=(private_physical_phase[0]) ^ (private_physical_phase[1]);
            assign private_next_phase[2]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_reset_phase=3'd0;
         end else if(RF_HIGH_PHASE_FORM == 2)begin : gen_code_2
            assign private_decoded_high[0]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[2]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[0]);
            assign private_next_phase[1]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[1]);
            assign private_next_phase[2]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_reset_phase=3'd1;
         end else if(RF_HIGH_PHASE_FORM == 3)begin : gen_code_3
            assign private_decoded_high[0]=1'b1 ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[1]=1'b1 ^ (private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[2]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[0]);
            assign private_next_phase[1]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[1]);
            assign private_next_phase[2]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_reset_phase=3'd3;
         end else if(RF_HIGH_PHASE_FORM == 4)begin : gen_code_4
            assign private_decoded_high[0]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[2]=(private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[3]=1'b1 ^ (private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[0]);
            assign private_next_phase[1]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[1]);
            assign private_next_phase[2]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_reset_phase=3'd7;
         end else if(RF_HIGH_PHASE_FORM == 5)begin : gen_code_5
            assign private_decoded_high[0]=(private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[1]);
            assign private_decoded_high[2]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=(private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_next_phase[2]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_reset_phase=3'd0;
         end else if(RF_HIGH_PHASE_FORM == 6)begin : gen_code_6
            assign private_decoded_high[0]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[1]);
            assign private_decoded_high[2]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[2]);
            assign private_next_phase[0]=(private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_next_phase[2]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_reset_phase=3'd1;
         end else if(RF_HIGH_PHASE_FORM == 7)begin : gen_code_7
            assign private_decoded_high[0]=1'b1 ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[1]=1'b1 ^ (private_physical_phase[1]);
            assign private_decoded_high[2]=(private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_next_phase[2]=(private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_reset_phase=3'd3;
         end else if(RF_HIGH_PHASE_FORM == 8)begin : gen_code_8
            assign private_decoded_high[0]=(private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[1]=1'b1 ^ (private_physical_phase[1]);
            assign private_decoded_high[2]=1'b1 ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[3]=1'b1 ^ (private_physical_phase[2]);
            assign private_next_phase[0]=(private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_next_phase[2]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_reset_phase=3'd7;
         end else if(RF_HIGH_PHASE_FORM == 9)begin : gen_code_9
            assign private_decoded_high[0]=(private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[2]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=(private_physical_phase[0]);
            assign private_next_phase[2]=(private_physical_phase[1]);
            assign private_reset_phase=3'd0;
         end else if(RF_HIGH_PHASE_FORM == 10)begin : gen_code_10
            assign private_decoded_high[0]=1'b1 ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[1]=1'b1 ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[2]=1'b1 ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=(private_physical_phase[0]);
            assign private_next_phase[2]=(private_physical_phase[1]);
            assign private_reset_phase=3'd7;
         end else if(RF_HIGH_PHASE_FORM == 11)begin : gen_code_11
            assign private_decoded_high[0]=(private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[2]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=(private_physical_phase[0]);
            assign private_next_phase[2]=(private_physical_phase[1]);
            assign private_reset_phase=3'd0;
         end else if(RF_HIGH_PHASE_FORM == 12)begin : gen_code_12
            assign private_decoded_high[0]=(private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[1]=1'b1 ^ (private_physical_phase[0]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[2]=1'b1 ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]) ^ (private_physical_phase[1] & private_physical_phase[2]);
            assign private_decoded_high[3]=1'b1 ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_next_phase[1]=(private_physical_phase[0]);
            assign private_next_phase[2]=(private_physical_phase[1]);
            assign private_reset_phase=3'd7;
         end
         always @* high_state=private_decoded_high;
      always @(posedge i_clk) begin
         low_state <= low_state + 2'd1;
         if (low_last) private_physical_phase <= private_next_phase;
         if ((i_rreq | i_wreq)) begin
            low_state <= {i_wreq,1'b0};
            private_physical_phase <= private_reset_phase;
         end
         if (i_rst && (reset_strategy != "NONE")) begin
            low_state <= 2'b00;
            private_physical_phase <= private_reset_phase;
         end
      end

      end else begin : gen_literal_high_phase
      always @(posedge i_clk) begin
         low_state <= low_state + 2'd1;
         if (low_last) high_state <= {high_state[2:0],!high_state[3]};
         if ((i_rreq | i_wreq)) begin
            low_state <= {i_wreq,1'b0};
            high_state <= 4'b0000;
         end
         if (i_rst && (reset_strategy != "NONE")) begin
            low_state <= 2'b00;
            high_state <= 4'b0000;
         end
      end

      end
   end else begin : gen_binary_counter
      reg [CMSB:0] binary_count;
      assign rcnt = binary_count;
      assign wcnt = binary_count - 4;
      always @(posedge i_clk) begin
         binary_count <= binary_count + {{CMSB{1'b0}},1'b1};
         if ((i_rreq | i_wreq)) binary_count <= {{CMSB-1{1'b0}},i_wreq,1'b0};
         if (i_rst && (reset_strategy != "NONE")) binary_count <= {CMSB+1{1'b0}};
      end
   end endgenerate

   always @(posedge i_clk) begin
      if (wcnt[0]) begin
	 wen0_r    <= i_wen0;
	 wen1_r    <= i_wen1;
      end

      wdata0_r  <= {i_wdata0,wdata0_r[width-1:W]};
      wdata1_r  <= {i_wdata1,wdata1_r[width+W-1:W]};

   end

   /*
    ********** Read side ***********
    */


   wire 	  rtrig0;

   wire [raw-1:0] rreg = rtrig0 ? i_rreg1 : i_rreg0;
   generate if (width == 32) begin : gen_rreg_eq_32
      assign o_raddr = rreg;
   end else begin : gen_rreg_neq_32
      assign o_raddr = {rreg, rcnt[CMSB:l2r]};
   end
   endgenerate

   reg [width-1:0]  rdata0;
   reg [width-1-W:0]  rdata1;

   reg 		    rgate;

   assign o_rdata0 = rdata0[B:0];
   assign o_rdata1 = rtrig1 ? i_rdata[B:0] : rdata1[B:0];

   assign rtrig0 = (rcnt[l2r-1:0] == 1);

   generate if (ratio == 2) begin : gen_ren_w_eq_2
      assign o_ren = rgate;
   end else begin : gen_ren_w_neq_2
      assign o_ren = rgate & (rcnt[l2r-1:1] == 0);
   end
   endgenerate

   reg 	      rreq_r;

   generate if (ratio > 2) begin : gen_rdata1_w_neq_2
      always @(posedge i_clk) begin
	 rdata1 <= {{W{1'b0}},rdata1[width-W-1:W]};
	 if (rtrig1)
	   rdata1[width-W-1:0] <= i_rdata[width-1:W];
      end
   end else begin : gen_rdata1_w_eq_2
      always @(posedge i_clk) if (rtrig1) rdata1 <= i_rdata[W*2-1:W];
   end
   endgenerate

   always @(posedge i_clk) begin
      if (&rcnt | i_rreq)
	rgate <= i_rreq;

      rtrig1 <= rtrig0;

      rreq_r <= i_rreq;
      rgnt <= rreq_r;

      rdata0 <= {{W{1'b0}}, rdata0[width-1:W]};
      if (rtrig0)
	rdata0 <= i_rdata;

      if (i_rst) begin
	 if (reset_strategy != "NONE") begin
	    rgate <= 1'b0;
	    rgnt <= 1'b0;
	    rreq_r <= 1'b0;
	 end
      end
   end



endmodule
