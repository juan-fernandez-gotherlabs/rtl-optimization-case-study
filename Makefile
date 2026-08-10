.PHONY: all verify test technical-report checksums clean

PYTHON ?= python3
LATEXMK ?= latexmk
SOURCE_DATE_EPOCH ?= 1786233600

all: technical-report checksums verify test

verify:
	$(PYTHON) verify.py

test:
	$(PYTHON) -m unittest discover -s tests -v

technical-report:
	$(PYTHON) scripts/generate_latex_data.py
	mkdir -p tmp/latex
	cd report/latex && SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH) FORCE_SOURCE_DATE=1 $(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error -outdir=../../tmp/latex technical-report.tex
	cp tmp/latex/technical-report.pdf technical-report.pdf

checksums:
	$(PYTHON) scripts/write_manifest.py

clean:
	rm -rf tmp/latex
