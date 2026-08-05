#!/usr/bin/env bash
set -euo pipefail
exec 2>&1

bash "$SCRIPTS/create_mutated.sh" -o mutated.v
cat > check.eqy <<'EOF'
[gold]
read_verilog ../../sha1_gold.v
prep -top sha1
sim -clock clk_i -reset rst_i -rstlen 1 -n 1 -w sha1

[gate]
read_verilog mutated.v
prep -top sha1
sim -clock clk_i -reset rst_i -rstlen 1 -n 1 -w sha1

[strategy sat]
use sat
depth 10
EOF

set +e
timeout --signal=TERM --kill-after=10s 300s eqy -f check.eqy > formal.log 2>&1
status=$?
set -e
if [[ $status -eq 0 ]] && grep -q 'Successfully proved designs equivalent' formal.log; then
  echo '1 PASS' > output.txt
elif [[ $status -ne 124 ]] && grep -Eq 'Failed to prove equivalence|not equivalent|FAIL' formal.log; then
  echo '1 FAIL' > output.txt
else
  echo '1 ERROR' > output.txt
fi
