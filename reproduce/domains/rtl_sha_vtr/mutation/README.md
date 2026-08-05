# Mutation certification

This MCY project generates exactly 500 deterministic post-synthesis mutations
with the frozen MCY random seed `1`.
Each mutation first runs the full Short/Long NIST regression and every NIST
survivor runs the frozen cycle-by-cycle temporal regression. A mismatch in either
is a concrete witness that the mutation is functionally distinguishable and
covered. Only survivors of both run unbounded inductive EQY equivalence: mutations proven
equivalent are excluded from the denominator, counterexamples are uncovered test
escapes, and timeouts or inconclusive proofs block release. This ordering preserves
the formal coverage definition while keeping the 500-mutation gate bounded on the
two-CPU measurement environment.

The certification runner copies the corrected golden `sha.v`, frozen NIST
testbench and generated corpus here before `mcy init && mcy run -j2`.
