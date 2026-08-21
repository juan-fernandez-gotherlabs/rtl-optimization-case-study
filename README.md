# Evolther verified RTL optimization results

Three small, auditable before/after RTL cases show how Evolther improves a
frozen implementation while preserving its functional contract. Each package
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

## Read the reports

- [SHA1-RTL-Optimization.pdf](SHA1-RTL-Optimization.pdf) — historical
  methodology-qualification case.
- [INT8-MatVec-Optimization.pdf](INT8-MatVec-Optimization.pdf) — quantized
  arithmetic case.
- [MLKEM-CBD-Optimization.pdf](MLKEM-CBD-Optimization.pdf) — post-quantum
  state-representation case.

The reports are kept at the repository root so a technical reviewer can reach
the result without first navigating the evidence tree.

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

## Verify all three cases

Only Python 3 is required for compact consistency verification:

```bash
python3 verify.py
```

Expected ending:

```text
SHA-1 compact evidence: PASS
INT8 MatVec compact evidence: PASS
ML-KEM CBD compact evidence: PASS
Portfolio verification: PASS
```

Each case README also links a separately downloadable, hash-addressed raw
evidence archive. Supplying that archive to the case verifier checks every
member and re-extracts the published post-route PPA metrics. This audits the
recorded evidence; it does not rerun the EDA tools.

## Claim boundary

The cases use academic VTR/PTM 45 nm post-route comparisons on a homogeneous
LUT6 target. Power comes from either a fixed activity trace or the explicitly
declared ACE probabilistic model. These are not ASIC signoff, commercial-FPGA
characterization, Vivado or Quartus results, physical-board measurements,
measured energy or manufactured-silicon evidence. The ML-KEM case is also not
side-channel analysis or certification of a complete cryptographic system.

Read [METHODOLOGY.md](METHODOLOGY.md) for the common evidence model and
[AUDIT.md](AUDIT.md) for the external-audit protocol.
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) records provenance and
licensing.

## Evaluating a customer design

A pilot starts by freezing one owned design interface, correctness suite,
implementation target, objective and validity limits. Göther Labs can then
produce a bounded before/after result and an agreed evidence package before a
larger engagement.

[Göther Labs](https://www.gotherlabs.com/)
