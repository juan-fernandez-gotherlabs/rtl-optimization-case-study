            assign private_decoded_high[0]=(private_physical_phase[0]) ^ (private_physical_phase[1]) ^ (private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[1]=(private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[2]=(private_physical_phase[0] & private_physical_phase[1]) ^ (private_physical_phase[2]);
            assign private_decoded_high[3]=(private_physical_phase[2]);
            assign private_next_phase[0]=1'b1 ^ (private_physical_phase[0]);
            assign private_next_phase[1]=(private_physical_phase[0]) ^ (private_physical_phase[1]);
