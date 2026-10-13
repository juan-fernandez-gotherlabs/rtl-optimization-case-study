.PHONY: all verify test reports module-sizes checksums clean

PYTHON ?= python3

all: reports module-sizes checksums verify test

verify:
	$(PYTHON) verify.py

test:
	$(PYTHON) -m unittest discover -s cases/sha1/tests -v
	$(PYTHON) -m unittest discover -s cases/int8-matvec/tests -v
	$(PYTHON) -m unittest discover -s cases/mlkem-cbd/tests -v
	$(PYTHON) -m unittest discover -s experiments/serv-1.4.0/tests -v

reports:
	$(MAKE) -C cases/sha1 technical-report
	$(MAKE) -C cases/int8-matvec technical-report
	$(MAKE) -C cases/mlkem-cbd technical-report
	$(PYTHON) experiments/serv-1.4.0/tools/build_report.py
	cp cases/sha1/RTL-Study-SHA1.pdf RTL-Study-SHA1.pdf
	cp cases/int8-matvec/RTL-Study-INT8-MatVec.pdf RTL-Study-INT8-MatVec.pdf
	cp cases/mlkem-cbd/RTL-Study-MLKEM-CBD.pdf RTL-Study-MLKEM-CBD.pdf

module-sizes:
	$(PYTHON) tools/generate_module_sizes.py

checksums:
	$(PYTHON) cases/sha1/scripts/write_manifest.py
	$(PYTHON) cases/int8-matvec/tools/write_manifest.py
	$(PYTHON) cases/mlkem-cbd/tools/write_manifest.py
	$(PYTHON) experiments/serv-1.4.0/verify.py --write-manifest
	$(PYTHON) verify.py --write-manifest

clean:
	$(MAKE) -C cases/sha1 clean
	$(MAKE) -C cases/int8-matvec clean
	$(MAKE) -C cases/mlkem-cbd clean
