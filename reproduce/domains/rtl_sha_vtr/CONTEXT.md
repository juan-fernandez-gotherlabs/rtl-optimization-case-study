# Candidate guidance: SHA-1 RTL 45 nm

Edit only `domains/rtl_sha_vtr/benchmarks/sha.v`, preserving the exact `sha1`
interface and cycle behavior. This includes reset, command/status timing,
latency, read order, throughput, `text_o` and `cmd_o` on every cycle.

Correctness is not a sampled objective: EQY equivalence is a hard gate before
any proposal is considered valid, while certification also reruns the
official NIST Short/Long regression. A non-certifying triage may rank proposals
after freezing the RTL and passing EQY; its five-seed score is only a ranking
signal and must not be reported as accepted improvement. The pilot is deliberately structure-preserving:
candidates must remain provable by the pinned EQY cut-point flow. Arbitrary
state recoding, retiming and replacement microarchitectures are outside scope.
Do not add testbench-specific behavior, conditional compilation, system tasks,
delays, `initial`/`final`, DPI, external includes, force/release or
synthesis-exclusion directives.

## Local submission feedback

After a focused edit, you may obtain one non-certifying local score with:

```bash
python domains/rtl_sha_vtr/local_submit.py \
  --workspace . --candidate-id codex-local-1
```

Read `provisional_score`, the three metric deltas and `search_uncertainty`
before deciding your next step. The uncertainty report is descriptive: it
includes paired dispersion, a two-sided 95% Student-t interval and seed
wins/ties/losses. Treat an interval that crosses `1.0` as a fragile five-seed
ordering, not as evidence of improvement. Runtime is measured and emitted by
the command; an identical candidate is served from a verified cache. You
control the local search strategy and may make as many novel local submissions
as you judge useful. The tool reports measurements without recommending
whether to keep, revise or revert a candidate.

This command is deliberately only a ranking aid. It requires EQY to establish
the formal eligibility of the exact frozen submission, but it cannot establish
PPA acceptance and must never be described as a passing certification. The
external 64-seed evaluator remains the sole acceptance authority after you
return your selected candidate.

The search loop uses five exposed seeds (`1, 7, 19, 43, 97`) only as a
provisional ranking signal. Certification uses a different frozen pool of 64
seeds only after search closes. Up to three distinct finalists are selected by
the five-seed point score and certified. A new champion is named only when one
finalist has direct 64-seed evidence of improvement against the incumbent and
every other proven finalist; otherwise the incumbent remains or the result is
reported without a unique champion. The three equal-weight objectives are routed total area,
post-route delay and active-workload energy per block. Lower score is better.
Certification requires the paired composite one-sided 95% upper confidence
bound below `1.0` and no primary metric with evidence of regression. It stops at
64 and may remain inconclusive. Preserve readable synthesizable RTL and explain
the hardware effect of every proposed change.
