#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
flow_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
repo_root=$(CDPATH= cd -- "$flow_root/../.." && pwd)

: "${QUARTUS_INSTALL_DIR:?Set QUARTUS_INSTALL_DIR to the absolute host directory containing Quartus Lite}"

if [[ ! -d "$QUARTUS_INSTALL_DIR" ]]; then
    echo "Quartus installation directory does not exist: $QUARTUS_INSTALL_DIR" >&2
    exit 2
fi

exec docker run --rm -it \
    --platform linux/amd64 \
    --volume "$repo_root:/workspace" \
    --volume "$QUARTUS_INSTALL_DIR:/opt/altera:ro" \
    --workdir /workspace/experiments/quartus-int8-matvec \
    gother-quartus-runner:ubuntu22.04
