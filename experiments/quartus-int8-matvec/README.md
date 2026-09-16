# Quartus Lite INT8 MatVec transfer experiment

Status: complete exploratory transfer run. All four Quartus compilations and
Power Analyzer runs completed successfully on 2026-09-16; the limitations
below remain part of the result.

## Question

The published INT8 MatVec case improves a homogeneous LUT-only VTR target. This
experiment asks whether the exact same RTL change transfers to an industrial
Altera flow when Quartus may infer dedicated DSP blocks.

The matrix separates two architectural conditions:

| Mapping | Meaning |
| --- | --- |
| `dsp_auto` | Normal Quartus DSP inference. |
| `lut_only` | DSP recognition disabled and DSP balancing forced to logic elements. |

Both frozen RTL variants run in both modes. A common wrapper registers every
input and output so the primary timing comparison is register-to-register.

## Frozen defaults

- Quartus Prime Lite: 25.1 Standard or a compatible later release, recorded per run.
- Family: `MAX 10`.
- Device: `10M50DAF484C7G` (the DE10-Lite MAX 10 device).
- Clock period: `5.000 ns` (200 MHz target).
- Top: `int8_matvec_registered_top`.
- Fitter seed: `1`.
- Threads: four.
- Power: Quartus vectorless estimate when the Power Analyzer completes.

Quartus Prime Lite is proprietary but zero-cost and requires no license file.
The selected device is supported by the Lite edition. The tool and MAX 10 device
support must be installed separately from this repository.

## Result

Tool: Quartus Prime Lite 25.1std.0 build 1129. Device: MAX 10
`10M50DAF484C7G`, fitter seed 1, slow 1200 mV/85 C post-fit timing model.
The checked-in machine-readable snapshot is
[`results/quartus-lite-25.1std-max10-summary.json`](results/quartus-lite-25.1std-max10-summary.json).

| Mapping | Variant | Logic elements | Registers | Physical multiplier blocks | 9-bit multiplier elements | WNS | Fmax | Vectorless total power |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dsp_auto` | Baseline | 273 | 128 | 8 | 16 | -5.124 ns | 98.78 MHz | 138.22 mW |
| `dsp_auto` | Optimized | 269 | 128 | 8 | 16 | -4.013 ns | 110.95 MHz | 134.77 mW |
| `lut_only` | Baseline | 1,740 | 288 | 0 | 0 | -8.063 ns | 76.55 MHz | 126.98 mW |
| `lut_only` | Optimized | 1,718 | 288 | 0 | 0 | -6.923 ns | 83.87 MHz | 128.72 mW |

Within `dsp_auto`, the optimized RTL improves estimated Fmax by **12.32%**,
improves WNS by **1.111 ns**, reduces logic elements by **1.47%**, and leaves
multiplier use unchanged. Within `lut_only`, it improves Fmax by **9.56%**,
improves WNS by **1.140 ns**, and reduces logic elements by **1.26%**. The
timing benefit therefore survives both normal DSP inference and a logic-only
control; this run does not support a claim of reduced DSP count.

Neither implementation meets the deliberately aggressive 200 MHz target. The
top-level data I/O paths are intentionally unconstrained because the comparison
boundary is the common input-register-to-output-register path; the clock and
all synchronous transfers are constrained. DSP input registers are packed into
the multiplier primitives, so Quartus reports 128 top-level logic registers in
`dsp_auto` and 288 in `lut_only`; this is not lost architectural state.

Power is a low-confidence vectorless estimate with no simulation activity or
board thermal model. It is suitable only as a directional diagnostic within a
fixed mapping mode. In particular, the `lut_only` optimized estimate is 1.37%
higher, so no general power-improvement claim is made.

## Apple Silicon bootstrap

The Docker runner uses an Ubuntu 22.04 `linux/amd64` userspace because Quartus is
an x86-64 Linux application. Docker Desktop's Rosetta path faulted on an x87
instruction in this tool release. The completed run therefore used a full
x86-64 QEMU VM through Colima 0.10.3 (six virtual CPUs and 8 GiB RAM), not
Rosetta. This is emulated and unsupported on Apple Silicon; results must remain
labelled exploratory until reproduced on a supported native x86-64 host.

```bash
make docker-image

QUARTUS_INSTALL_DIR=/absolute/path/to/altera \
make docker-matrix
```

The installation directory stays outside the repository and is mounted
read-only. No Altera software is redistributed.

## Run and outputs

```bash
make check
make matrix
```

Each run keeps its generated QPF/QSF/SDC, complete Quartus reports and logs under
the ignored `output/` directory. A complete matrix produces `summary.json` and
`summary.csv` with logic-element, register, DSP, timing and available vectorless
power data.

Interpret `dsp_auto` and `lut_only` independently. These MAX 10 results are not
numerically comparable with AMD Vivado results because device architectures and
resource definitions differ. The useful transfer question is whether the
optimized RTL improves the baseline within each fixed Quartus mapping mode.
