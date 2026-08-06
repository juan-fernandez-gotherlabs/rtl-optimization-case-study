# v1.1.0 release candidate · client-facing evaluated result

This release presents the corrected SHA-1 baseline and the accepted RTL revision under one frozen VTR 45 nm evaluation contract.

## Result

- Composite PPA: **5.98% improvement** (paired 95% CI: 5.69% to 6.27%).
- Critical-path delay: **11.43% improvement** (paired 95% CI: 10.87% to 11.98%).
- Energy per block: **6.14% improvement** (paired 95% CI: 5.77% to 6.52%).
- Total area: statistically neutral.
- Functional, NIST and pinned EQY gates: pass.
- Certification: 64 fixed, paired VPR seeds.

## Prepared release assets

- `executive-summary.pdf`: decision brief in the Göther Labs visual system.
- `technical-report.pdf`: full method, four-line diff, statistics, trade-offs and limitations.
- `accepted-rtl-certification-evidence.tar.gz`: path-sanitized certification evidence.
- `SHA256SUMS`: release checksum list.

The path-sanitized evidence archive is byte-identical to the certified public derivative and is published under the client-facing filename. Its SHA-256 is `413aefb29bbe9bc1d22e847cd0901c24a0bfaa675af111fbd879598a76b2874f`.

This release candidate is not published until the canonical PDFs, manifest and clean-checkout build all pass on the same commit.

## Claims boundary

This is an academic open-FPGA VTR/PTM45 comparison, not ASIC signoff, a commercial FPGA measurement or manufactured silicon. SHA-1 is used only as a legacy benchmark.
