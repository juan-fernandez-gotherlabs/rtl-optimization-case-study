# Limitations and claims boundary

This document is part of the result. A claim outside these boundaries is not supported by the published evidence.

## Technology target

The PPA values are estimates from an open academic FPGA flow:

- VTR/VPR at commit `95f5c6de9e158371ba7185bf97c07a84153735d6`.
- Homogeneous non-fracturable LUT6 architecture `k6_N10_I40_Fi6_L4_frac0_ff1_45nm.xml`.
- VTR PTM45 technology properties at the architecture's 0.9 V, 85 °C point.
- ACE signal activity derived from a fixed 5,000-cycle legal workload.

The values are useful for controlled comparison within this exact contract. They are not portable absolute estimates for a commercial FPGA or ASIC process.

## Excluded signoff concerns

The flow does not provide production clock-tree synthesis, extracted parasitics, multi-corner multi-mode closure, IR drop, electromigration, signal integrity, DRC/LVS, package or board analysis, yield, production test or manufactured-silicon validation.

## Formal scope

The pinned EQY proof is unbounded but deliberately conservative and structure-aware. It compares public outputs and same-named internal cut points. This supports local cycle-exact rewrites but may reject an output-equivalent candidate that substantially recodes state, retimes registers or replaces the microarchitecture. Such a rejection is a false negative for optimization, not a false proof of correctness.

## Statistical scope

The 64-seed pool is a fixed sample of VPR placement/routing randomness. The reported confidence intervals quantify variation across that declared pool under the pinned flow. They do not model process variation, voltage, temperature, workload variation, tool-version changes or different architecture choices.

The sample size was fixed before inspecting finalist outcomes and was not extended. The area result is explicitly neutral because its interval crosses no change. The score combines equal-weight area, delay and workload energy ratios for search and reporting; engineering decisions must still inspect the individual metrics.

## Power and energy

VTR power is a model-based estimate. The active trace represents 60 complete legal blocks in 5,000 cycles; energy per block is total active power multiplied by workload time and divided by 60. The champion's active-power median rises while workload energy falls because delay decreases. This trade-off may be undesirable under a power-cap objective even though it is beneficial under the declared energy objective.

## Benchmark scope

SHA-1 is a legacy cryptographic algorithm and should not be selected for new security applications. It is used here only as a sequential compute benchmark with state, Boolean logic, word-level arithmetic and a clear external conformance oracle.

The original VTR RTL was non-conformant for the `abc` known-answer test. The optimization baseline is a separately corrected and frozen reference. The conformance correction is not counted as an optimization.

## Transfer to customer RTL

This result does not establish that the same edits or percentage improvement apply to a processor, vector unit, accelerator or any proprietary design. A customer pilot must requalify the functional contract, formal strategy, technology libraries, constraints, activity, implementation flow and acceptance policy. Only results produced and reproduced within that customer-owned flow should support product decisions.
