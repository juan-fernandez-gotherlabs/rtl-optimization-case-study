# External audit protocol

This repository is a self-verifying evidence package. It has not, as of the
version documented here, received an accredited certification or a signed
independent third-party assurance opinion. “Certification” in case artifacts
means acceptance under the fixed, source-controlled project contract.

## Current status

| Layer | SHA-1 | INT8 MatVec | ML-KEM CBD |
|---|---|---|---|
| Compact consistency verifier | Public and automated | Public and automated | Public and automated |
| Raw-provenance verification | Public release asset and verifier | Public blinded release asset and verifier | Public 64-pair release asset and verifier |
| Separate deterministic replay by the project | Not claimed as third-party work | Recorded for baseline and accepted RTL | Not claimed as third-party work |
| Fresh EDA rerun by an external organisation | Not yet signed off | Not yet signed off | Not yet signed off |
| Accredited certification or assurance | None | None | None |

The raw verifier recomputes metrics from archived logs. It does not rerun the
EDA tools, and a project-operated replay is not organisational independence.

## Auditor packet

An external reviewer should receive:

1. a clean checkout of the exact signed review tag or commit;
2. the matching hash-addressed raw-evidence release asset;
3. this protocol, the case report and the source-controlled verifier;
4. under NDA when necessary, the sealed INT8 placement-seed identity map and
   pre-selection records needed to check uniqueness, ordering and separation
   from the optimizer-visible pool;
5. the pinned container build inputs and target-file digests required for an
   optional fresh Linux/amd64 EDA rerun.

The reviewer should record every received file digest before inspection. Seed
identities need not be published, but the auditor must state whether all 64 are
unique, whether they are disjoint from the five search pairs and whether the
fixed sample and stopping rule pre-date inspection of the accepted result.

## Minimum evidence review

From the repository root:

```bash
python3 verify.py
python3 -m unittest discover -s cases/sha1/tests -v
python3 -m unittest discover -s cases/int8-matvec/tests -v
python3 -m unittest discover -s cases/mlkem-cbd/tests -v
```

Then download each release asset using the URL in its case README, verify the
published SHA-256 digest and run:

```bash
python3 cases/sha1/verify.py --evidence-archive \
  path/to/sha1-vtr45-full-evidence-v2.tar.gz
python3 cases/int8-matvec/verify.py --evidence-archive \
  path/to/int8-matvec-vtr45-full-evidence-v1.tar.gz
python3 cases/mlkem-cbd/verify.py --evidence-archive \
  path/to/mlkem-cbd-vtr45-full-evidence-v1.tar.gz
```

The reviewer must fail the audit if an archive member, fixed authority,
correctness marker, formal closure result, RTL binding, raw metric extraction,
acceptance bound or declared claim boundary fails. Rehashing a modified JSON
file is not sufficient to change a source-controlled authority.

## Optional fresh reproduction

A stronger review independently rebuilds the pinned Linux/amd64 environment
and reruns functional checks, formal equivalence and all fixed VTR/PTM 45 nm
placement pairs. The reproduced output must be compared with the published RTL
hashes, target hashes, operating point, metric definitions and acceptance
decision. Tool-version drift or an unverified substitute target is a different
experiment and must be reported as such.

## Claim matrix

An audit sign-off may confirm only the claims its work supports:

| Claim | Compact check | Raw archive | Fresh external rerun |
|---|:---:|:---:|:---:|
| Published arithmetic and confidence intervals recompute | Yes | Yes | Yes |
| Published RTL and patch identities match | Yes | Yes | Yes |
| Archived correctness and EDA records are internally bound | No | Yes | Yes |
| EDA results were independently regenerated | No | No | Yes |
| Physical FPGA, ASIC or measured-energy performance | No | No | No |

## Sign-off record

The external report should identify the reviewed Git commit/tag and archive
digests; auditor organisation and responsible reviewer; review date; commands
and environment; compact, raw and fresh-rerun status separately; exceptions;
and the exact approved claim wording. “PASS” without this scope is insufficient.

Historical tags and release assets remain immutable records of their published
versions. A later hardened package does not retroactively change an earlier
artifact; an auditor should always review the files named by the selected tag.
