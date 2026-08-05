# Evidence index

This directory contains compact identities for the evidence that supports the case study.

- [`formal-proof.json`](formal-proof.json) records the champion RTL hash, EQY pass-marker hash, formal-driver log hash and full archive identity.
- `MANIFEST.json` binds the public artifacts to their SHA-256 values.
- `SHA256SUMS` provides a conventional checksum list for release auditing.

Raw seed measurements are in [`../results/baseline-certification.json`](../results/baseline-certification.json) and [`../results/champion-certification.json`](../results/champion-certification.json). The 70 MB complete champion evidence is distributed as a path-sanitized release asset rather than committed to Git. `formal-proof.json` retains the certified original archive identity; [`../REPRODUCIBILITY.md`](../REPRODUCIBILITY.md) explains the public derivative and its embedded hash mapping.

The compact verifier does not trust precomputed percentages. It recomputes the 64 paired comparisons from those raw rows:

```bash
make verify
```
