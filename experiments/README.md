# Commercial-tool transfer experiments

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
