#!/usr/bin/env bash
set -euo pipefail
exec 2>&1

bash "$SCRIPTS/create_mutated.sh" -o mutated.v

if ! verilator --binary --timing -Wall -Wno-fatal --top-module sha1_nist_tb \
  --Mdir nist_obj mutated.v "$PRJDIR/sha1_nist_tb.sv" > nist_compile.log 2>&1; then
  echo '1 ERROR' > output.txt
  exit 0
fi
set +e
nist_obj/Vsha1_nist_tb +CORPUS="$PRJDIR/nist_short_long.corpus" > nist_simulation.log 2>&1
nist_status=$?
set -e
if [[ $nist_status -ne 0 ]]; then
  if grep -Eq 'mismatch|%Error|Aborting' nist_simulation.log; then
    echo '1 FAIL' > output.txt
  else
    echo '1 ERROR' > output.txt
  fi
  exit 0
fi
if ! grep -q '^SHA1_NIST_SHAVS_PASS cases=129$' nist_simulation.log; then
  echo '1 ERROR' > output.txt
  exit 0
fi

# Digest-level tests intentionally do not observe every cycle-visible output.
# Run the frozen temporal contract for every NIST survivor before asking EQY to
# classify any remaining survivor as equivalent or an uncovered test escape.
if ! verilator --binary --timing -Wall -Wno-fatal --top-module sha1_equivalence_tb \
  --Mdir cycle_obj mutated.v "$PRJDIR/sha1_reference.v" "$PRJDIR/sha1_equivalence_tb.v" \
  > cycle_compile.log 2>&1; then
  echo '1 ERROR' > output.txt
  exit 0
fi
set +e
cycle_obj/Vsha1_equivalence_tb > cycle_simulation.log 2>&1
cycle_status=$?
set -e
if [[ $cycle_status -eq 0 ]] && \
  grep -q '^SHA_VTR_EQUIVALENCE_CONTRACT_PASS cases=16 checks=' cycle_simulation.log; then
  echo '1 PASS' > output.txt
elif grep -Eq 'mismatch|%Error|Aborting|Assertion failed' cycle_simulation.log; then
  echo '1 FAIL' > output.txt
else
  echo '1 ERROR' > output.txt
fi
