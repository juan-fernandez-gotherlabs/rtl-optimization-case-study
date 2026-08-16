# Evolther verified RTL optimization results

Evolther improves bounded technical implementations while preserving a frozen
functional contract. Each published result is verified for correctness,
measured on a pinned implementation target and certified on evidence separated
from the optimization search.

## Results at a glance

| Case | Circuit | Correctness evidence | Certification | Result |
|---|---|---|---|---:|
| [SHA-1 RTL](cases/sha1/README.md) | Stateful cryptographic datapath and command protocol | NIST SHAVS, cycle regression and sequential formal equivalence | 64 fixed pairs, disjoint from search, with raw-evidence audit | **2.27% better** |
| [INT8 MatVec RTL](cases/int8-matvec/README.md) | Signed-INT8 4x4 matrix-vector kernel for quantized AI arithmetic | 151 deterministic tests and exhaustive combinational equivalence | 64 fixed held-out pairs with exact independent replay | **8.3230% better** |

### Read the reports

- **[SHA1-RTL-Optimization.pdf](SHA1-RTL-Optimization.pdf)** - historical
  methodology-qualification case.
- **[INT8-MatVec-Optimization.pdf](INT8-MatVec-Optimization.pdf)** - current
  quantized AI-kernel case.

The reports are intentionally available at the repository root so a technical
customer can reach the result without navigating the evidence tree.

## What the evidence means

```text
Frozen baseline and requirements
              |
      bounded optimization
              |
  functional and formal proof
              |
  pinned implementation metrics
              |
   held-out paired certification
```

The optimization mechanism is outside this public package. The inspectable
boundary is the input RTL, accepted RTL, exact change, correctness result,
paired measurement certificate and fail-closed verifier.

## Verify both cases

Only Python 3 is required for the compact consistency checks:

```bash
python3 verify.py
```

Expected result:

```text
SHA-1 compact evidence: PASS
INT8 MatVec compact evidence: PASS
Portfolio verification: PASS
```

Each case directory contains its baseline, optimized RTL, exact patch,
certificate, report source, checksums and adversarial verifier tests. Large raw
EDA evidence is distributed through case-specific GitHub releases rather than
normal Git history. SHA-1 v1.3.1 remains the historical publication anchor;
the INT8 release will be created only after this portfolio branch is closed and
approved.

## Claim boundary

Both cases use academic VTR PTM 45 nm post-route comparisons. They are not ASIC
signoff, commercial-FPGA characterization, Vivado results, physical-board
measurements, measured power, measured energy or manufactured-silicon evidence.
Percentages are specific to each frozen circuit, target and evaluation contract.

Read [METHODOLOGY.md](METHODOLOGY.md) for the common evidence model and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for provenance and licensing.

## Evaluating a customer design

A pilot starts by freezing one owned design interface, correctness suite,
implementation target, objective and validity limits. Göther Labs can then
produce a bounded before/after result and an agreed evidence package before a
larger engagement.

[Göther Labs](https://www.gotherlabs.com/)
