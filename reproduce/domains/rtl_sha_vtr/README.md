# SHA-1 RTL / VTR 45 nm pilot

This is a generator-neutral optimization domain for classic Evölther and
Evölther Codex. The domain defines correctness, measurement, evidence and the
public score; it never defines how candidates are generated.

> Scope: academic open-FPGA PPA estimation at the VTR 45 nm operating point.
> It is not a commercial FPGA result, ASIC flow, manufactured silicon result,
> or timing/power signoff. SHA-1 is used only as a legacy benchmark.

## Frozen contract

The sole editable file is `benchmarks/sha.v`, with interface:

```text
sha1(clk_i, rst_i, text_i[31:0], text_o[31:0], cmd_i[2:0], cmd_w_i, cmd_o[3:0])
```

The VTR upstream source, corrective patch, corrected golden seed, NIST vectors,
protocol, reset, all cycle-visible outputs, architecture, PTM, tool revisions,
activity profiles, seeds, parsers and score policy are hash-pinned in
`benchmarks/sha_vtr_manifest.json`. Candidate RTL cannot change latency or
throughput. Simulation-only constructs and synthesis escape hatches are blocked.

The original VTR RTL is retained as provenance and as a negative test: it does
not produce the FIPS SHA-1 digest for `abc`. The golden seed is rebuilt by
applying `sha1_conformance.patch` to that exact upstream file. This corrective
change is separate from optimization.

## Two evaluation modes

Candidate scoring has exactly two modes. The baseline for both pools is
measured once and reused; each candidate is always paired with the same seed in
the reference.

- **Domain qualification, once per released contract:** provenance, corrected
  gold, all NIST Short/Long and Monte Carlo vectors, unbounded EQY, 500 MCY
  mutations, baseline PPA, active/idle power and a clean reproduction.
- **Search:** hard correctness gates and the five exposed VPR seeds
  `1, 7, 19, 43, 97`. Its paired geometric PPA score ranks proposals only.
- **Certification:** hard correctness gates, all 129 NIST Short/Long cases and
  a fixed pool of 64 seeds disjoint from search. Only this mode can set
  `accepted_improvement=true`; it always stops after seed 64 and may return
  `evidence_improvement`, `inconclusive` or `evidence_regression`.

The agent-local **search submission** first freezes `sha.v` under its SHA-256,
then runs the complete functional and EQY gate. Only `formal_status=pass`
submissions may spend the five search seeds or enter the shortlist. It emits a
numeric `provisional_score` with `certified=false` and no acceptance decision.
On the qualified MacBook it uses two bounded workers and a verified
content-addressed cache. See `docs/SEARCH_ACCELERATION.md`. It never replaces
certification.

A formal timeout or inconclusive result invalidates every candidate tier. MCY
and the 100,000-hash Monte Carlo corpus qualify the harness and corrected gold;
they are not redundantly rerun for every equivalent candidate.

### Structure-preserving pilot contract

This pilot intentionally accepts only cycle-exact transformations that the
pinned EQY flow can prove using its same-named structural cut points. Arbitrary
state recoding, retiming and replacement microarchitectures are outside the
pilot scope. This is a conservative acceptance boundary: a functionally
equivalent but structurally unrelated candidate may be rejected, never silently
accepted. The earlier output-only feasibility audit remains traceable in
`evidence/ppa45/mutation_diagnostic.json`.

MCY qualifies the complete verification stack. A mutation is covered when the
NIST/cycle regression rejects it or, if it survives simulation, when the
structure-aware EQY gate rejects it. A completed EQY proof classifies it as
equivalent under this pilot contract. Reports must expose simulation-detected,
formal-only and equivalent counts separately; 100% combined coverage with zero
inconclusive mutations is mandatory. The previous 94.190871% value is retained
only as the diagnostic simulation contribution and is not the combined
qualification result.

The released reference passed a fresh 500-mutation campaign and an independent
qualification reproduction. Both runs produced the same MCY classification:
454 mutations detected by simulation, 28 additional mutations rejected
formally, 18 proven equivalent and zero inconclusive. The PPA baseline now also
stores five search rows and 64 disjoint certification rows with their raw
provenance. `evidence/ppa45/baseline.json` is the authoritative record; no score
or future promotion may bypass these gates.

## PPA and score

All primary metrics are minimized:

- `area_total_mwta`: post-route logic plus routing area in minimum-width
  transistor-area units.
- `critical_path_delay_ns`: post-route critical path.
- `energy_per_block_nj`: active total power times 5,000 routed clock periods,
  divided by 60 complete compression blocks.

The five-seed search score is the equal-weight geometric mean of paired area,
delay and energy ratios. It is provisional and never accepts a candidate. For
each search result the evaluator also publishes paired log dispersion, a
descriptive 95% interval, per-seed composite ratios and win/tie/loss counts.
These fields identify fragile rankings but have no certification authority
because the optimizer can see and reuse the search seeds. For
certification, the same ratios are evaluated in log space over the fixed 64
seeds:

```text
score = exp(mean_seed(mean_metric(log(candidate / reference))))
```

The baseline is valid with score `1.0` but is not an accepted improvement.
Functional, formal, synthesis, route, power or evidence-integrity failure is
invalid with score infinity. Certification accepts improvement only when the
composite one-sided 95% upper confidence bound is below `1.0` and no primary
metric has a one-sided 95% lower bound above `1.0`. Otherwise the result is
inconclusive or regressed. The fixed sample is never extended after inspecting
the result. Raw distributions, confidence bounds and Pareto coordinates remain
public.

## Reproducible image

Docker Desktop must have at least 7 GB available. Build context is the recursive
VTR checkout at commit `95f5c6de9e158371ba7185bf97c07a84153735d6`:

```bash
VTR_ROOT=/absolute/path/to/vtr-verilog-to-routing
DOMAIN_ROOT="$PWD/domains/rtl_sha_vtr"
test "$(git -C "$VTR_ROOT" rev-parse HEAD)" = 95f5c6de9e158371ba7185bf97c07a84153735d6

docker build --platform linux/amd64 \
  --file "$DOMAIN_ROOT/Dockerfile.vtr-ppa45-linux-amd64" \
  --tag evolther-vtr-ppa45:95f5c6de-linux-amd64 \
  "$VTR_ROOT"
```

Evaluation containers are always networkless and limited to 2 CPUs, 7 GB RAM,
7 GB swap-inclusive memory, 512 PIDs and stage timeouts. The image records OS
packages and Python packages for SBOM/provenance.

## Certification and evaluation

Run progressively; never jump directly to the costly 64-seed baseline:

```bash
python domains/rtl_sha_vtr/certify_baseline.py \
  --phase functional --results /absolute/path/sha-functional

python domains/rtl_sha_vtr/certify_baseline.py \
  --phase preflight --results /absolute/path/sha-preflight

python domains/rtl_sha_vtr/certify_baseline.py \
  --phase certify --results /absolute/path/sha-certified

python domains/rtl_sha_vtr/compare_reproduction.py \
  /absolute/path/sha-certified/baseline_certify.json \
  /absolute/path/sha-clean-reproduction/baseline_certify.json \
  --output /absolute/path/reproduction-comparison.json

python domains/rtl_sha_vtr/promote_baseline.py \
  /absolute/path/sha-certified/baseline_certify.json \
  /absolute/path/sha-clean-reproduction/baseline_certify.json
```

The promotion command independently repeats the comparison, verifies the
current manifest and golden RTL hashes, and writes `evidence/ppa45/baseline.json`
atomically. Only after review and successful promotion may a candidate be
evaluated. The default command is the five-seed search mode:

```bash
python domains/rtl_sha_vtr/eval_script.py \
  --workspace . --candidate-id search-check --tier search --output /tmp/sha-result.json
jq '{valid, accepted_improvement, score, metrics, status: .trace.status}' /tmp/sha-result.json
```

Certify a selected winner separately:

```bash
python domains/rtl_sha_vtr/eval_script.py \
  --workspace . --candidate-id winner --tier certification \
  --evidence-dir /absolute/path/sha-certification-evidence \
  --output /tmp/sha-certification.json
```

Search is `valid` when its correctness and measurement gates pass,
but it has `certified=false`, `acceptance_decision=null` and can never claim an
accepted improvement.
Certification fails closed unless its complete logs are written to a
new or empty persistent evidence directory.

### Finalists and champion

At the end of search, build the fixed three-candidate shortlist from any number
of five-seed result files:

```bash
python domains/rtl_sha_vtr/selection.py shortlist \
  /absolute/path/search-results/*.json \
  --output /absolute/path/finalists.json
```

The selector admits only immutable submissions with `formal_status=pass`,
verifies every score from the raw paired rows, deduplicates RTL by SHA-256,
ranks by the point estimate and reports descriptive pairwise fragility against
the point leader. It selects at most three candidates; it does not claim that
their order is certified.

After separately running `--tier certification` for those candidates, decide
the champion from their 64-seed result files:

```bash
python domains/rtl_sha_vtr/selection.py champion \
  /absolute/path/certifications/*.json \
  --output /absolute/path/champion.json
```

An optional `--incumbent <certification.json>` compares challengers with an
already certified champion instead of the released baseline. The incumbent is
replaced only when exactly one challenger has evidence of improvement against
it and against every other finalist that also proved improvement. Otherwise
the result is `incumbent_retained_no_proven_improvement` or
`no_unique_champion`; no additional seeds are requested.

For high-volume ranking, run the non-certifying triage first:

```bash
python domains/rtl_sha_vtr/triage_script.py \
  --workspace . --candidate-id proposal-001 \
  --cache-dir /absolute/path/sha-triage-cache \
  --output /tmp/proposal-001-triage.json
```

See `docs/REPRODUCIBILITY.md` for evidence handling and `docs/DEMO.md` for the
one-command correctness plus disposable-seed customer preflight. Historical 40 nm files are indexed under
`evidence/legacy_40nm/` and are explicitly incompatible with this baseline.

### Agent-local submission

Evölther Codex may inspect one candidate before returning it to the coordinator,
using the same frozen triage through a concise agent-facing command:

```bash
python domains/rtl_sha_vtr/local_submit.py \
  --workspace . --candidate-id codex-local-1
```

The command reports candidate and baseline five-seed metrics, percentage deltas
and cache status without making a keep/revise/revert recommendation. It is
bounded per invocation to the functional/EQY gate plus five fixed PPA seeds,
and is content-addressed. A failed or inconclusive EQY result stops before PPA.
Evölther Codex controls its own search horizon and may run
as many novel submissions as it judges useful. The disjoint 64-seed
certification remains the external acceptance gate, so local output cannot set
`certified` or `accepted_improvement`.
