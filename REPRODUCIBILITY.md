# Reproducibility

The repository separates a fast audit of the published baseline-versus-accepted evidence from a complete physical rerun. A cached report is never presented as a new measurement.

## 1. Offline evidence audit

Requirements: Python 3.11 or newer. No network, Docker or EDA tools are required.

```bash
make verify
```

The verifier:

1. Checks the SHA-256 identities of the corrected baseline and accepted RTL.
2. Confirms that both records contain the same 64 implementation seeds.
3. Recomputes metric and composite paired log ratios.
4. Recomputes two-sided and one-sided Student-t confidence bounds.
5. Reapplies the published acceptance conditions.
6. Checks the formal, functional and NIST evidence references.

Expected composite output:

```text
score=0.940187630028
score_ci95=[0.937274457714, 0.943109856865]
```

## 2. Figure and report regeneration

Linux report requirements:

- Python 3.11 or newer and `requirements-report.txt`;
- `latexmk`, XeLaTeX, `texlive-latex-extra`, `texlive-fonts-recommended` and
  `texlive-science` (for `siunitx`);
- the open TeX Gyre fonts;
- Poppler-compatible PDF inspection tools.

```bash
make figures
make equations  # only after editing report/equations/*.tex
python3 -m pip install -r requirements-report.txt
make report
```

Figures are generated directly from the compact 64-seed records. Equations are generated as vector SVG paths from checked-in standalone LaTeX sources and require `pdflatex` plus `pdftocairo` only when regenerated. The canonical technical PDF is compiled from `report/latex/technical-report.tex`; its tables and plots are generated from the certified JSON records. The executive PDF is generated with ReportLab. Neither artifact uses screenshots or manually entered chart values.

The Makefile fixes `SOURCE_DATE_EPOCH` to the evidence date and uses TeX Gyre Heros/Cursor by file name so compilation does not depend on host-installed proprietary fonts.

## 3. Pinned measurement image

Requirements:

- Docker Engine with Linux/amd64 emulation.
- At least 2 CPUs and 7 GB available to the container.
- Network access only while cloning sources and building the image.
- Approximately one hour for a cold image build on an Apple Silicon laptop; cached rebuilds are faster.

```bash
./reproduce/build-image.sh
```

The script checks out VTR recursively at commit `95f5c6de9e158371ba7185bf97c07a84153735d6` and builds the embedded Linux/amd64 evaluator image. Runtime evaluation disables networking and caps the container at 2 CPUs, 7 GB RAM and 512 processes.

## 4. Accepted RTL certification

Certification repeats structural, functional, NIST, formal, route and power stages and evaluates the fixed 64-seed pool:

```bash
./reproduce/run-candidate.sh \
  rtl/accepted/sha.v \
  certification \
  /absolute/new/results/certification \
  accepted-rtl-reproduction
```

The certified run completed in 1,091.82 seconds on the qualified Apple Silicon laptop using two workers. Host contention can change wall time but must not change source hashes, seeds, parsed measurements or the decision contract.

## 5. Complete evidence identity

The full certification archive is not committed because it contains approximately 70 MB of compressed EDA outputs and thousands of intermediate files. The measurement authority is retained by SHA-256:

```text
9983b1fef4509b9a9a592af8134be39eaa7545e5269ac7332206e86db7cce3e8
```

The client-facing, path-sanitized derivative is named:

```text
accepted-rtl-certification-evidence.tar.gz
```

It preserves every measurement and EDA output, replaces only the local source-worktree prefix and includes `PUBLIC_SANITIZATION.json` mapping modified command records to their original hashes. The byte-identical public derivative is 73,705,071 bytes and has SHA-256:

```text
413aefb29bbe9bc1d22e847cd0901c24a0bfaa675af111fbd879598a76b2874f
```

Changing the release filename does not change this content hash.

After obtaining that archive, assemble (but do not publish) the complete
release directory with:

```bash
make release-package EVIDENCE_ARCHIVE=/absolute/path/to/accepted-rtl-certification-evidence.tar.gz
```

The command rejects any archive whose byte count or SHA-256 differs from the
frozen public derivative, then writes the two canonical PDFs, the archive and
their `SHA256SUMS` under `output/release-v1.1.0/`.

## 6. Clean-room expectation

A new measurement starts from a clean checkout, builds or retrieves the pinned image, writes to a new evidence directory and uses the fixed 64-seed certification pool. Failed or interrupted runs remain failures; generated JSON is never edited into success.

See [`LIMITATIONS.md`](LIMITATIONS.md) before interpreting any reproduced value outside this exact VTR contract.
