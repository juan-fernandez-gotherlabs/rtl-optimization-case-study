.PHONY: check matrix summarize docker-image docker-matrix docker-shell clean

PYTHON ?= python3
QUARTUS_SH ?= quartus_sh
QUARTUS_POW ?= quartus_pow
FAMILY ?= MAX 10
DEVICE ?= 10M50DAF484C7G
PERIOD_NS ?= 5.000
OUTPUT_ROOT ?= output

check:
	$(PYTHON) tools/check_flow.py

matrix: check
	$(PYTHON) tools/run_matrix.py --quartus-sh "$(QUARTUS_SH)" --quartus-pow "$(QUARTUS_POW)" --family "$(FAMILY)" --device "$(DEVICE)" --period-ns "$(PERIOD_NS)" --output-root "$(OUTPUT_ROOT)"

summarize:
	$(PYTHON) tools/summarize_results.py "$(OUTPUT_ROOT)"

docker-image:
	docker build --platform linux/amd64 -t gother-quartus-runner:ubuntu22.04 docker

docker-matrix:
	QUARTUS_DEVICE="$(DEVICE)" QUARTUS_FAMILY="$(FAMILY)" QUARTUS_PERIOD_NS="$(PERIOD_NS)" docker/run-matrix.sh

docker-shell:
	docker/run-shell.sh

clean:
	@echo "Remove $(OUTPUT_ROOT) explicitly after preserving any evidence you need."
