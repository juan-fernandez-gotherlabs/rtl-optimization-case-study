# Fixed register-to-register timing boundary.
create_clock -name clk -period 5.000000000 [get_ports {clk}]
set_clock_uncertainty -rise_from [get_clocks {clk}] -rise_to [get_clocks {clk}] 0.100
