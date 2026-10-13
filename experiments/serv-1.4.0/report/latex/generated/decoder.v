         assign co_alu_sub = (CAPTURE_USAGE_FORM == 2 || CAPTURE_USAGE_FORM == 3) ? legacy_co_alu_sub : captured_alu_sub;

         assign co_rd_op = (CAPTURE_USAGE_FORM == 1 || CAPTURE_USAGE_FORM == 3) ? legacy_co_rd_op : captured_rd_op;

         always @(posedge clk) begin
            if (i_wb_en) begin
               captured_alu_sub <= capture_co_alu_sub;
               captured_rd_op <= capture_co_rd_op;
               funct3_encoded <= i_wb_rdt[14:12] ^ 3'b101;
