#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "usage: $0 <candidate-sha.v> <search|certification> <new-results-dir> [candidate-id]" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
candidate="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
tier="$2"
results="$3"
candidate_id="${4:-external-candidate}"

if [[ "${tier}" != "search" && "${tier}" != "certification" ]]; then
  echo "tier must be search or certification" >&2
  exit 2
fi
if [[ -e "${results}" && -n "$(find "${results}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "results directory must be new or empty: ${results}" >&2
  exit 2
fi

workspace="$(mktemp -d)"
mkdir -p "${workspace}/domains/rtl_sha_vtr/benchmarks" "${results}"
cp "${candidate}" "${workspace}/domains/rtl_sha_vtr/benchmarks/sha.v"

PYTHONPATH="${repo_root}/reproduce" python3 \
  "${repo_root}/reproduce/domains/rtl_sha_vtr/eval_script.py" \
  --workspace "${workspace}" \
  --output "${results}/result.json" \
  --candidate-id "${candidate_id}" \
  --tier "${tier}" \
  --evidence-dir "${results}/evidence"
