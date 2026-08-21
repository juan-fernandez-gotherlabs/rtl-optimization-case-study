# ML-KEM CBD RTL optimization

Post-quantum cryptographic-IP case in the
[verified RTL portfolio](../../README.md).

## What this module does

The stateful centred-binomial-distribution (`CBD`) sampler converts 1,088 bits
from SHAKE into small positive and negative polynomial coefficients used as
controlled mathematical noise in ML-KEM. This is a real synthesizable block
from the open HOPE-MLKEM implementation, not a complete key-encapsulation
engine.

## What changed

The baseline advances a 1,096-bit state by either 16 or 24 bits according to
the active eta mode. The optimized RTL:

- always moves the physical state in fixed 24-bit chunks;
- records the remaining byte offset in a two-bit phase;
- presents the same logical head to the existing coefficient arithmetic.

This is similar to moving a small read pointer instead of repeatedly moving a
large data structure in two different increments. The interface, reset,
loading, eta modes, stalls, addresses, outputs and cycle timing remain fixed.
See the [exact patch](rtl/changes.patch).

## Result

| Metric | Baseline | Optimized | Paired improvement | 95% interval |
|---|---:|---:|---:|---:|
| Total area | 22,751,867 MWTA | 19,132,428 MWTA | **15.9083%** | 15.5265% to 16.2884% |
| Critical path | 4.0538 ns | 3.7703 ns | **6.9920%** | 5.4724% to 8.4872% |
| Active total power | 64.106 mW | 60.284 mW | **5.9621%** | 4.0336% to 7.8519% |
| Composite PPA | 1.000000 | 0.902662 | **9.7338%** | 9.3331% to 10.1327% |

MWTA is VTR's minimum-width transistor-area unit. Packed CLBs fall from 337 to
270, a 19.8813% reduction. Reciprocal routed delay corresponds to a 7.5177%
increase in the frequency estimate. The composite is the
equal-weight geometric mean of paired area, post-route delay and active-total-
power ratios over 64 fixed pairs. Cross-case percentages are not a
cross-circuit performance ranking.

## Correctness evidence

- Verilator lint and Yosys hierarchy/interface checks;
- a 239-cycle dual-design regression with 239 checks, covering reset, eta 2/3,
  stalls, reload and second-load behaviour;
- complete sequential EQY equivalence using five-step temporal induction after
  the declared two-cycle reset;
- a joined 1,096-bit logical-state refinement view connecting the new physical
  representation to the baseline state;
- 64 prospectively frozen publication pairs, disjoint from all 15 earlier
  search and confirmation seeds;
- raw VTR timing, area and ACE power evidence for baseline and optimized RTL.

Five-step induction is not a five-cycle-only check: it proves the invariant for
arbitrary future cycles after reset. Certification means acceptance under the
published project contract, not accredited or third-party certification.

## Verify

Compact consistency verification requires only Python 3:

```bash
python3 verify.py
```

Expected ending:

```text
ML-KEM CBD compact evidence: PASS
held_out_pairs=64
improvement=9.7338%
Full raw evidence: NOT CHECKED (pass --evidence-archive)
```

For raw-provenance verification, download the
[v2.2.0 evidence asset](https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v2.2.0/mlkem-cbd-vtr45-full-evidence-v1.tar.gz)
and run:

```bash
python3 verify.py --evidence-archive mlkem-cbd-vtr45-full-evidence-v1.tar.gz
```

Full mode audits every archived member and re-extracts all 128 post-route PPA
rows. It does not rerun the EDA tools.

## Source and licensing

The baseline comes from `HWSec-CSIC/hope-mlkem`, pinned to commit
`72a90d80484d45d0bed1e0f9903bd0fb78cceb47`, file `rtl/cbd.v`, under the MIT
License. The baseline differs from that file only by provenance comments.
HOPE-MLKEM and its contributors do not endorse this optimization or report.

## Claim boundary

These are paired academic VTR/PTM 45 nm estimates on a homogeneous LUT6 target
using deterministic ACE probabilistic activity. They are not ASIC signoff,
commercial-FPGA characterization, physical-board measurement, measured power
or energy, or manufactured-silicon evidence. This is not side-channel analysis
or certification of HOPE-MLKEM or a complete ML-KEM implementation.
