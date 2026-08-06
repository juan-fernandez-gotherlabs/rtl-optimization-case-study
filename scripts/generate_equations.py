#!/usr/bin/env python3
"""Render the checked-in standalone LaTeX equations as portable SVG paths."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "report" / "equations"
BUILD_DIR = ROOT / "tmp" / "pdfs" / "equations-build"
FIGURES_DIR = ROOT / "figures"
METADATA = {
    "rewrite-1-choose": (
        "SHA-1 choose equivalence",
        "LaTeX derivation from the baseline choose expression to the accepted product-of-sums form.",
    ),
    "rewrite-2-majority": (
        "SHA-1 majority equivalence",
        "LaTeX derivation from the expanded majority expression to the accepted factored form.",
    ),
    "rewrite-3-xor": (
        "Message-schedule XOR equivalence",
        "LaTeX derivation showing associativity of the balanced message-schedule XOR.",
    ),
    "rewrite-4-accumulator": (
        "Round accumulator equivalence",
        "LaTeX derivation showing associativity of the 32-bit accumulator modulo 2 to the power 32.",
    ),
}


def required_command(env_name: str, default: str) -> str:
    configured = os.environ.get(env_name)
    resolved = shutil.which(configured or default)
    if resolved is None:
        raise RuntimeError(f"{configured or default} is required to render equations")
    return resolved


def main() -> int:
    pdflatex = required_command("PDFLATEX", "pdflatex")
    pdftocairo = required_command("PDFTOCAIRO", "pdftocairo")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    for source in sorted(SOURCE_DIR.glob("*.tex")):
        subprocess.run(
            [
                pdflatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={BUILD_DIR}",
                str(source),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        pdf = BUILD_DIR / f"{source.stem}.pdf"
        target = FIGURES_DIR / f"{source.stem}-equation.svg"
        subprocess.run([pdftocairo, "-svg", str(pdf), str(target)], check=True)
        svg = target.read_text(encoding="utf-8")
        root_end = svg.index(">", svg.index("<svg")) + 1
        title, description = METADATA[source.stem]
        svg = (
            svg[:root_end]
            + f"\n<title>{title}</title>\n<desc>{description}</desc>"
            + svg[root_end:]
        )
        target.write_text(svg, encoding="utf-8")
        print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
