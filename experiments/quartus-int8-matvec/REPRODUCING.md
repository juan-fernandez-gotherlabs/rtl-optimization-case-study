# Reproducing the Quartus INT8 MatVec transfer experiment

The checked-in verifier does not require Quartus. A fresh implementation run
does, because Quartus Prime Lite and MAX 10 device support are proprietary and
are not redistributed by this repository.

## Recommended environment

- supported native x86-64 Linux host;
- Quartus Prime Lite Edition `25.1std.0 Build 1129`;
- MAX 10 device support;
- Python 3.10 or newer;
- approximately 9 GB for the external Quartus installation, plus working space.

The published evidence is pinned to this exact tool build. A later Quartus
release is useful new evidence, but it is a new experiment rather than an exact
reproduction.

## Verify the checked-in evidence without Quartus

From the repository root:

```bash
python3 experiments/quartus-int8-matvec/verify.py
```

The verifier checks the package manifest, exact RTL hashes, all four run
contracts, the reported comparisons, successful compilation markers, and
re-extracts resources, timing and power from the checked-in Quartus reports.

## Run the four implementations

From `experiments/quartus-int8-matvec`:

```bash
make check
make matrix \
  QUARTUS_SH=/opt/altera/quartus/bin/quartus_sh \
  QUARTUS_POW=/opt/altera/quartus/bin/quartus_pow \
  EXECUTION_ENVIRONMENT=native_x86_64
```

The runner executes, in order:

1. baseline with normal DSP inference;
2. optimized RTL with normal DSP inference;
3. baseline with multipliers forced into logic;
4. optimized RTL with multipliers forced into logic.

Override `DEVICE`, `FAMILY` or `PERIOD_NS` only when intentionally creating a
different experiment. Outputs are written to the ignored `output/` directory.

To package only the auditable reports after a reviewed run:

```bash
make evidence
make checksums
make verify
```

Do not commit Quartus databases, incremental databases, caches or programming
files. The evidence packager accepts only the QPF/QSF/SDC, compile and power
logs, selected fit/map/timing/power/flow reports and their compact summaries,
plus the JSON/CSV result summaries.

## Published-run provenance

The checked-in run was executed on 2026-09-17 in a full x86-64 QEMU virtual
machine managed by Colima 0.10.3 on Apple Silicon, with six virtual CPUs and
8 GiB RAM. Docker Desktop's Rosetta path faulted on an x87 instruction in this
Quartus build, so Rosetta was not used for the completed evidence.

This emulated route is recorded for transparency, not recommended as the
reference reproduction platform. Replay on a supported native x86-64 host is
still required before upgrading the result beyond exploratory status.

## Timing boundary

The wrapper registers all 160 DUT input bits and all 128 output bits. Data ports
are virtual pins; only the clock uses a physical MAX 10 pin. Top-level I/O paths
therefore remain intentionally unconstrained, while the `clk` register-to-
register paths under comparison are constrained. The generated image is not a
board-ready design.
