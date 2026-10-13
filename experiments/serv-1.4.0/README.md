# SERV 1.4.0 RTL optimization research record

**Status: paused research. The best saved result is a development result from
12 paired implementations. Held-out certification and the final 64 pairs
remain unexecuted for this candidate.**

This record preserves the best implementation and the evidence available when
the study stopped on 12 October 2026. It belongs to the repository's research
experiments. The portfolio still has three published, accepted cases.

## What the design does

SERV is a bit-serial 32-bit RISC-V processor. The measured configuration uses
`serv_synth_wrapper`, serial width `W=1`, CSR support, minimal reset and a
two-bit external register-file SRAM interface. Instruction and data buses,
register-file addresses, data, handshakes and cycle timing form the comparison
boundary. The complete system's external SRAM is outside the mapped wrapper.

## What changed

The frozen candidate combines a three-bit representation of the high
register-file phase with earlier decoder, buffer, PC and control rewrites.
The wrapper selects `RF_HIGH_PHASE_FORM=1`, `DECODER_CAPTURE_USAGE_FORM=3`,
`PC_WORD_ENABLE_FORM=3`, `DATA_WORD_ENABLE_FORM=3` and `BUFFER_CONTROL_FORM=3`.
Its source also contains inactive parameter alternatives. The saved result
applies to the selected configuration, not every parameter combination.

The [exact patch](rtl/changes.patch) changes ten of the eighteen files.
Both [baseline](rtl/baseline/) and [optimized RTL](rtl/optimized/) are preserved
byte for byte. Source length rises from 3,562 to 4,137 total lines; this includes
comments, blank lines and inactive alternatives and is not an area measure.

The result measures the complete combined candidate. It does not assign an
independent percentage contribution to each transformation.

## Best saved development result

| Metric | Baseline mean | Optimized mean | Paired geometric change |
| --- | ---: | ---: | ---: |
| Total area | 2,743,003.5 MWTA | 2,579,889.0 MWTA | **5.9467% lower** |
| Critical path | 4.275710 ns | 4.278436 ns | **0.0721% higher** |
| Active total power | 3.541333 mW | 3.386167 mW | **4.3802% lower** |
| Packed CLBs | 46 | 43 | 6.5217% fewer |
| Mapped flip-flops | 181 | 181 | Unchanged |
| Composite PPA | 1.000000 | 0.965484 | **3.4516% lower** |

Arithmetic means and paired geometric changes are different summaries; the
percentages are calculated from each pair's ratio, not by dividing the two
displayed arithmetic means. The composite equally weights log area, delay and
power ratios over development seeds `5001..5012`.

MWTA is VTR's minimum-width transistor-area unit, not square millimetres.
These are academic VTR/PTM 45 nm estimates on a homogeneous LUT6 target with
ACE probabilistic activity at 0.9 V and 85 C. They are not measured silicon,
board power, workload energy, ASIC signoff or commercial-FPGA characterization.
The small timing increase is reported explicitly; no claim of improvement in
every primary metric is made.

### Size and capacity

Both configurations require 32 GPR words and four RAM-backed CSR words,
32 bits per word: **1,152 bits / 144 bytes**, represented as **576 logical
two-bit rows**. The external SRAM capacity and interface are unchanged and its
area is excluded from the wrapper measurements. The 181 flip-flops describe
the mapped wrapper state and must not be confused with the external register
storage capacity.

## Correctness and evidence

The package contains saved evidence for:

- source lint at serial widths 1 and 4, plus structural warning checks;
- sequential source equivalence, with 357 proved and zero unproved obligations
  for each recorded source gate;
- RTL-to-measured-netlist equivalence for each design: 126 primary output bits
  plus all 181 state bits, **307 proved / zero unproved**, preserving undefined
  initialization rather than forcing it in the proof;
- two recorded 4,096-cycle post-mapping simulations per design, comparing
  defined RTL output bits; undefined RTL bits are skipped in these simulations;
- all 24 saved timing/area reports, power reports, flow logs and measured BLIF
  netlists for the twelve pairs.

The proofs use Yosys sequential equivalence and induction. They are equivalence
checks for this RTL boundary, not a certification of full RISC-V ISA compliance.
The public verifier checks recorded evidence, hashes, proof closure markers,
netlist identities and recomputed metrics. It does not run the EDA tools or
independently regenerate the proofs. The full private exploration archive,
optimizer and execution infrastructure are outside this package.

The private host path prefix in the four simulation logs is replaced with
`<private-study-root>`. Their [projection provenance](evidence/simulation/provenance.json)
records original and public hashes; every other byte is preserved.

## Search history and the stopping point

The closed revision-2 exploration registered **2,812 candidates**: 2,621 had
valid PPA measurements and 191 were excluded without PPA. These counts cover
exploratory candidates; they are not 2,621 independent certification trials.
The selected RF-phase cohort contained 36 measured candidates before the best
candidate received its complete twelve-pair development comparison.

Earlier measurements used a synthesis flow subsequently repaired to lower
subtractions through standard Yosys mapping before Parmys. The repair was
applied equally to baseline and candidates. Historical apparent improvements,
including the rejected 11.10461% result, the unrecertified 4.4778% result and two
older exploratory 64-pair replicas, are not evidence for the current candidate.

Later combinations were explored from the current leader and other promising
parents. None of the completed, validated combinations superseded this leader.
The last family prepared nine branch/trap candidates: 36 full elaborations and
three native banks passed, six native banks remained pending, and no PPA
measurement was completed. Those candidates have no reported improvement.

The study was paused by the user after repeated storage stops. The best RTL,
measurements and pending checkpoint are preserved. The optimization objective
remains unmet.

## Acceptance remains pending

The SERV contract reserved a held-out twelve-pair certification sample and a
final 64-pair sample. Both remain unused for the current leader. Its original
editorial target requires both a point score and the one-sided 95% upper score
bound strictly below 0.90, with the declared primary-metric and multiplicity
rules. The 3.4516% development improvement does not meet that target.

The saved development confidence bound is descriptive after selection. It is
not used as a confirmatory acceptance test. This research record does not
change the contract or promote the candidate to an accepted portfolio case.

## Verify and read the report

From the repository root:

```bash
python3 experiments/serv-1.4.0/verify.py
python3 verify.py
```

Expected SERV output includes:

```text
SERV 1.4.0 saved research evidence: PASS
development_pairs=12; improvement=3.4516%
held_out_certification_pairs=0; final_pairs=0; publication_accepted=False
```

See the [technical report](technical-report.pdf),
[frozen public contract projection](contract.json),
[paired measurements](results/measurements.json),
[best result](results/development.json) and
[original pause record](results/pause-record.json).

## Source and licensing

The eighteen baseline files match SERV tag `1.4.0`, commit
[`7d9cde4e6ca4f4c84d7512a752a4c187537dd373`](https://github.com/olofk/serv/tree/7d9cde4e6ca4f4c84d7512a752a4c187537dd373/rtl).
The [provenance record](provenance.json) lists their original Git blob and
SHA-256 identities. Baseline and derived RTL retain their ISC source headers;
the upstream [ISC License](LICENSE) is included. SERV, its authors and the
tool providers do not endorse this study.

The included synthesis template derives from VTR scripts. The pinned upstream
[VTR license](VTR-LICENSE.md) is included for that material.
