#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache_root="${RTL_SHA_VTR_CACHE:-${repo_root}/.cache}"
vtr_root="${cache_root}/vtr-verilog-to-routing"
vtr_commit="95f5c6de9e158371ba7185bf97c07a84153735d6"
image="evolther-vtr-ppa45:95f5c6de-linux-amd64"

mkdir -p "${cache_root}"
if [[ ! -d "${vtr_root}/.git" ]]; then
  git clone --filter=blob:none --no-checkout \
    https://github.com/verilog-to-routing/vtr-verilog-to-routing.git "${vtr_root}"
fi
git -C "${vtr_root}" fetch --depth 1 origin "${vtr_commit}"
git -C "${vtr_root}" checkout --detach "${vtr_commit}"
git -C "${vtr_root}" submodule update --init --recursive --depth 1
test "$(git -C "${vtr_root}" rev-parse HEAD)" = "${vtr_commit}"

docker build \
  --platform linux/amd64 \
  --tag "${image}" \
  --file "${repo_root}/reproduce/domains/rtl_sha_vtr/Dockerfile.vtr-ppa45-linux-amd64" \
  "${vtr_root}"

docker image inspect "${image}" --format '{{.Id}} {{.Os}}/{{.Architecture}}'
