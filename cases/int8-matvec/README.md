# INT8 4x4 matrix-vector RTL optimization

Quantized-arithmetic case in the
[verified RTL portfolio](../../README.md).

## What this module does

The combinational datapath accepts four signed INT8 activations and a 4x4
signed INT8 weight matrix. It performs sixteen exact 8x8 multiplications and
returns four signed INT32 dot products. Matrix-vector multiplication is a core
operation in quantized linear and projection layers; this case is not presented
as a complete neural network or accelerator platform.

## What changed

The optimized RTL replaces sixteen unnecessary 32-bit product extensions and a
wide chained accumulation with a balanced, range-correct tree:

- pairwise products are accumulated in signed 17-bit sums;
- each row is completed in one signed 18-bit sum;
- sign extension to the 32-bit interface occurs once, at the output.

The exact mathematical dot product and every output bit remain unchanged. See
the [exact patch](rtl/changes.patch).

## Result

| Metric | Baseline | Optimized | Paired improvement | 95% interval |
|---|---:|---:|---:|---:|
| Total area | 33,892,339 MWTA | 28,607,064 MWTA | **15.5943%** | 15.5355% to 15.6531% |
| Critical path | 11.1642 ns | 10.8085 ns | **3.1868%** | 2.5843% to 3.7855% |
| Active total power | 22.4567 mW | 21.1749 mW | **5.7081%** | 5.1622% to 6.2509% |
| Composite PPA | 1.000000 | 0.916770 | **8.3230%** | 8.1997% to 8.4462% |

MWTA is VTR's minimum-width transistor-area unit. Packed CLBs fall from 368 to
304 and mapped logic elements from 2,586 to 2,467. The PPA flow places the DUT
behind a fixed output-register wrapper; the reported 72 registers belong to
that unchanged wrapper, not to candidate datapath state. The target has no commercial DSP-slice, BRAM or ASIC MAC-cell model,
so every multiplier maps to LUT fabric.

The composite is the equal-weight geometric mean of paired area, post-route
delay and active-total-power ratios over 64 fixed pairs. Cross-case percentages
are not a cross-circuit performance ranking.

## Correctness evidence

- 151 deterministic signed, extreme, lane and seeded-random simulations;
- exhaustive Yosys combinational equivalence for every 160-bit input assignment;
- 64 held-out publication pairs disjoint from five optimizer-visible pairs;
- a separate deterministic project replay for baseline and optimized RTL;
- raw VTR timing, area and active/idle power evidence for all four legs.

The replay is project-operated evidence, not independent third-party
reproduction. Certification means acceptance under the published project
contract, not accredited certification.

## Verify

Compact consistency verification requires only Python 3:

```bash
python3 verify.py
```

Expected ending:

```text
INT8 MatVec compact evidence: PASS
held_out_pairs=64
improvement=8.3230%
Full raw evidence: NOT CHECKED (pass --evidence-archive)
```

For raw-provenance verification, download the
[v2.0.1 evidence asset](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v2.0.1/int8-matvec-vtr45-full-evidence-v1.tar.gz)
and run:

```bash
python3 verify.py --evidence-archive int8-matvec-vtr45-full-evidence-v1.tar.gz
```

Full mode re-extracts all 256 post-route PPA rows and checks the four functional
and formal pass records. It does not rerun the EDA tools.

## Source and licensing

The baseline and optimized RTL are original work copyright 2026 Juan José
Fernández and licensed under Apache License 2.0. The frozen source files retain
their original Evolther-contributors header and are kept byte-exact to preserve
their published evidence identities.

## Claim boundary

These are paired VTR/PTM 45 nm estimates at 0.9 V and 85 degrees C on a
homogeneous LUT6 target. They are not Vivado results, ASIC signoff,
physical-board measurements, measured power or energy, manufactured-silicon
evidence, or proof that the same structure improves another matrix size,
precision, architecture or workload.
