.PHONY: all verify test reports checksums clean

PYTHON ?= python3

all: reports checksums verify test

verify:
	$(PYTHON) verify.py

test:
	$(PYTHON) -m unittest discover -s cases/sha1/tests -v
	$(PYTHON) -m unittest discover -s cases/int8-matvec/tests -v
	$(PYTHON) -m unittest discover -s cases/mlkem-cbd/tests -v

reports:
	$(MAKE) -C cases/sha1 technical-report
	$(MAKE) -C cases/int8-matvec technical-report
	$(MAKE) -C cases/mlkem-cbd technical-report
	cp cases/sha1/technical-report.pdf SHA1-RTL-Optimization.pdf
	cp cases/int8-matvec/technical-report.pdf INT8-MatVec-Optimization.pdf
	cp cases/mlkem-cbd/technical-report.pdf MLKEM-CBD-Optimization.pdf

checksums:
	$(PYTHON) cases/sha1/scripts/write_manifest.py
	$(PYTHON) cases/int8-matvec/tools/write_manifest.py
	$(PYTHON) cases/mlkem-cbd/tools/write_manifest.py
	$(PYTHON) verify.py --write-manifest

clean:
	$(MAKE) -C cases/sha1 clean
	$(MAKE) -C cases/int8-matvec clean
	$(MAKE) -C cases/mlkem-cbd clean
