#!/usr/bin/env python3
"""Recompute the portfolio size tables from frozen RTL and paired evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = "<!-- module-sizes:start -->"
END = "<!-- module-sizes:end -->"
SPECS = (
    ("SHA-1", "cases/sha1", "accepted", "results/certification.json", "per_seed", "clb_blocks", "Sequential compression core"),
    ("INT8 MatVec", "cases/int8-matvec", "optimized", "certificate.json", "pairs", "clb_blocks", "Combinational 4 × 4 kernel"),
    ("ML-KEM CBD", "cases/mlkem-cbd", "optimized", "certificate.json", "pairs", "clb_count", "Sequential coefficient sampler"),
    ("SERV 1.4.0", "experiments/serv-1.4.0", "optimized", "results/confirmation64.json", "all_rows", "clb_count", "Serial 32-bit CPU and RF interface"),
)


def source_size(folder: Path) -> dict[str, int]:
    files = sorted(p for p in folder.rglob("*") if p.suffix in {".v", ".sv"})
    result = dict(files=len(files), modules=0, total_lines=0, code_lines=0, bytes=0)
    # Preserve strings and newlines while removing Verilog comments.
    pattern = r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*'
    for path in files:
        source = path.read_text(encoding="utf-8")
        stripped = re.sub(
            pattern,
            lambda m: m.group() if m.group().startswith('"') else "\n" * m.group().count("\n"),
            source,
            flags=re.S,
        )
        result["modules"] += len(re.findall(r"\bmodule\s+\w+", stripped))
        result["total_lines"] += len(source.splitlines())
        result["code_lines"] += sum(bool(line.strip()) for line in stripped.splitlines())
        result["bytes"] += path.stat().st_size
    return result


def geometric_mean(values: list[float]) -> float:
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("invalid area sample")
    return math.exp(math.fsum(math.log(v) for v in values) / len(values))


def constant(values: list[int]) -> int:
    if len(set(values)) != 1:
        raise ValueError("resource count varies; report its range instead")
    return values[0]


def load_cases() -> list[dict]:
    cases = []
    for name, folder, candidate, filename, rows_key, clb_key, scope in SPECS:
        evidence_path = ROOT / folder / filename
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        rows = evidence[rows_key]
        if len(rows) != 64:
            raise ValueError(f"{name}: expected the frozen 64-pair sample")
        case = dict(name=name, folder=folder, candidate=candidate, scope=scope,
                    evidence=f"{folder}/{filename}",
                    digest=hashlib.sha256(evidence_path.read_bytes()).hexdigest())
        for side in ("baseline", candidate):
            row_side = "accepted" if candidate == "accepted" and side != "baseline" else side
            metrics = [row[row_side] for row in rows]
            registers = None
            if "registers" in metrics[0]:
                registers = constant([m["registers"] for m in metrics])
            elif name == "SERV 1.4.0":
                registers = evidence["mapped_FF_count"][side]
            case[side] = dict(
                source=source_size(ROOT / folder / "rtl" / side),
                clbs=constant([m[clb_key] for m in metrics]),
                registers=registers,
                area=geometric_mean([m["area_total_mwta"] for m in metrics]),
            )
        cases.append(case)
    return cases


def pair(before: int, after: int) -> str:
    return f"{before:,} → {after:,}"


def overview(cases: list[dict]) -> str:
    lines = [START, "", "| Module | Measured scope | RTL files¹ | Code lines¹ | CLBs² | Area² (10⁶ MWTA) |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for case in cases:
        b, o = case["baseline"], case[case["candidate"]]
        lines.append(f"| [{case['name']}]({case['folder']}/README.md) | {case['scope']} | "
                     f"{pair(b['source']['files'], o['source']['files'])} | "
                     f"{pair(b['source']['code_lines'], o['source']['code_lines'])} | "
                     f"{pair(b['clbs'], o['clbs'])} | {b['area']/1e6:.3f} → {o['area']/1e6:.3f} |")
    serv = cases[-1]["baseline"]
    multiples = [c["baseline"]["area"] / serv["area"] for c in cases[:-1]]
    lines += ["", "All arrows show baseline → optimized. ¹ Bundled source, including inactive",
              "alternatives. ² Measured wrapper; area is the geometric mean of 64 implementations.",
              "", f"**SERV expands the architectural scope to a CPU, while its measured baseline is",
              f"{min(multiples):.2f}–{max(multiples):.2f} times smaller in area than the other modules.** Its external",
              "register RAM is excluded from these measurements: the default configuration",
              "requires 1,152 bits (144 B), arranged as 576 rows × 2 bits. The source tree",
              "contains 18 modules, including modules outside the measured hierarchy.",
              "", "See [Module sizes and orders of magnitude](MODULE-SIZES.md) for source bytes,",
              "state, memory capacity, mapped registers, measurement boundaries and reproducible tables.",
              "", END]
    return "\n".join(lines)


def document(cases: list[dict]) -> str:
    lines = ["# Module sizes and orders of magnitude", "",
             "This comparison covers the three accepted VTR cases and the paused SERV 1.4.0",
             "study. All measurements below use each case's frozen 64-pair sample.", "",
             "**SERV is the step from a specialized block to an instruction-executing CPU.**",
             "Its serial datapath keeps the measured hardware small. The portfolio therefore",
             "expands in architectural integration and verification scope; the measured",
             "circuit becomes smaller than the previous blocks.", "",
             "## 1. Source size", "",
             "Each arrow is baseline → optimized. Code lines are nonblank lines after",
             "removing `//` and `/* ... */` comments; declarations and preprocessor directives",
             "count. Total lines include blank lines and comments. Bytes are exact file sizes",
             "for `.v` and `.sv` files in the bundled RTL directory (1 KiB = 1,024 bytes).", "",
             "| Module | Files / module declarations | Code lines | Total lines | Bytes | KiB |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for case in cases:
        b, o = case["baseline"]["source"], case[case["candidate"]]["source"]
        lines.append(f"| [{case['name']}]({case['folder']}/rtl/baseline) | "
                     f"{b['files']} / {b['modules']} → {o['files']} / {o['modules']} | "
                     f"{pair(b['code_lines'],o['code_lines'])} | {pair(b['total_lines'],o['total_lines'])} | "
                     f"{pair(b['bytes'],o['bytes'])} | {b['bytes']/1024:.2f} → {o['bytes']/1024:.2f} |")
    lines += ["", "Source size describes the material included in the study. It does not count",
              "gates, instantiated hardware, memory capacity or execution throughput. SERV's",
              "18-file tree includes RAM, debug, alignment and other optional modules outside",
              "the selected synthesis hierarchy. The optimized tree also retains inactive",
              "parameter alternatives; its additional source lines do not enlarge the frozen",
              "implemented configuration.", "", "## 2. Implemented resource size", "",
              "CLB counts are constant across all 64 implementations of each source. Area is",
              "the geometric mean of **total area = reported logic area + reported routing area**",
              "from the saved per-pair rows. MWTA means minimum-width transistor area, an",
              "academic normalized unit; these values cannot be read as mm² or ASIC gate counts.", "",
              "| Module | CLBs | Mapped registers / FF | Total area (MWTA) | Area (10⁶ MWTA) |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for case in cases:
        b, o = case["baseline"], case[case["candidate"]]
        ff = pair(b["registers"], o["registers"]) if b["registers"] is not None else "Not recorded in compact certificate"
        lines.append(f"| {case['name']} | {pair(b['clbs'],o['clbs'])} | {ff} | "
                     f"{b['area']:,.0f} → {o['area']:,.0f} | {b['area']/1e6:.3f} → {o['area']/1e6:.3f} |")
    lines += ["", "- **SHA-1:** the 892 mapped registers include the core's implemented state.",
              "- **INT8 MatVec:** the DUT has no sequential state. The 72 mapped registers",
              "  belong to the fixed output-register measurement wrapper after synthesis.",
              "  All 16 signed multiplications map into LUT fabric; the contract reports zero",
              "  dedicated multiplier blocks. The vector and matrix are input signals, not RAM.",
              "- **ML-KEM CBD:** the compact certificate records CLBs and area, without a",
              "  mapped FF count. RTL declares 1,113 sequential bits in the baseline and 1,115",
              "  in the candidate: 1,096 data bits, two 8-bit counters, one end flag, plus the",
              "  candidate's 2-bit phase. These are declared state sizes, not a claimed mapped",
              "  FF count. The candidate's `reg_shake` is a combinational view of `shake_chunks`,",
              "  so it does not add another 1,096-bit storage array.",
              "- **SERV:** the 181 mapped FF include the selected CPU and register-file",
              "  interface. External register RAM, instruction memory and data memory are",
              "  outside the wrapper and the PPA totals.", "",
              "The four contracts use the academic homogeneous LUT6/PTM 45 nm target. Each",
              "wrapper, lowering contract and workload remains specific to its case. Resource",
              "figures describe circuit scale within those boundaries. Power models and work",
              "per operation differ, so the comparison does not rank cross-module throughput",
              "or energy efficiency. The SHA-1 report uses medians in its executive table;",
              "this comparison consistently recomputes geometric means for all four cases.", "",
              "## 3. Workload, state and capacity", "",
              "| Module | Data dimensions and interface | Main logical state / capacity | Storage boundary |",
              "| --- | --- | --- | --- |",
              "| [SHA-1](cases/sha1/rtl/baseline/sha.v) | 80 compression rounds; 512-bit (64 B) input block; 160-bit (20 B) digest; 32-bit command data input/output | 16 × 32-bit schedule words (15 `W` registers plus `Wt`), 5 × 32-bit working words, 5 × 32-bit hash words: 832 main data-state bits (104 B); control and output registers are additional | Registers inside the core; no mapped memory blocks |",
              "| [INT8 MatVec](cases/int8-matvec/rtl/baseline/int8_matvec_4x4.sv) | 4 × 4 signed INT8 matrix plus 4-element INT8 vector: 160 input bits (20 B); four signed 32-bit outputs: 128 bits (16 B) | 16 exact parallel multiplications and 4 dot products; zero stored DUT state | Inputs are supplied externally; output FF belong to the measurement wrapper |",
              "| [ML-KEM CBD](cases/mlkem-cbd/rtl/baseline/cbd.v) | 1,088-bit (136 B) SHAKE input; four 12-bit coefficients on two 24-bit outputs; two 8-bit destination addresses; η = 2 or 3 | 1,096-bit (137 B) sampler state, including 8 carry bits; candidate retains that logical capacity and adds 2 phase bits to its representation | State is internal registers; destination coefficient RAM is external |",
              "| [SERV 1.4.0](experiments/serv-1.4.0/rtl/baseline/serv_synth_wrapper.v) | 32-bit instruction set; 1-bit serial datapath; 32-bit instruction/data buses; 2-bit RF data interface and 10-bit RF addresses | Default RF allocation: (32 GPR slots + 4 CSR slots) × 32 = 1,152 bits (144 B), including the x0 slot; 576 rows × 2 bits | RF storage is external to the measured wrapper; instruction/data memory capacity is unspecified |", "",
              "These capacities remain unchanged by the transformations. The RF's 10-bit",
              "address ports can encode 1,024 addresses, but its configured storage depth is",
              "576 rows; address width is not allocated capacity. SERV's x0 reads return zero.",
              "The four RAM-backed CSR slots are `mtvec`, `mscratch`, `mepc` and `mtval`.",
              "See [RF storage](experiments/serv-1.4.0/rtl/baseline/serv_rf_ram.v) and",
              "[RF interface](experiments/serv-1.4.0/rtl/baseline/serv_rf_if.v). The 144 B",
              "allocation is an architectural storage requirement, not part of the reported",
              "181 FF and not a measured full CPU-with-RAM area.", "",
              "## 4. Relative scale and orders of magnitude", "",
              "The following ratios use **baselines only**, with SERV = 1.00. They compare",
              "source and physical resources separately.", "",
              "| Module | Code lines / SERV | CLBs / SERV | Area / SERV | Baseline resource scale |",
              "| --- | ---: | ---: | ---: | --- |"]
    serv = cases[-1]["baseline"]
    for case in cases:
        b = case["baseline"]
        lines.append(f"| {case['name']} | {b['source']['code_lines']/serv['source']['code_lines']:.2f}× | "
                     f"{b['clbs']/serv['clbs']:.2f}× | {b['area']/serv['area']:.2f}× | "
                     f"{b['clbs']:.2e} CLBs; {b['area']:.2e} MWTA |")
    sha, int8, cbd = (case["baseline"] for case in cases[:3])
    lines += ["", f"- SERV's baseline source has **{serv['source']['code_lines']/sha['source']['code_lines']:.2f}×** the code lines of SHA-1,",
              f"  **{serv['source']['code_lines']/int8['source']['code_lines']:.2f}×** INT8 MatVec and **{serv['source']['code_lines']/cbd['source']['code_lines']:.2f}×** ML-KEM CBD.",
              "- Baseline source lengths span roughly 10²–10³ code lines (INT8 has 73);",
              "  implemented CLBs span tens for SERV and hundreds for the other modules.",
              "- SERV's area is about 2.74 × 10⁶ MWTA; the others span 1.66 × 10⁷ to",
              "  3.39 × 10⁷ MWTA. This is approximately one order of magnitude in physical",
              "  area, with actual factors between 6.06 and 12.35 under the measured contracts.",
              "- The architectural step is a CPU with instruction decode, ALU, PC, CSR/control,",
              "  memory buses and RF protocol. The physical scope is a compact serial core",
              "  with external storage excluded; source breadth and silicon size describe",
              "  different aspects of the study.", "",
              "## 5. Acceptance status", "",
              "SHA-1, INT8 MatVec and ML-KEM CBD are the three accepted cases. SERV remains a",
              "paused research record: its 64 pairs show a **3.3474% lower composite PPA",
              "estimate**, with **5.8985% lower area**, **5.8835% lower estimated power** and",
              "**1.9478% higher critical-path delay**. The timing regression rejects acceptance;",
              "the 10% objective was not reached and the separate 12-pair certification was",
              "not run. File naming and inclusion in this size comparison do not change that",
              "status. See the [SERV report](RTL-Study-SERV-1.4.0.pdf).", "",
              "## 6. Sources and reproduction", "",
              "Tables are generated by [generate_module_sizes.py](tools/generate_module_sizes.py).",
              "It counts the bundled source files, reads every frozen per-pair resource row,",
              "checks that each sample contains 64 pairs and recomputes geometric mean area.",
              "Logical capacities above are derived from the linked RTL declarations and",
              "selected wrapper parameters. Missing mapped counts remain explicitly missing.", "",
              "| Paired evidence | SHA-256 |", "| --- | --- |"]
    for case in cases:
        lines.append(f"| [{case['name']}]({case['evidence']}) | `{case['digest']}` |")
    lines += ["", "```bash", "python3 tools/generate_module_sizes.py          # update this page and README tables",
              "python3 tools/generate_module_sizes.py --check  # verify that tables are current",
              "python3 verify.py                             # audit all compact packages and checksums",
              "```", "", "Regeneration and verification use Python's standard library and the saved",
              "artifacts. They do not launch EDA or optimization jobs.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    cases = load_cases()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise SystemExit("README must contain one module-size table marker pair")
    prefix, rest = readme.split(START)
    _, suffix = rest.split(END)
    expected = {ROOT / "MODULE-SIZES.md": document(cases),
                ROOT / "README.md": prefix + overview(cases) + suffix}
    for path, content in expected.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"outdated size comparison: {path.relative_to(ROOT)}")
        else:
            path.write_text(content, encoding="utf-8")
    print("Module size comparison: PASS" if args.check else "Updated module size comparison and README tables")


if __name__ == "__main__":
    main()
