.PHONY: all verify figures report checksums test clean-report

PYTHON ?= python3
REPORT_PYTHON ?= python3

all: verify figures report

verify:
	$(PYTHON) scripts/verify_evidence.py

figures:
	$(PYTHON) scripts/generate_figures.py

report: figures
	$(REPORT_PYTHON) scripts/build_report.py

checksums:
	$(PYTHON) scripts/write_manifest.py

test: verify
	$(PYTHON) -m unittest discover -s tests -v

clean-report:
	$(PYTHON) -c "from pathlib import Path; [p.unlink() for p in (Path('tmp/pdfs')).glob('report-page-*.png')]"
