# Restoring SERV research for new experiments

## Public evidence package

A fresh clone contains both frozen 18-file RTL trees, their exact patch,
recorded source/mapped correctness evidence, every final-pair report, the
14-page PDF, report sources and consistency verifiers:

```bash
git clone https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study.git
cd rtl-optimization-case-study
python3 verify.py
```

This verifies the saved evidence. New RTL experiments additionally need the
measurement runtime and research drivers; those are preserved in the private
[maintainer recovery checkpoint](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-serv-resume).
Access to that repository is required for the recovery commands below. The
public package contains the study results; the private checkpoint contains
the complete research workspace and optimization infrastructure.

## Maintainer recovery

The private release `checkpoint-20261013` preserves the exact Docker image,
all candidate workspaces, private drivers, exploration evidence and pending
experiment records. Its manifest identifies every archive part by SHA-256.
No original local study directory is required.

```bash
gh repo clone juan-fernandez-gotherlabs/rtl-optimization-serv-resume
cd rtl-optimization-serv-resume
python3 restore.py --destination /absolute/path/to/recovered --core --runtime
```

Use `--study --runtime` for the full history; this restores the compact core
and then overlays the remaining study. The ordinary full extraction is about
40 GiB because the original local filesystem compressed many files. Allow at
least 50 GiB for full extraction and the Docker runtime, plus new experiment
output. Compact recovery needs substantially less space: about 1 GiB for the
core, the 7.15 GiB uncompressed image, download/load overhead and output space.

Requires Python 3.12+, authenticated GitHub CLI and Docker with `linux/amd64`
support. The loader verifies each downloaded part and the immutable image ID
`sha256:25ac0b7034aa4e2e537020980ddddf974f5d6197c306e88ec27dfc6f2255598e`.
Dependency/build recipes and third-party licenses are preserved alongside the
original tools. The runtime can be restored without rebuilding from current
package mirrors.

## Recovery check and continuing work

The checkpoint's `smoke_replay.py` runs fresh source equivalence and a new
baseline/candidate implementation pair. It compares all three metrics with
the frozen public seed and requires every executable BLIF statement to match
before reusing the saved complete mapped proof. Its
`recovery-validation.json` records the checks performed before local cleanup.

After cloning the public repository into `public-study`, run:

```bash
python3 smoke_replay.py --study /absolute/path/to/recovered/serv-1.4.0-study-20261005 \
  --public-repo /absolute/path/to/public-study --seed 6001
```

Continue from the recovered selected RTL or any saved candidate workspace.
Use the recovered `domain` generators, correctness checks and measurement
drivers to register new variants. A changed source or measured executable
netlist requires its own correctness evidence; the frozen proof cannot be
reused across a changed implementation. Preserve the original baseline and
freeze a new sampling plan before selecting and confirming new candidates.

These recovery checks establish that new experiments can be run. They do not
change SERV's published 64-pair result, its timing regression or its status as
a paused research record.
