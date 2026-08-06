# SHA-1 RTL optimization on VTR

[![Verify result](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/actions/workflows/verify.yml/badge.svg)](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/actions/workflows/verify.yml)

## Evaluated technical improvement

Four cycle-equivalent RTL rewrites reduce the estimated composite PPA score by **5.98%** under a frozen VTR 45 nm FPGA contract. Critical-path delay improves by **11.43%**, workload energy by **6.14%**, and total estimated area remains statistically neutral.

![Baseline versus accepted RTL](figures/certified-ppa-profile.svg)

The interface, reset behavior, command protocol, latency, throughput, state-visible behavior and implementation flow remain fixed. This is an open academic FPGA estimate, not ASIC signoff, a commercial-FPGA result or manufactured silicon.

## Baseline versus accepted RTL

| Metric | Baseline median | Accepted RTL median | Paired improvement (95% CI) |
|---|---:|---:|---:|
| Total area | 16,614,693 MWTA | 16,614,693 MWTA | **+0.03%** (-0.04%, +0.09%) · neutral |
| Critical path | 15.0054 ns | 13.28085 ns | **+11.43%** (+10.87%, +11.98%) |
| Energy / block | 12.3896 nJ | 11.6399 nJ | **+6.14%** (+5.77%, +6.52%) |
| Composite PPA | 1.000000 | 0.940188 | **+5.98%** (+5.69%, +6.27%) |

Timing, energy and the composite score improve in all 64 paired implementations. Area produces 14 wins, 41 exact ties and 9 losses and is therefore reported as neutral. Active total power rises from 9.9125 mW to 10.4900 mW at the medians; energy per completed block falls because the routed implementation completes the fixed workload faster.

## The accepted change

Only four assignments differ between the [corrected baseline](rtl/baseline/sha.v) and the [accepted RTL](rtl/accepted/sha.v): two equivalent SHA-1 Boolean forms, one balanced XOR tree and one reassociated modulo-2^32 addition.

- [Review the exact patch](rtl/baseline-to-accepted.patch).
- [Read the engineering explanation](report/technical-report.md#6-the-four-rtl-rewrites).
- [Inspect the formal proof identity](evidence/formal-proof.json).

![Representative implementation evidence](figures/netlist-evidence.svg)

For representative seed 20, the accepted RTL reduces the VPR timing graph from 46 to 42 levels and packs into 187 rather than 188 CLBs. It contains slightly more ABC `.names` nodes, so the result is a topology and packing improvement rather than a simple gate-count reduction.

## Why the result is reviewable

![Verification-first evaluation contract](figures/verification-pipeline.svg)

- `sha.v` is the only editable artifact and is frozen by SHA-256.
- The exact interface and cycle behavior are fixed.
- NIST SHAVS Short and Long Message tests cover 129 cases; qualification also includes 100,000 Monte Carlo hashes.
- Pinned EQY proves conservative sequential equivalence. Failure, timeout or inconclusive status invalidates the RTL.
- Five hundred deterministic MCY mutations qualify the verification stack: 454 simulation-detected, 28 formal-only rejected, 18 proven equivalent and zero inconclusive.
- Sixty-four fixed, paired VPR seeds support the published PPA comparison.
- The public score and confidence intervals are recomputed from raw paired records.

## Audit the evidence

The fast audit needs Python 3 only and performs no new EDA measurement:

```bash
make verify
```

Regenerate figures and reports:

```bash
make figures
make report
```

The canonical 15-page technical report is compiled from native XeLaTeX using the open TeX Gyre font family. `make report` also regenerates the two-page executive PDF. See [Reproducibility](REPRODUCIBILITY.md) for the exact Linux packages and build contract.

The equation SVGs are checked in with their standalone LaTeX sources. Regenerate them when those sources change:

```bash
make equations  # requires pdflatex and pdftocairo
```

See [Reproducibility](REPRODUCIBILITY.md) for the pinned Linux/amd64 measurement image, resource limits and complete certification command.

## Read the result

- [Executive summary](EXECUTIVE_SUMMARY.md)
- [Resumen ejecutivo en español](RESUMEN_EJECUTIVO_ES.md)
- [Technical report](report/technical-report.md)
- [Technical report PDF](report/technical-report.pdf)
- [Executive PDF](report/executive-summary.pdf)
- [Claims boundary](LIMITATIONS.md)
- [Evidence index](evidence/README.md)
- [Third-party provenance](THIRD_PARTY_NOTICES.md)

## Repository map

```text
rtl/          corrected baseline, accepted RTL and exact patch
contract/     frozen interface, testbenches, EQY config and domain manifest
results/      compact baseline and accepted 64-seed measurements
evidence/     formal and artifact identities plus checksums
figures/      generated baseline-versus-accepted SVG figures and equations
report/       canonical XeLaTeX/PDF report, Markdown companion and equation sources
scripts/      evidence verifier, figure generator and report builder
reproduce/    evaluator snapshot and pinned Docker environment
```

## Measurement boundary

The target is VTR's open homogeneous FPGA architecture `k6_N10_I40_Fi6_L4_frac0_ff1_45nm.xml`, using its PTM45 technology model at 0.9 V and 85 °C. These values are comparative estimates within this exact contract and do not transfer numerically to another device, technology or signoff flow. SHA-1 is used only as a legacy compute benchmark and is not recommended for new security designs.

## Göther Labs

This case study demonstrates Göther Labs' approach to evaluated technical improvement: freeze the contract, make the change inspectable and accept the result only when the evidence survives independent checks. Documentation and original tooling are available under the MIT License; third-party artifacts retain their own notices and licenses.

- [Göther Labs](https://www.gotherlabs.com/)
- [Public case-study repository](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study)
