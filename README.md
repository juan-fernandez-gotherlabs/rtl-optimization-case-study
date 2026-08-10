# SHA-1 RTL optimization on VTR

Three cycle-equivalent RTL transformations improve the estimated composite
PPA score by **2.27%** under a frozen VTR 45 nm FPGA comparison.

| Primary metric | Corrected baseline | Accepted RTL | Paired improvement (95% CI) |
|---|---:|---:|---:|
| Total area | 16,614,693 MWTA | 16,614,693 MWTA | **0.15%** (0.08%, 0.21%) |
| Critical path | 15.0054 ns | 14.2090 ns | **5.20%** (4.64%, 5.75%) |
| Active total power | 9.9125 mW | 9.7755 mW | **1.38%** (0.89%, 1.87%) |
| Composite PPA | 1.000000 | 0.977335 | **2.27%** (2.12%, 2.41%) |

The result uses 64 fixed, paired VPR seeds. Area improves in 30 comparisons,
ties in 28 and regresses in 6; timing improves in all 64; active power improves
in 46 and regresses in 18. The paired 95% intervals remain on the improvement
side for all three primary metrics, and the composite improves in all 64 pairs.

Energy per completed block is retained as a secondary operating metric: its
median falls from 12.3896 nJ to 11.5718 nJ, with a paired estimate of **6.51%**
(95% CI: 6.14% to 6.87%). It is not an input to the primary PPA score.

## Review the result

- [Technical report](technical-report.pdf) — method, conceptual diagrams,
  64-seed statistics and claims boundary.
- [Exact baseline-to-accepted patch](rtl/baseline-to-accepted.patch).
- [Corrected baseline](rtl/baseline/sha.v) and [accepted RTL](rtl/accepted/sha.v).
- [Compact 64-seed certification](results/certification.json).

## Verify

The audit uses only the Python standard library. It checks every published
checksum, reconstructs the RTL patch and recomputes medians, paired confidence
intervals and the area-delay-power score from all 64 seed pairs.

```bash
python3 verify.py
```

Expected result:

```text
Verification: PASS
paired_seeds=64
composite_score=0.977334953847
improvement=2.27% (95% CI 2.12% to 2.41%)
formal_status=pass
```

The full formal, functional, route and power evidence is retained outside
normal Git history and is available for technical audit. Its result identity
and evidence hashes are recorded in the compact certification.

## Scope

This is a comparative estimate on VTR's open 45 nm FPGA architecture at
0.9 V and 85 °C. It is not ASIC signoff, a commercial-FPGA measurement or
manufactured silicon. SHA-1 is used only as a legacy compute benchmark.

## Provenance and license

The SHA-1 RTL descends from the OpenCores core redistributed by VTR at commit
`95f5c6de9e158371ba7185bf97c07a84153735d6`. Its original copyright notice,
redistribution condition and disclaimer remain in both RTL files. VTR, EQY and
NIST remain governed by their respective upstream terms.

The MIT License applies to the original Göther Labs case-study material and
verification code. Third-party material retains its original terms.

[Göther Labs](https://www.gotherlabs.com/)
