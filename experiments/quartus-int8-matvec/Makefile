.PHONY: check verify matrix summarize evidence checksums clean

PYTHON ?= python3
QUARTUS_SH ?= quartus_sh
QUARTUS_POW ?= quartus_pow
FAMILY ?= MAX 10
DEVICE ?= 10M50DAF484C7G
PERIOD_NS ?= 5.000
FITTER_SEED ?= 1
THREADS ?= 4
EXECUTION_ENVIRONMENT ?= unspecified
OUTPUT_ROOT ?= output

check:
	$(PYTHON) tools/check_flow.py

verify: check
	$(PYTHON) verify.py

matrix: check
	$(PYTHON) tools/run_matrix.py --quartus-sh "$(QUARTUS_SH)" --quartus-pow "$(QUARTUS_POW)" --family "$(FAMILY)" --device "$(DEVICE)" --period-ns "$(PERIOD_NS)" --fitter-seed "$(FITTER_SEED)" --threads "$(THREADS)" --execution-environment "$(EXECUTION_ENVIRONMENT)" --output-root "$(OUTPUT_ROOT)"

summarize:
	$(PYTHON) tools/summarize_results.py "$(OUTPUT_ROOT)"

evidence:
	$(PYTHON) tools/package_evidence.py "$(OUTPUT_ROOT)" evidence/quartus-lite-25.1std-max10 --result-snapshot results/quartus-lite-25.1std-max10-summary.json

checksums:
	$(PYTHON) tools/write_manifest.py

clean:
	@echo "Remove $(OUTPUT_ROOT) explicitly after preserving any evidence you need."
