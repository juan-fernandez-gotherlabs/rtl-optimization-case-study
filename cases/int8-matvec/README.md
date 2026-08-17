# INT8 4x4 matrix-vector RTL optimization

[Read the technical report](../../INT8-MatVec-Optimization.pdf) or run the
compact verifier with `python3 verify.py` from this directory. The complete
blinded raw archive is a release asset, kept out of Git because it contains all
four 64-pair VTR run sets.

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

Here, certification means acceptance under the published project contract; it
is not accredited certification or an external assurance opinion.

- 151 deterministic signed, extreme, lane and seeded-random simulations passed
  in both primary and separate replay runs for each RTL;
- exhaustive Yosys combinational equivalence covered every 160-bit input
  assignment in all four evidence legs;
- five optimizer-visible VTR placement pairs rank search candidates only;
- 64 disjoint held-out pairs determine certification;
- baseline and accepted records carry an exact deterministic-replay
  attestation; this is not a third-party reproduction;
- the composite one-sided 95% upper confidence bound remains below `1.0`;
- every primary metric passes its non-regression bound and the resource envelope.

The public certificate and archive replace held-out placement-seed identities
with stable pair labels. The compact verifier checks certificate consistency,
RTL identity, the exact patch and all derived statistics. With the raw archive
it additionally verifies every member hash, checks the four functional and
formal pass records, and re-extracts all 256 post-route area, timing and power
rows before matching them to the certificate. It does not rerun the EDA tools.

## Verify

The compact consistency check uses only Python 3:

```bash
python3 verify.py
```

Expected ending:

```text
held_out_pairs=64
composite_score=0.916769683690
improvement=8.3230%
Full raw evidence: NOT CHECKED (pass --evidence-archive)
```

To verify every raw file, download the release asset and supply it explicitly:

```bash
curl -LO https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v2.0.1/int8-matvec-vtr45-full-evidence-v1.tar.gz
python3 verify.py --evidence-archive \
  int8-matvec-vtr45-full-evidence-v1.tar.gz
```

## Public artifacts

- [Download the full raw-evidence archive](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v2.0.1/int8-matvec-vtr45-full-evidence-v1.tar.gz)
- [`rtl/baseline/int8_matvec_4x4.sv`](rtl/baseline/int8_matvec_4x4.sv)
- [`rtl/optimized/int8_matvec_4x4.sv`](rtl/optimized/int8_matvec_4x4.sv)
- [`rtl/changes.patch`](rtl/changes.patch)
- [`certificate.json`](certificate.json)
- [`full-evidence.json`](full-evidence.json)
- [`technical-report.pdf`](technical-report.pdf)

## Claim boundary

These are paired academic VTR PTM 45 nm post-route estimates at 0.9 V and
85 degrees C on a homogeneous LUT6 target without commercial DSP or BRAM
resources. They are not physical FPGA measurements, Vivado results, ASIC or
silicon signoff, board measurements, measured power or measured energy. The raw
archive establishes provenance and metric re-extraction comparable
to SHA-1; it does not turn academic estimates into physical measurements.

The INT8 RTL is copyright 2026 Juan José Fernández and Apache-2.0 licensed. The
optimization implementation and private execution data are intentionally
outside this public evidence package.
