# Module sizes and orders of magnitude

This comparison covers the three accepted VTR cases and the paused SERV 1.4.0
study. All measurements below use each case's frozen 64-pair sample.

**SERV is the step from a specialized block to an instruction-executing CPU.**
Its serial datapath keeps the measured hardware small. The portfolio therefore
expands in architectural integration and verification scope; the measured
circuit becomes smaller than the previous blocks.

## 1. Source size

Each arrow is baseline → optimized. Code lines are nonblank lines after
removing `//` and `/* ... */` comments; declarations and preprocessor directives
count. Total lines include blank lines and comments. Bytes are exact file sizes
for `.v` and `.sv` files in the bundled RTL directory (1 KiB = 1,024 bytes).

| Module | Files / module declarations | Code lines | Total lines | Bytes | KiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| [SHA-1](cases/sha1/rtl/baseline) | 1 / 1 → 1 / 1 | 1,908 → 1,910 | 2,178 → 2,179 | 38,302 → 38,306 | 37.40 → 37.41 |
| [INT8 MatVec](cases/int8-matvec/rtl/baseline) | 1 / 1 → 1 / 1 | 73 → 70 | 80 → 78 | 2,498 → 2,471 | 2.44 → 2.41 |
| [ML-KEM CBD](cases/mlkem-cbd/rtl/baseline) | 1 / 1 → 1 / 1 | 95 → 114 | 110 → 134 | 3,983 → 4,865 | 3.89 → 4.75 |
| [SERV 1.4.0](experiments/serv-1.4.0/rtl/baseline) | 18 / 18 → 18 / 18 | 2,584 → 3,047 | 3,562 → 4,137 | 108,220 → 144,460 | 105.68 → 141.07 |

Source size describes the material included in the study. It does not count
gates, instantiated hardware, memory capacity or execution throughput. SERV's
18-file tree includes RAM, debug, alignment and other optional modules outside
the selected synthesis hierarchy. The optimized tree also retains inactive
parameter alternatives; its additional source lines do not enlarge the frozen
implemented configuration.

## 2. Implemented resource size

CLB counts are constant across all 64 implementations of each source. Area is
the geometric mean of **total area = reported logic area + reported routing area**
from the saved per-pair rows. MWTA means minimum-width transistor area, an
academic normalized unit; these values cannot be read as mm² or ASIC gate counts.

| Module | CLBs | Mapped registers / FF | Total area (MWTA) | Area (10⁶ MWTA) |
| --- | ---: | ---: | ---: | ---: |
| SHA-1 | 188 → 182 | 892 → 892 | 16,626,180 → 16,601,333 | 16.626 → 16.601 |
| INT8 MatVec | 368 → 304 | 72 → 72 | 33,892,339 → 28,607,064 | 33.892 → 28.607 |
| ML-KEM CBD | 337 → 270 | Not recorded in compact certificate | 22,751,867 → 19,132,428 | 22.752 → 19.132 |
| SERV 1.4.0 | 46 → 43 | 181 → 181 | 2,743,359 → 2,581,543 | 2.743 → 2.582 |

- **SHA-1:** the 892 mapped registers include the core's implemented state.
- **INT8 MatVec:** the DUT has no sequential state. The 72 mapped registers
  belong to the fixed output-register measurement wrapper after synthesis.
  All 16 signed multiplications map into LUT fabric; the contract reports zero
  dedicated multiplier blocks. The vector and matrix are input signals, not RAM.
- **ML-KEM CBD:** the compact certificate records CLBs and area, without a
  mapped FF count. RTL declares 1,113 sequential bits in the baseline and 1,115
  in the candidate: 1,096 data bits, two 8-bit counters, one end flag, plus the
  candidate's 2-bit phase. These are declared state sizes, not a claimed mapped
  FF count. The candidate's `reg_shake` is a combinational view of `shake_chunks`,
  so it does not add another 1,096-bit storage array.
- **SERV:** the 181 mapped FF include the selected CPU and register-file
  interface. External register RAM, instruction memory and data memory are
  outside the wrapper and the PPA totals.

The four contracts use the academic homogeneous LUT6/PTM 45 nm target. Each
wrapper, lowering contract and workload remains specific to its case. Resource
figures describe circuit scale within those boundaries. Power models and work
per operation differ, so the comparison does not rank cross-module throughput
or energy efficiency. The SHA-1 report uses medians in its executive table;
this comparison consistently recomputes geometric means for all four cases.

## 3. Workload, state and capacity

| Module | Data dimensions and interface | Main logical state / capacity | Storage boundary |
| --- | --- | --- | --- |
| [SHA-1](cases/sha1/rtl/baseline/sha.v) | 80 compression rounds; 512-bit (64 B) input block; 160-bit (20 B) digest; 32-bit command data input/output | 16 × 32-bit schedule words (15 `W` registers plus `Wt`), 5 × 32-bit working words, 5 × 32-bit hash words: 832 main data-state bits (104 B); control and output registers are additional | Registers inside the core; no mapped memory blocks |
| [INT8 MatVec](cases/int8-matvec/rtl/baseline/int8_matvec_4x4.sv) | 4 × 4 signed INT8 matrix plus 4-element INT8 vector: 160 input bits (20 B); four signed 32-bit outputs: 128 bits (16 B) | 16 exact parallel multiplications and 4 dot products; zero stored DUT state | Inputs are supplied externally; output FF belong to the measurement wrapper |
| [ML-KEM CBD](cases/mlkem-cbd/rtl/baseline/cbd.v) | 1,088-bit (136 B) SHAKE input; four 12-bit coefficients on two 24-bit outputs; two 8-bit destination addresses; η = 2 or 3 | 1,096-bit (137 B) sampler state, including 8 carry bits; candidate retains that logical capacity and adds 2 phase bits to its representation | State is internal registers; destination coefficient RAM is external |
| [SERV 1.4.0](experiments/serv-1.4.0/rtl/baseline/serv_synth_wrapper.v) | 32-bit instruction set; 1-bit serial datapath; 32-bit instruction/data buses; 2-bit RF data interface and 10-bit RF addresses | Default RF allocation: (32 GPR slots + 4 CSR slots) × 32 = 1,152 bits (144 B), including the x0 slot; 576 rows × 2 bits | RF storage is external to the measured wrapper; instruction/data memory capacity is unspecified |

These capacities remain unchanged by the transformations. The RF's 10-bit
address ports can encode 1,024 addresses, but its configured storage depth is
576 rows; address width is not allocated capacity. SERV's x0 reads return zero.
The four RAM-backed CSR slots are `mtvec`, `mscratch`, `mepc` and `mtval`.
See [RF storage](experiments/serv-1.4.0/rtl/baseline/serv_rf_ram.v) and
[RF interface](experiments/serv-1.4.0/rtl/baseline/serv_rf_if.v). The 144 B
allocation is an architectural storage requirement, not part of the reported
181 FF and not a measured full CPU-with-RAM area.

## 4. Relative scale and orders of magnitude

The following ratios use **baselines only**, with SERV = 1.00. They compare
source and physical resources separately.

| Module | Code lines / SERV | CLBs / SERV | Area / SERV | Baseline resource scale |
| --- | ---: | ---: | ---: | --- |
| SHA-1 | 0.74× | 4.09× | 6.06× | 1.88e+02 CLBs; 1.66e+07 MWTA |
| INT8 MatVec | 0.03× | 8.00× | 12.35× | 3.68e+02 CLBs; 3.39e+07 MWTA |
| ML-KEM CBD | 0.04× | 7.33× | 8.29× | 3.37e+02 CLBs; 2.28e+07 MWTA |
| SERV 1.4.0 | 1.00× | 1.00× | 1.00× | 4.60e+01 CLBs; 2.74e+06 MWTA |

- SERV's baseline source has **1.35×** the code lines of SHA-1,
  **35.40×** INT8 MatVec and **27.20×** ML-KEM CBD.
- Baseline source lengths span roughly 10²–10³ code lines (INT8 has 73);
  implemented CLBs span tens for SERV and hundreds for the other modules.
- SERV's area is about 2.74 × 10⁶ MWTA; the others span 1.66 × 10⁷ to
  3.39 × 10⁷ MWTA. This is approximately one order of magnitude in physical
  area, with actual factors between 6.06 and 12.35 under the measured contracts.
- The architectural step is a CPU with instruction decode, ALU, PC, CSR/control,
  memory buses and RF protocol. The physical scope is a compact serial core
  with external storage excluded; source breadth and silicon size describe
  different aspects of the study.

## 5. Acceptance status

SHA-1, INT8 MatVec and ML-KEM CBD are the three accepted cases. SERV remains a
paused research record: its 64 pairs show a **3.3474% lower composite PPA
estimate**, with **5.8985% lower area**, **5.8835% lower estimated power** and
**1.9478% higher critical-path delay**. The timing regression rejects acceptance;
the 10% objective was not reached and the separate 12-pair certification was
not run. File naming and inclusion in this size comparison do not change that
status. See the [SERV report](RTL-Study-SERV-1.4.0.pdf).

## 6. Sources and reproduction

Tables are generated by [generate_module_sizes.py](tools/generate_module_sizes.py).
It counts the bundled source files, reads every frozen per-pair resource row,
checks that each sample contains 64 pairs and recomputes geometric mean area.
Logical capacities above are derived from the linked RTL declarations and
selected wrapper parameters. Missing mapped counts remain explicitly missing.

| Paired evidence | SHA-256 |
| --- | --- |
| [SHA-1](cases/sha1/results/certification.json) | `67bef904e9ba443fbd6b2a9bde8b87b5001b37ecefbff2182b2dcd50d04082f0` |
| [INT8 MatVec](cases/int8-matvec/certificate.json) | `e77ed39c79559af8cbbd2efeaf4fb67045740684ac4fc35699213c3cc1858906` |
| [ML-KEM CBD](cases/mlkem-cbd/certificate.json) | `3d8b6120db2957da6c4d3cd4569e73df180ba07d5c624c9ae4bc1f4d2d37406d` |
| [SERV 1.4.0](experiments/serv-1.4.0/results/confirmation64.json) | `2a39a8c018d80203413dc669316c185fc12a2e085e22f89f001a285d565999b4` |

```bash
python3 tools/generate_module_sizes.py          # update this page and README tables
python3 tools/generate_module_sizes.py --check  # verify that tables are current
python3 verify.py                             # audit all compact packages and checksums
```

Regeneration and verification use Python's standard library and the saved
artifacts. They do not launch EDA or optimization jobs.
