# RTL experiments and research records

## Paused research

Research records preserve source and evidence from development studies before
final project-contract acceptance. Development results remain labelled as
development results and are not added to the accepted portfolio case table.

| Study | Target | Status | Saved result |
| --- | --- | --- | --- |
| [SERV 1.4.0](serv-1.4.0/README.md) | Academic VTR/PTM 45 nm, LUT6, ACE probabilistic activity | Paused; 12 development pairs; held-out certification and final 64 pairs pending | 3.4516% lower composite estimate; area 5.9467% lower, power 4.3802% lower, delay 0.0721% higher. |

The SERV verifier recomputes the 24 implementation rows from saved reports and
checks source identities and recorded correctness. It does not execute EDA or
claim final acceptance. Its original greater-than-10% objective is unmet.

## Commercial-tool transfer experiments

The verified portfolio cases use a pinned academic VTR/PTM 45 nm target. The
experiments in this directory ask a separate question: does the same frozen RTL
change remain useful when a commercial FPGA tool maps it to a real device?

These experiments do not replace the publication contract of the corresponding
case and are not numerically comparable across FPGA families or toolchains.

| Experiment | Tool and target | Status | Result |
| --- | --- | --- | --- |
| [INT8 MatVec on Quartus](quartus-int8-matvec/README.md) | Quartus Prime Lite 25.1std.0, MAX 10 `10M50DAF484C7G` | Complete exploratory transfer run | Estimated Fmax improves 12.32% with normal DSP inference and 9.56% in the logic-only control. |

"Exploratory" means that the exact reports and compact verifier are public, but
the run used full x86-64 QEMU emulation on Apple Silicon, one fixed fitter seed,
and vectorless low-confidence power estimation. It is not a native-host replay
or a physical-board measurement.
