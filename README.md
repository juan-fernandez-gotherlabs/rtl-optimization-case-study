# Göther Labs verified RTL optimization results

Three small, auditable before/after RTL cases show how Göther Labs applies
Evölther to improve a frozen implementation while preserving its functional
contract. Each package
contains the baseline, optimized RTL, exact patch, paired measurements,
correctness evidence, report, checksums and a fail-closed verifier.

## Results at a glance

| Case | What the module does | Transformation | Publication result |
|---|---|---|---:|
| [SHA-1 RTL](cases/sha1/README.md) | Runs the 80-round SHA-1 compression function through a stateful command interface | Shares Boolean logic and simplifies state readout | **2.27% lower composite PPA estimate** |
| [INT8 MatVec RTL](cases/int8-matvec/README.md) | Computes four signed INT8 dot products using 16 exact multiplications | Uses range-correct widths and a balanced addition tree | **8.3230% lower composite PPA estimate** |
| [ML-KEM CBD RTL](cases/mlkem-cbd/README.md) | Converts SHAKE bits into small polynomial coefficients for post-quantum ML-KEM | Replaces wide variable state movement with fixed movement plus a byte phase | **9.7338% lower composite PPA estimate** |

All three headline values use 64 fixed paired implementations and the same
equal-weight area-delay-power score form. They are valid within each case's
own frozen contract; they are not a cross-circuit performance ranking.

## Commercial-tool transfer experiments

The published case contracts above remain tied to VTR. Separate transfer
experiments test the same frozen RTL changes with commercial FPGA tools without
mixing their metrics into the VTR headline scores.

| Experiment | Tool and target | Evidence status | Transfer result |
| --- | --- | --- | --- |
| [INT8 MatVec on Quartus](experiments/quartus-int8-matvec/README.md) | Quartus Prime Lite 25.1std.0, MAX 10 | Complete exploratory run; reports and verifier checked in | **+12.32% estimated Fmax with normal DSP inference; +9.56% in the logic-only control** |

See the [commercial-tool experiment index](experiments/README.md) for the
separate evidence boundary and limitations.

## Paused RTL research

The repository also preserves development studies whose final acceptance
remains pending. They have their own evidence packages and claim boundaries.

| Study | Saved result | Evidence status |
| --- | --- | --- |
| [SERV 1.4.0](experiments/serv-1.4.0/README.md) | **3.3474% lower composite PPA estimate in 64 fixed pairs**, with **1.9478% higher critical-path delay**; 46 to 43 CLBs, 181 FF unchanged | Optimization paused; fixed 64-pair sample complete; timing regression rejects acceptance; separate 12-pair certification unexecuted |

See [RTL-Study-SERV-1.4.0.pdf](RTL-Study-SERV-1.4.0.pdf) for the
scope, before/after metrics, search history and stopping point. SERV is a
research record; the accepted portfolio above still contains three cases.

## Why the third case matters

The portfolio now spans three distinct kinds of hardware reasoning:

- **SHA-1:** local Boolean simplification in a legacy sequential core;
- **INT8 MatVec:** arithmetic-width and tree restructuring in a combinational
  quantized-AI kernel;
- **ML-KEM CBD:** a different physical representation for 1,096 bits of
  sequential state, connected to the original state by a proved refinement
  relation.

ML-KEM CBD is therefore the conceptual step forward. It is not the longest RTL
file: the baseline has 95 nonblank, non-comment code lines, versus 73 for INT8
MatVec and 1,908 for the bundled SHA-1 core. Its significance comes from the
stateful transformation and its relevance to post-quantum cryptographic IP,
not from source-line count alone.

## Module sizes and architectural scope

<!-- module-sizes:start -->

| Module | Measured scope | RTL files¹ | Code lines¹ | CLBs² | Area² (10⁶ MWTA) |
| --- | --- | ---: | ---: | ---: | ---: |
| [SHA-1](cases/sha1/README.md) | Sequential compression core | 1 → 1 | 1,908 → 1,910 | 188 → 182 | 16.626 → 16.601 |
| [INT8 MatVec](cases/int8-matvec/README.md) | Combinational 4 × 4 kernel | 1 → 1 | 73 → 70 | 368 → 304 | 33.892 → 28.607 |
| [ML-KEM CBD](cases/mlkem-cbd/README.md) | Sequential coefficient sampler | 1 → 1 | 95 → 114 | 337 → 270 | 22.752 → 19.132 |
| [SERV 1.4.0](experiments/serv-1.4.0/README.md) | Serial 32-bit CPU and RF interface | 18 → 18 | 2,584 → 3,047 | 46 → 43 | 2.743 → 2.582 |

All arrows show baseline → optimized. ¹ Bundled source, including inactive
alternatives. ² Measured wrapper; area is the geometric mean of 64 implementations.

**SERV expands the architectural scope to a CPU, while its measured baseline is
6.06–12.35 times smaller in area than the other modules.** Its external
register RAM is excluded from these measurements: the default configuration
requires 1,152 bits (144 B), arranged as 576 rows × 2 bits. The source tree
contains 18 modules, including modules outside the measured hierarchy.

See [Module sizes and orders of magnitude](MODULE-SIZES.md) for source bytes,
state, memory capacity, mapped registers, measurement boundaries and reproducible tables.

<!-- module-sizes:end -->

## Read the reports

- [RTL-Study-SHA1.pdf](RTL-Study-SHA1.pdf) — historical
  methodology-qualification case.
- [RTL-Study-INT8-MatVec.pdf](RTL-Study-INT8-MatVec.pdf) — quantized
  arithmetic case.
- [RTL-Study-MLKEM-CBD.pdf](RTL-Study-MLKEM-CBD.pdf) — post-quantum
  state-representation case.
- [RTL-Study-SERV-1.4.0.pdf](RTL-Study-SERV-1.4.0.pdf) — paused CPU
  research study; 64 pairs, with the timing regression documented.

The reports are kept at the repository root so a technical reviewer can reach
the result without first navigating the evidence tree. All study PDFs use
`RTL-Study-<module>.pdf`; each evidence package keeps an identical copy with the
same filename. The shared prefix groups them together in the file listing.

## What the evidence means

```text
Frozen baseline, interface and score
                 |
         bounded optimization
                 |
     functional + formal validity
                 |
      pinned implementation metrics
                 |
      fixed paired acceptance test
```

The optimization machinery is outside this public package. The inspectable
boundary is the input RTL, accepted RTL, exact source change, correctness
result, paired measurement certificate and public verifier.

## Verify the portfolio and transfer evidence

Only Python 3 is required for compact consistency verification:

```bash
python3 verify.py
```

Expected ending:

```text
SHA-1 compact evidence: PASS
INT8 MatVec compact evidence: PASS
ML-KEM CBD compact evidence: PASS
Quartus INT8 MatVec compact evidence: PASS
SERV 1.4.0 saved research evidence: PASS
development_pairs=12; improvement=3.4516%
final_pairs=64; final_improvement=3.3474%
timing_regression=1.9478%; acceptance=evidence_regression
held_out_certification_pairs=0; publication_accepted=False
Scope: saved evidence consistency; no fresh EDA execution or PPA certification.
Module size comparison: PASS
Portfolio verification: PASS
```

Each case README also links a separately downloadable, hash-addressed raw
evidence archive. Supplying that archive to the case verifier checks every
member and re-extracts the published post-route PPA metrics. This audits the
recorded evidence; it does not rerun the EDA tools.

## Claim boundary

The three headline cases use academic VTR/PTM 45 nm post-route comparisons on a
homogeneous LUT6 target. Power comes from either a fixed activity trace or the
explicitly declared ACE probabilistic model. Those headline figures are not
ASIC signoff, commercial-FPGA characterization, Vivado or Quartus results,
physical-board measurements, measured energy or manufactured-silicon evidence.

Commercial-tool transfer experiments have their own narrower claim boundaries.
The Quartus experiment is a fixed-seed emulated implementation comparison, not
a physical-board measurement, native-host replay or measured-power result. The
ML-KEM case is also not side-channel analysis or certification of a complete
cryptographic system.

Read [METHODOLOGY.md](METHODOLOGY.md) for the common evidence model and
[AUDIT.md](AUDIT.md) for the external-audit protocol.
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) records provenance and
licensing.

## Evaluating a customer design

A pilot starts by freezing one owned design interface, correctness suite,
implementation target, objective and validity limits. Göther Labs can then
produce a bounded before/after result and an agreed evidence package before a
larger engagement.

[Evaluate one RTL block with Göther Labs](https://www.gotherlabs.com/rtl-optimization/)
