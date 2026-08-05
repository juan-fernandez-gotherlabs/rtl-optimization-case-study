# Reproducibility

The repository separates a fast audit of published evidence from a complete physical rerun. This prevents a cached report from being mistaken for a new measurement and makes the expected cost explicit.

## 1. Offline evidence audit

Requirements: Python 3.11 or newer. No network, Docker or EDA tools are required.

```bash
make verify
```

The verifier:

1. Checks the SHA-256 identities of the corrected baseline and champion RTL.
2. Confirms the 64 baseline and champion seed sets are identical.
3. Recomputes metric and composite paired log ratios.
4. Recomputes two-sided and one-sided Student-t confidence bounds.
5. Reapplies the fixed acceptance rule.
6. Checks the published formal, functional and NIST status references.

Expected composite output:

```text
score=0.940187630028
score_ci95=[0.937274457714, 0.943109856865]
```

## 2. Figure regeneration

```bash
make figures
```

The SVG figures are generated directly from the compact certified JSON, not from screenshots or hand-entered chart values.

The presentation PDFs require the pinned Python dependency and `rsvg-convert`:

```bash
python3 -m pip install -r requirements-report.txt
make report
```

## 3. Pinned measurement image

Requirements:

- Docker Engine with Linux/amd64 emulation.
- At least 2 CPUs and 7 GB available to the container.
- Network access only while cloning sources and building the image.
- Approximately one hour for a cold image build on an Apple Silicon laptop; cached rebuilds are faster.

```bash
./reproduce/build-image.sh
```

The script checks out VTR recursively at commit `95f5c6de9e158371ba7185bf97c07a84153735d6` and builds the exact Dockerfile embedded in the frozen evaluator snapshot. Runtime candidate evaluation disables networking and caps the container at 2 CPUs, 7 GB RAM and 512 processes.

## 4. Candidate search measurement

Five exposed paired seeds provide provisional ranking only:

```bash
./reproduce/run-candidate.sh \
  rtl/champion/sha.v \
  search \
  /absolute/new/results/search \
  champion-search-reproduction
```

The result must report `certified=false` and no acceptance decision.

## 5. Candidate certification

Certification reruns correctness, NIST Short/Long and 64 fixed, disjoint PPA seeds:

```bash
./reproduce/run-candidate.sh \
  rtl/champion/sha.v \
  certification \
  /absolute/new/results/certification \
  champion-certification-reproduction
```

The certified champion archive completed in 1,091.82 seconds on the qualified Apple Silicon MacBook using two workers. Host contention can change wall time but must not change the parsed deterministic inputs, seed set or decision contract.

## 6. Full evidence archive

The repository intentionally avoids committing the 70 MB compressed champion evidence archive and thousands of generated intermediate files. The certified original archive is retained under this identity:

```text
rank-2-g15-wt-balanced-xor-743e6c9ffcca-evidence.tar.gz
```

Expected SHA-256:

```text
9983b1fef4509b9a9a592af8134be39eaa7545e5269ac7332206e86db7cce3e8
```

The original command records include an absolute host worktree path. The public release therefore distributes a deterministic derivative named `g15-wt-balanced-xor-public-evidence.tar.gz`. It changes only that path prefix to `<SOURCE_WORKTREE>` and adds `PUBLIC_SANITIZATION.json`, which maps original member hashes to public member hashes. The certified original hash above remains the authority for the measurement; the release manifest records the public derivative's separate hash.

Public release SHA-256:

```text
413aefb29bbe9bc1d22e847cd0901c24a0bfaa675af111fbd879598a76b2874f
```

Verify either artifact with:

```bash
shasum -a 256 <archive>
```

## 7. Clean-room expectation

A new measurement must use a clean checkout, the pinned image and a new evidence directory. Failed or interrupted runs remain failures; do not edit their JSON into success. Certification is fixed at 64 seeds and must not be extended after inspecting a result.

See [`LIMITATIONS.md`](LIMITATIONS.md) before interpreting any reproduced value outside this exact VTR contract.
