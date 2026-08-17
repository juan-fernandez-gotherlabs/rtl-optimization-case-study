# Verify, measure, certify

The public cases share one evidence model. They do not expose the optimization
implementation or private execution data.

## 1. Freeze the contract

Before optimization, the case fixes:

- editable artifacts and protected interfaces;
- functional and formal semantics;
- implementation toolchain and target;
- primary metrics and score direction;
- resource and metric validity limits;
- search and certification sampling policies.

Changing that contract produces a different experiment rather than an improved
candidate in the existing experiment.

## 2. Verify before measurement

A candidate must pass syntax/structure checks, deterministic functional tests
and the declared formal-equivalence scope before PPA measurement. Missing,
inconclusive or timed-out evidence fails closed. An incorrect design cannot
receive an improvement score.

## 3. Measure on a pinned target

Both current cases use a pinned Linux/amd64 VTR flow, homogeneous academic LUT6
architecture and PTM 45 nm model at 0.9 V and 85 degrees C. The target does not
model commercial DSP slices, BRAM or ASIC arithmetic cells. Case-specific fixed
wrappers may provide the clocked measurement boundary; wrapper resources must
be labelled separately from candidate RTL. Total area, post-route critical-path
delay and active total power are implementation-model estimates, not physical
measurements.

The composite score is the equal-weight paired geometric mean of:

```text
area ratio x critical-path-delay ratio x active-total-power ratio
```

expressed in log space. Lower is better and the frozen baseline is `1.0`.

## 4. Separate search from project-contract certification

The optimizer-visible sample ranks candidates. Once a candidate is frozen by
RTL hash, a disjoint held-out sample determines the project-contract result. The
sample size and stopping rule are fixed before observing certification.

Acceptance requires:

- functional and formal validity;
- complete implementation evidence;
- the composite one-sided 95% upper confidence bound below `1.0`;
- no primary metric with a one-sided 95% lower confidence bound above `1.0`;
- all declared resource and metric limits to pass.

## 5. Publish only the evidence boundary

The client-facing package contains before/after RTL, an exact patch, compact
paired measurements, hashes, reports and fail-closed consistency verification.
Reserved identities may be replaced by stable pair labels in a compact
certificate. Such a certificate can attest that functional, formal and
independent-replay gates passed, but it does not make those gates publicly
rerunnable unless their harnesses and raw outputs are also published.

Raw EDA logs can be distributed as hash-addressed release assets when the case
publication policy requires full provenance replay. Operational optimization
infrastructure remains private because it is neither necessary to understand
the claim nor part of the delivered technical improvement.

Here, “certification” means acceptance under the source-controlled project
contract. It is not an accredited certification, an assurance opinion or an
external third-party audit.

SHA-1 and INT8 each publish a separately downloadable, hash-addressed raw
evidence archive. Their public verifiers bind the archive to the compact case,
audit all members and re-extract the reported PPA metrics. This is provenance
replay, not a fresh EDA execution; independently rerunning the pinned tools is a
separate and more expensive reproduction step.
