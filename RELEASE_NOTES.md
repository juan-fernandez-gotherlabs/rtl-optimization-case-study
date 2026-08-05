# v1.0.0 - Certified case-study release

This release freezes the independent SHA-1/VTR RTL optimization case study presented in this repository.

## Result

- Composite PPA: **5.98% improvement** (paired 95% CI: 5.69% to 6.27%).
- Critical-path delay: **11.43% improvement** (paired 95% CI: 10.87% to 11.98%).
- Energy per block: **6.14% improvement** (paired 95% CI: 5.77% to 6.52%).
- Total area: statistically neutral.
- Functional, NIST and pinned EQY gates: pass.
- Certification: 64 fixed, paired and search-disjoint VPR seeds.

## Release assets

- `executive-summary.pdf`: two-page decision brief.
- `technical-report.pdf`: full method, four-line diff, statistics, trade-offs and limitations.
- `g15-wt-balanced-xor-public-evidence.tar.gz`: complete path-sanitized certification evidence.
- `SHA256SUMS`: release checksum list.

The public evidence archive SHA-256 is:

```text
413aefb29bbe9bc1d22e847cd0901c24a0bfaa675af111fbd879598a76b2874f
```

Its embedded `PUBLIC_SANITIZATION.json` identifies the certified original archive and maps all 67 modified command records from original to public hashes. No measurement value or EDA output was edited.

## Claims boundary

This is an academic open-FPGA VTR/PTM45 comparison, not ASIC signoff, a commercial FPGA measurement or manufactured silicon. SHA-1 is used only as a legacy benchmark.
