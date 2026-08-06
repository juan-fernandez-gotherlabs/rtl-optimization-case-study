.PHONY: all verify equations figures report executive-report technical-report latex-report reportlab-report checksums release-package test clean-report

PYTHON ?= python3
REPORT_PYTHON ?= python3
LATEXMK ?= latexmk
SOURCE_DATE_EPOCH ?= 1785888000

all: verify figures report

verify:
	$(PYTHON) scripts/verify_evidence.py

equations:
	$(PYTHON) scripts/generate_equations.py

figures:
	$(PYTHON) scripts/generate_figures.py

report: executive-report technical-report

executive-report: figures
	$(REPORT_PYTHON) scripts/build_report.py --executive-only

technical-report:
	$(PYTHON) scripts/generate_latex_data.py
	mkdir -p tmp/latex
	cd report/latex && SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH) FORCE_SOURCE_DATE=1 $(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error -outdir=../../tmp/latex technical-report.tex
	cp tmp/latex/technical-report.pdf report/technical-report.pdf

latex-report: technical-report

reportlab-report: figures
	$(REPORT_PYTHON) scripts/build_report.py --technical-only

checksums:
	$(PYTHON) scripts/write_manifest.py

release-package: report checksums
	@test -n "$(EVIDENCE_ARCHIVE)" || (echo "EVIDENCE_ARCHIVE=/absolute/path/to/public-evidence.tar.gz is required" >&2; exit 2)
	$(PYTHON) scripts/prepare_release.py --evidence-archive "$(EVIDENCE_ARCHIVE)"

test: verify
	$(PYTHON) -m unittest discover -s tests -v

clean-report:
	$(PYTHON) -c "from pathlib import Path; [p.unlink() for p in (Path('tmp/pdfs')).glob('report-page-*.png')]"
