# SHA-1 RTL optimization on VTR

Three cycle-equivalent RTL transformations improve the paired primary PPA
estimate by **2.27%** under a frozen VTR 45 nm FPGA comparison.

| Primary metric | Corrected baseline | Accepted RTL | Paired improvement (95% CI) |
|---|---:|---:|---:|
| Total area | 16,614,693 MWTA | 16,614,693 MWTA | **0.15%** (0.08%, 0.21%) |
| Critical path | 15.0054 ns | 14.2090 ns | **5.20%** (4.64%, 5.75%) |
| Active total power | 9.9125 mW | 9.7755 mW | **1.38%** (0.89%, 1.87%) |
| Composite estimator | 1.000000 | 0.977335 | **2.27%** (2.12%, 2.41%) |

The score is the equal-weight geometric mean of paired area, post-route delay
and active-total-power ratios over 64 fixed certification seeds. `0.977335` is
the paired geometric-mean estimator; the median of the 64 per-seed composite
ratios is `0.978469`. Energy per block is secondary and improves by **6.51%**
(95% CI: 6.14% to 6.87%).

The five search seeds (`1, 7, 19, 43, 97`) are disjoint from the fixed
certification pool: the other 64 seeds in `1..68`. The certification sample is
never extended after observing a candidate.

## Review

- [Technical report](technical-report.pdf) - method, RTL transformations,
  verification scope, distributions and limitations.
- [Exact baseline-to-accepted patch](rtl/baseline-to-accepted.patch).
- [Corrected baseline](rtl/baseline/sha.v) and [accepted RTL](rtl/accepted/sha.v).
- [Compact certification](results/certification.json) with all 64 paired rows.
- [Full raw evidence release](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/tag/v1.3.0-rc3)
  with baseline and accepted VTR/ACE outputs, formal/NIST evidence and an
  11,362-file internal manifest.

## Verify

The compact audit uses only Python 3 and is intentionally described as a
consistency check, not as raw-provenance certification:

```bash
python3 verify.py
```

Expected ending:

```text
Compact package consistency: PASS
paired_seeds=64
composite_estimate=0.977334953847
composite_per_seed_median=0.978469312455
improvement=2.27% (95% CI 2.12% to 2.41%)
Full raw evidence: NOT CHECKED (pass --evidence-archive)
```

To audit every raw file, download the release asset and supply it explicitly:

```bash
curl -LO https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v1.3.0-rc3/primary-ppa-full-evidence.tar.gz
python3 verify.py --evidence-archive primary-ppa-full-evidence.tar.gz
```

The second command verifies the external archive digest, all internal member
hashes, exact formal and NIST markers, both RTL identities and the accepted
record-to-RTL binding before reporting `Full raw evidence: PASS`.

Adversarial verifier tests run with:

```bash
python3 -m unittest discover -s tests -v
```

## Rebuild the report

The checked-in LaTeX source and generated data make the PDF rebuildable:

```bash
python3 scripts/generate_latex_data.py
make technical-report
```

## Scope

This is a two-state, defined-input equivalence contract and a comparative
estimate on VTR's open 45 nm FPGA architecture at 0.9 V and 85 °C. It does not
claim identical X/Z propagation, ASIC signoff, a commercial-FPGA measurement
or manufactured silicon. SHA-1 is used only as a legacy compute benchmark.

The SHA-1 RTL descends from the OpenCores core redistributed by VTR at commit
`95f5c6de9e158371ba7185bf97c07a84153735d6`. Third-party material retains its
upstream terms; the repository MIT License covers original Göther Labs work.

[Göther Labs](https://www.gotherlabs.com/)
