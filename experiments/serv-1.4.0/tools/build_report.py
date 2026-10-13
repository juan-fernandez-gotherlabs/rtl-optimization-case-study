#!/usr/bin/env python3
"""Build the14-page portfolio report from the saved64-pair evidence."""
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
LATEX=ROOT/'report/latex'
OUTPUT=REPO/'output/pdf/serv14'
subprocess.run([sys.executable,str(ROOT/'tools/generate_report_data.py')],check=True)
compiler=shutil.which('latexmk')
if compiler is None:
    raise SystemExit('Building this report requires TeX Live or MacTeX with latexmk and XeLaTeX.')
OUTPUT.mkdir(parents=True,exist_ok=True)
subprocess.run([compiler,'-norc','-xelatex','-interaction=nonstopmode','-halt-on-error','-synctex=1','-outdir='+str(OUTPUT),'technical-report.tex'],cwd=LATEX,check=True)
pdf=OUTPUT/'technical-report.pdf'
for target in [ROOT/'RTL-Study-SERV-1.4.0.pdf',REPO/'RTL-Study-SERV-1.4.0.pdf',REPO/'output/pdf/RTL-Study-SERV-1.4.0.pdf']:
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(pdf,target)
print(REPO/'RTL-Study-SERV-1.4.0.pdf')
