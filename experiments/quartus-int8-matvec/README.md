# INT8 MatVec transfer to Quartus Prime Lite

**Result:** the exact frozen RTL optimization improves post-fit timing in
Quartus under both normal DSP inference and a logic-only control. It does not
reduce multiplier count, and the vectorless power estimate is not strong enough
to support a power claim.

Status: complete exploratory transfer run. All four Quartus compilations and
Power Analyzer runs completed successfully. See the [claim boundary](#claim-boundary)
before reusing the figures.

## What this experiment tests

The [published INT8 MatVec case](../../cases/int8-matvec/README.md) performs
sixteen exact signed 8x8 multiplications and four dot-product reductions. Its
optimized RTL replaces early 32-bit widening and chained additions with a
balanced, range-correct tree. The arithmetic, interface and every output bit
remain unchanged.

The original result uses a homogeneous academic LUT6 target. This experiment
keeps the same byte-exact baseline and optimized DUT files and asks whether the
change transfers to Quartus Prime Lite on a commercial MAX 10 FPGA.

Here, `DSP` means the dedicated multiplier hardware inside the FPGA. The DUT is
a compact arithmetic kernel, not a large streaming DSP subsystem.

| Quartus mapping | Baseline RTL | Optimized RTL | Purpose |
| --- | :---: | :---: | --- |
| Normal DSP inference | Run | Run | Commercially realistic transfer result |
| Multipliers forced into logic | Run | Run | Control for whether the result depends on DSP inference |

A common wrapper registers every input and output, giving both RTL variants the
same register-to-register timing boundary. The result snapshot binds the DUT
and wrapper to their SHA-256 hashes.

## Result with normal DSP inference

This is the primary result because it allows Quartus to use the MAX 10 device
normally.

| Metric | Baseline | Optimized | Change |
| --- | ---: | ---: | ---: |
| Estimated Fmax | 98.78 MHz | 110.95 MHz | **+12.32%** |
| Worst setup slack at 200 MHz | -5.124 ns | -4.013 ns | **+1.111 ns** |
| Datapath delay | 10.124 ns | 9.013 ns | **-10.97%** |
| Logic elements | 273 | 269 | **-1.47%** |
| Physical multiplier blocks | 8 | 8 | No change |
| 9-bit multiplier elements | 16 | 16 | No change |

Quartus maps the sixteen signed 8x8 multiplications into sixteen 9-bit
multiplier elements packed into eight physical blocks. The RTL change improves
the accumulation path around those multipliers; it does not remove any of the
multiplications.

## Logic-only control

This deliberately disables dedicated multiplier use. It is not the recommended
implementation; it tests whether the timing result is only an artefact of DSP
mapping.

| Metric | Baseline | Optimized | Change |
| --- | ---: | ---: | ---: |
| Estimated Fmax | 76.55 MHz | 83.87 MHz | **+9.56%** |
| Worst setup slack at 200 MHz | -8.063 ns | -6.923 ns | **+1.140 ns** |
| Datapath delay | 13.063 ns | 11.923 ns | **-8.73%** |
| Logic elements | 1,740 | 1,718 | **-1.26%** |
| Physical multiplier blocks | 0 | 0 | No change |

The timing improvement survives without DSP blocks. Quartus, however, absorbs
most of the area advantage seen on the original VTR target, so this experiment
supports a timing-transfer claim rather than a large area-reduction claim.

## Power estimate

Quartus reported a low-confidence vectorless estimate because no simulation
activity or board thermal model was supplied:

| Mapping | Baseline | Optimized | Direction |
| --- | ---: | ---: | ---: |
| Normal DSP inference | 138.22 mW | 134.77 mW | -2.50% |
| Logic-only control | 126.98 mW | 128.72 mW | +1.37% |

The directions disagree across mappings and the activity model is insufficient.
No general power-improvement claim is made.

## Inspect and verify

Quartus is not required to audit the checked-in result:

```bash
python3 verify.py
```

The verifier checks the exact package manifest, RTL hashes and run contract,
then re-extracts the published metrics from the selected Quartus reports. The
auditable evidence is under
[`evidence/quartus-lite-25.1std-max10`](evidence/quartus-lite-25.1std-max10),
and the combined machine-readable result is
[`results/quartus-lite-25.1std-max10-summary.json`](results/quartus-lite-25.1std-max10-summary.json).

For a fresh Quartus run, prerequisites and the exact commands are in
[`REPRODUCING.md`](REPRODUCING.md).

## Frozen implementation contract

- Tool: Quartus Prime Lite Edition `25.1std.0 Build 1129`.
- Family and device: MAX 10 `10M50DAF484C7G`.
- Clock target: 5.000 ns, or 200 MHz.
- Timing model: slow 1200 mV, 85 C, post-fit.
- Top: `int8_matvec_registered_top`.
- Fitter seed: 1.
- Parallel processors: four.
- Data I/O: virtual pins; physical clock on `PIN_M8`.
- Power: vectorless estimate, explicitly low confidence.

The deliberately aggressive 200 MHz target is not met by either RTL variant.
The optimized implementation is faster, but it is not a timing-closed 200 MHz
design. In normal DSP mode, Quartus absorbs the 160 input registers into
multiplier primitives and reports 128 remaining logic registers; in logic-only
mode it reports all 288 wrapper registers. This is packing, not lost state.

## Claim boundary

This is one fixed-seed implementation comparison on one MAX 10 device and one
Quartus build. It was executed under full x86-64 QEMU emulation on Apple
Silicon. It is not a supported-native-host replay, a multi-seed estimate, a
physical-board measurement, measured power or energy, a cross-vendor ranking,
or evidence for a larger matrix, streaming pipeline or complete DSP subsystem.

The valid claim is narrower: for this exact device, tool build, constraint,
wrapper, seed and mapping mode, the frozen optimized RTL improves reported
post-fit timing relative to the frozen baseline.
