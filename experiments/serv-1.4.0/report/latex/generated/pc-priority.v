      else if (WORD_BANK_ENABLE_FORM == 3) begin
      if (i_rst | i_pc_en) o_ibus_adr <= i_pc_en ? (i_rst ? RESET_PC : {new_pc, o_ibus_adr[31:W]}) : RESET_PC;
