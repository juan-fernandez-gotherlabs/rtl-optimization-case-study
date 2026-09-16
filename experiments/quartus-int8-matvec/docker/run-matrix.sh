#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
flow_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
repo_root=$(CDPATH= cd -- "$flow_root/../.." && pwd)

: "${QUARTUS_INSTALL_DIR:?Set QUARTUS_INSTALL_DIR to the absolute host directory containing Quartus Lite}"

quartus_device=${QUARTUS_DEVICE:-10M50DAF484C7G}
quartus_family=${QUARTUS_FAMILY:-MAX 10}
quartus_period_ns=${QUARTUS_PERIOD_NS:-5.000}

if [[ ! -d "$QUARTUS_INSTALL_DIR" ]]; then
    echo "Quartus installation directory does not exist: $QUARTUS_INSTALL_DIR" >&2
    exit 2
fi

exec docker run --rm \
    --platform linux/amd64 \
    --volume "$repo_root:/workspace" \
    --volume "$QUARTUS_INSTALL_DIR:/opt/altera:ro" \
    --env QUARTUS_DEVICE="$quartus_device" \
    --env QUARTUS_FAMILY="$quartus_family" \
    --env QUARTUS_PERIOD_NS="$quartus_period_ns" \
    --workdir /workspace/experiments/quartus-int8-matvec \
    gother-quartus-runner:ubuntu22.04 \
    bash -lc 'quartus_sh_path=$(find /opt/altera -type f -path "*/quartus/bin/quartus_sh" -print -quit); test -n "$quartus_sh_path" || { echo "quartus_sh not found below /opt/altera" >&2; exit 2; }; quartus_bin=$(dirname "$quartus_sh_path"); export PATH="$quartus_bin:$PATH"; make matrix DEVICE="$QUARTUS_DEVICE" FAMILY="$QUARTUS_FAMILY" PERIOD_NS="$QUARTUS_PERIOD_NS"'
