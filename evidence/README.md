# Evidence index

This directory binds the baseline-versus-accepted result to compact, content-addressed evidence.

- [`formal-proof.json`](formal-proof.json) records the accepted RTL hash, EQY pass-marker hash, formal-driver log hash and complete archive identity.
- `MANIFEST.json` binds every public artifact to its SHA-256 value.
- `SHA256SUMS` provides a conventional checksum list for release auditing.

Raw paired measurements are in [`../results/baseline-certification.json`](../results/baseline-certification.json) and [`../results/accepted-certification.json`](../results/accepted-certification.json). The complete EDA archive is distributed separately because its generated intermediates are unsuitable for normal Git history.

The verifier does not trust precomputed percentages. It recomputes every metric and the composite result from the 64 paired rows:

```bash
make verify
```
