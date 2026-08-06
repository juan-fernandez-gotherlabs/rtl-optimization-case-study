# Executive summary

## Evaluated result

Four local, cycle-equivalent RTL rewrites reduce the **estimated composite PPA score by 5.98%** on a corrected SHA-1 core derived from the open Verilog-to-Routing benchmark suite.

- Critical-path delay improves by **11.43%** (paired 95% CI: 10.87% to 11.98%).
- Workload energy per compression block improves by **6.14%** (paired 95% CI: 5.77% to 6.52%).
- Total area is **statistically neutral** (estimated 0.03% improvement; the interval crosses zero).
- Composite PPA improves by **5.98%** (paired 95% CI: 5.69% to 6.27%).
- Timing, energy and composite score improve in all 64 paired implementations.
- EQY formal equivalence passes; the interface and 80-cycle block behavior are preserved.

The active-power median increases by 5.83%. This trade-off remains visible: the implementation uses more instantaneous power but completes the fixed workload fast enough to reduce total modeled energy per block.

## What changed

The accepted RTL changes four continuous assignments:

1. SHA-1 choose logic is rewritten in product-of-sums form.
2. SHA-1 majority logic is factored into a different Boolean topology.
3. The four-input message-schedule XOR is explicitly balanced.
4. The 32-bit round accumulator is reassociated into partial sums.

No register, port, state transition, command, output, latency or throughput statement changes. The exact patch is four removed assignments and four added assignments.

## Verification and measurement

The evaluator freezes the golden RTL, interface, test vectors, temporal behavior, toolchain, FPGA architecture, activity traces, 64 implementation seeds and acceptance policy.

The accepted `sha.v` is content-addressed and passes structural checks, cycle regression, NIST SHA-1 validation and conservative EQY sequential equivalence before routed PPA is evaluated. Baseline and accepted RTL then use the same 64 VPR seeds, allowing paired statistical comparison of area, critical-path delay and energy per block.

At representative seed 20:

| Post-synthesis / route property | Baseline | Accepted RTL |
|---|---:|---:|
| Timing graph levels | 46 | 42 |
| Critical path | 14.9802 ns | 13.4066 ns |
| CLB blocks | 188 | 187 |
| ABC `.names` nodes | 1,643 | 1,652 |

The result is not explained by a universal reduction in mapped node count. The changed topology packs and routes more effectively on the frozen target.

## Claims boundary

The reported values come from an academic VTR FPGA architecture and PTM45 power model. They are not ASIC PPA, commercial-FPGA measurements, silicon data or signoff and cannot be transferred numerically to another design or process. SHA-1 is used as a legacy compute benchmark, not as a recommended cryptographic primitive.

## Customer-pilot path

A confidential customer pilot would replace the academic proxy with the customer's RTL, formal strategy, libraries, constraints, workloads, tools and acceptance policy. The deliverable remains the same: a small reviewable patch, formal proof, reproducible measurements, explicit trade-offs and a bounded engineering claim.
