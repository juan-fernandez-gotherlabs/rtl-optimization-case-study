# INT8 4x4 matrix-vector RTL optimization

[Read the technical report](../../INT8-MatVec-Optimization.pdf) or run the
compact verifier with `python3 verify.py` from this directory.

This case optimizes a small, synthesizable signed-INT8 matrix-vector datapath:
four input values, a 4x4 weight matrix, sixteen signed multiplications and four
signed-INT32 outputs. Matrix-vector multiplication is a central arithmetic
primitive in quantized linear and projection layers. This case is deliberately
not presented as a complete neural network, accelerator platform or deployment.

## Result

| Primary metric | Frozen baseline | Accepted RTL | Paired improvement |
|---|---:|---:|---:|
| VTR total area estimate | 33,892,339 MWTA | 28,607,064 MWTA | **15.5943%** |
| Post-route critical path | 11.1642 ns | 10.8085 ns | **3.1868%** |
| Active total power estimate | 22.4567 mW | 21.1749 mW | **5.7081%** |
| Composite score | 1.000000 | 0.916770 | **8.3230%** |

The accepted RTL replaces unnecessary full-width product extensions and a
wide accumulation expression with a balanced, range-correct 17/18-bit adder
tree. The mathematical dot product and the four signed-INT32 outputs are
unchanged.

The PPA flow places the combinational DUT behind a fixed measurement wrapper
that registers only the four 32-bit outputs. The reported 72 registers belong
to that unchanged wrapper and are not state added to the candidate datapath.
The academic target is homogeneous LUT6 logic: the signed multipliers map to
LUT fabric, with no commercial DSP-slice, BRAM or ASIC MAC-cell model.

## Verification and certification

- the compact record attests that 151 deterministic signed, extreme, lane and
  seeded-random simulations passed;
- it attests that exhaustive Yosys combinational equivalence covered every
  160-bit input assignment;
- five optimizer-visible VTR placement pairs rank search candidates only;
- 64 disjoint held-out pairs determine certification;
- baseline and accepted certification records carry an exact independent-replay
  attestation;
- the composite one-sided 95% upper confidence bound remains below `1.0`;
- every primary metric passes its non-regression bound and the resource envelope.

The public compact certificate replaces held-out placement-seed identities with
stable pair labels. It retains both designs' complete paired metrics so the
statistics and decision can be recomputed without exposing the reserved pool.
The public verifier checks certificate consistency, RTL identity, the exact
patch and all derived statistics. It does not rerun the recorded functional,
formal or VTR jobs and does not parse raw VTR run trees.

## Public artifacts

- [`rtl/baseline/int8_matvec_4x4.sv`](rtl/baseline/int8_matvec_4x4.sv)
- [`rtl/optimized/int8_matvec_4x4.sv`](rtl/optimized/int8_matvec_4x4.sv)
- [`rtl/changes.patch`](rtl/changes.patch)
- [`certificate.json`](certificate.json)
- [`technical-report.pdf`](technical-report.pdf)

## Claim boundary

These are paired academic VTR PTM 45 nm post-route estimates at 0.9 V and
85 degrees C on a homogeneous LUT6 target without commercial DSP or BRAM
resources. They are not physical FPGA measurements, Vivado results, ASIC or
silicon signoff, board measurements, measured power or measured energy. This
compact edition is not a public raw-log provenance audit equivalent to the
historical SHA-1 v1.3.1 release asset.

The RTL is owned by the Evolther project and Apache-2.0 licensed. The
optimization implementation and private execution data are intentionally
outside this public evidence package.
