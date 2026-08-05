# Executive summary

## Question

Can an automated optimization process improve a real sequential RTL block without changing its interface, protocol, latency or observable cycle behavior?

## Result

On a corrected SHA-1 core derived from the open Verilog-to-Routing benchmark suite, four local RTL rewrites produced a **5.98% improvement in estimated composite PPA** over a fixed baseline. The result was certified over 64 paired VPR seeds that were not exposed during search.

- Critical-path delay improved by **11.43%** (paired 95% CI: 10.87% to 11.98%).
- Workload energy per compression block improved by **6.14%** (paired 95% CI: 5.77% to 6.52%).
- Total area was **statistically neutral** (estimated 0.03% improvement; CI crosses zero).
- Composite PPA improved by **5.98%** (paired 95% CI: 5.69% to 6.27%).
- Timing, energy and composite score improved in all 64 paired seeds.
- EQY formal equivalence passed; interface and 80-cycle block behavior were preserved.

The active-power median increased by 5.83%. This is not hidden: the implementation uses more instantaneous power but completes the fixed workload fast enough to reduce total energy per block by 6.05% at the medians.

## Method

The candidate generator is not trusted to define success. A separate evaluator freezes the golden RTL, interface, test vectors, timing behavior, toolchain, architecture, activity, seed pools and score policy.

Every proposed `sha.v` is content-addressed and must pass structural checks, cycle regression and conservative unbounded EQY equivalence before any routed PPA work. Five paired seeds provide provisional search feedback. At search closure, at most three unique formal-pass finalists enter the fixed 64-seed certification pool. Acceptance requires a composite one-sided 95% upper confidence bound below the baseline and no primary metric with one-sided evidence of regression.

The process matters as much as the winning patch. The five-seed provisional leader was rejected by certification because its small area regression became statistically visible. A different finalist became the unique champion.

## Engineering interpretation

The four rewrites change expression topology, not the SHA-1 algorithm or microarchitecture. At representative seed 20, VPR reports:

| Post-synthesis / route property | Baseline | Champion |
|---|---:|---:|
| Timing graph levels | 46 | 42 |
| Critical path | 14.9802 ns | 13.4066 ns |
| CLB blocks | 188 | 187 |
| ABC `.names` nodes | 1,643 | 1,652 |

This is not a gate-count story: the champion contains slightly more mapped logic nodes, but its topology packs and routes better on the frozen target.

## What this demonstrates

The case study demonstrates a transferable engineering workflow:

1. Freeze the customer-owned functional and physical contract.
2. Allow automated systems to propose bounded RTL changes.
3. Reject any change that is not formally proven under that contract.
4. Rank cheaply with a small, clearly provisional implementation sample.
5. Certify only a short list with predeclared, independent physical measurements.
6. Deliver a small patch, raw evidence and a reproducible decision.

## What this does not demonstrate

The reported values are from an academic VTR FPGA architecture and PTM45 model. They are not ASIC PPA, commercial-FPGA measurements, silicon data or signoff. They cannot be transferred numerically to another design or process. A commercial pilot would replace the academic evaluator with the customer's qualified libraries, constraints, workloads, tools and signoff policy while retaining the same separation between candidate generation and acceptance.

SHA-1 is used as a familiar legacy compute benchmark, not as a recommended cryptographic primitive.

## Proposed next step

Run a bounded, confidential pilot on one non-critical customer-selected compute block. Freeze its cycle contract and internal PPA flow, accept only reviewable formally equivalent patches, and let the customer's engineers reproduce every claimed improvement before deciding whether to expand the scope.
