# SHA-1 RTL optimization

Historical methodology-qualification case in the
[verified RTL portfolio](../../README.md).

## What this module does

The sequential SHA-1 compression module receives a 512-bit block through a
32-bit command/data interface and updates a 160-bit chaining state over 80
rounds. SHA-1 is retained as a legacy compute benchmark, not recommended as a
modern security primitive.

## What changed

Three cycle-equivalent transformations simplify the Boolean and readout logic:

- replace XOR with OR where the choose-function terms are mutually exclusive;
- share XOR terms across the parity and majority round functions;
- read the five chaining-state registers directly instead of slicing a
  temporary 160-bit concatenation.

The interface, reset, command protocol, read order, latency, throughput and
defined-input cycle behaviour remain fixed. See the
[exact patch](rtl/baseline-to-accepted.patch).

## Result

| Metric | Baseline | Optimized | Paired improvement | 95% interval |
|---|---:|---:|---:|---:|
| Total area | 16,614,693 MWTA | 16,614,693 MWTA | **0.15%** | 0.08% to 0.21% |
| Critical path | 15.0054 ns | 14.2090 ns | **5.20%** | 4.64% to 5.75% |
| Active total power | 9.9125 mW | 9.7755 mW | **1.38%** | 0.89% to 1.87% |
| Composite PPA | 1.000000 | 0.977335 | **2.27%** | 2.12% to 2.41% |

MWTA is VTR's minimum-width transistor-area unit. Packed CLBs fall from 188 to
182. Energy per completed block is secondary and improves by 6.51% (95%
interval: 6.14% to 6.87%). The composite is the
equal-weight geometric mean of paired area, post-route delay and active-total-
power ratios over 64 fixed pairs. Cross-case percentages are not a
cross-circuit performance ranking.

## Correctness evidence

- 129 NIST SHA-1 Short and Long Message cases;
- deterministic cycle-level protocol regression;
- complete two-state sequential EQY equivalence after reset;
- 64 certification seeds disjoint from five optimizer-visible search seeds;
- raw VTR/ACE timing, area and power records for baseline and optimized RTL.

Here, certification means acceptance under the published project contract,
not accredited certification or an external assurance opinion.

## Verify

Compact consistency verification requires only Python 3:

```bash
python3 verify.py
```

Expected ending:

```text
Compact package consistency: PASS
paired_seeds=64
improvement=2.27% (95% CI 2.12% to 2.41%)
Full raw evidence: NOT CHECKED (pass --evidence-archive)
```

For raw-provenance verification, download the
[v2.1.0 evidence asset](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v2.1.0/sha1-vtr45-full-evidence-v2.tar.gz)
and run:

```bash
python3 verify.py --evidence-archive sha1-vtr45-full-evidence-v2.tar.gz
```

This checks every archived member and re-extracts all 128 publication-run PPA
rows. It does not rerun the EDA tools.

## Source and licensing

The RTL descends from the OpenCores core redistributed by VTR at pinned commit
`95f5c6de9e158371ba7185bf97c07a84153735d6`. Source headers retain the
original copyright, redistribution condition and disclaimer.

Earlier releases corrected a documentation-level interface description from
`cmd_i[3:0]` to the actual `cmd_i[2:0]`. The measured RTL, raw outputs, metrics
and acceptance result were unchanged. Full transformation history remains in
the [technical report](technical-report.pdf) and immutable releases.

## Claim boundary

This is a comparative VTR/PTM 45 nm FPGA estimate under two-state,
defined-input semantics. It is not ASIC signoff, a commercial-FPGA result,
physical-board measurement, measured energy, manufactured-silicon evidence or
an endorsement of SHA-1 for new security systems.
