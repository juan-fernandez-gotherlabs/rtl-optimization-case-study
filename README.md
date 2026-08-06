# SHA-1 RTL optimization on VTR

A four-line, cycle-equivalent RTL revision improves the estimated composite
PPA score by **5.98%** under a frozen VTR 45 nm FPGA comparison.

| Metric | Corrected baseline | Accepted RTL | Paired improvement (95% CI) |
|---|---:|---:|---:|
| Total area | 16,614,693 MWTA | 16,614,693 MWTA | 0.03% (-0.04%, 0.09%) · neutral |
| Critical path | 15.0054 ns | 13.28085 ns | **11.43%** (10.87%, 11.98%) |
| Energy / block | 12.3896 nJ | 11.6399 nJ | **6.14%** (5.77%, 6.52%) |
| Composite PPA | 1.000000 | 0.940188 | **5.98%** (5.69%, 6.27%) |

The result uses 64 fixed, paired VPR seeds. Timing, energy and composite score
improve in all 64 comparisons; area is statistically neutral.

## Review the result

- [Technical report](technical-report.pdf) — method, diagrams, statistics,
  trade-offs and claims boundary.
- [Exact four-line patch](rtl/baseline-to-accepted.patch).
- [Corrected baseline](rtl/baseline/sha.v) and [accepted RTL](rtl/accepted/sha.v).
- [Compact 64-seed certification](results/certification.json).

## Verify

The audit uses only the Python standard library. It checks every published
checksum, reconstructs the RTL patch and recomputes medians, paired confidence
intervals and the composite score from all 64 seed pairs.

```bash
python3 verify.py
```

Expected result:

```text
Verification: PASS
paired_seeds=64
composite_score=0.940187630028
improvement=5.98% (95% CI 5.69% to 6.27%)
formal_status=pass
```

The complete formal, functional, route and power logs are available in the
[v1.2.0 release](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/tag/v1.2.0).

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
