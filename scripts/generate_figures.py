#!/usr/bin/env python3
"""Generate publication-ready SVG figures from the certified JSON records."""

from __future__ import annotations

import html
import json
import math
import statistics
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
NAVY = "#102A43"
BLUE = "#2563EB"
TEAL = "#0F9D8A"
ORANGE = "#E87924"
GREEN = "#16845B"
RED = "#C83E4D"
GRAY = "#64748B"
LIGHT = "#E8EEF4"
PALE = "#F6F8FB"
WHITE = "#FFFFFF"


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def text(x: float, y: float, value: object, *, size: int = 18, weight: int = 400,
         fill: str = NAVY, anchor: str = "start", family: str = "Arial, Helvetica, sans-serif") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">'
        f'{html.escape(str(value))}</text>'
    )


def line(x1: float, y1: float, x2: float, y2: float, *, stroke: str = LIGHT,
         width: float = 1, dash: str | None = None) -> str:
    dashed = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{width}"{dashed}/>'
    )


def circle(cx: float, cy: float, r: float, *, fill: str, stroke: str = WHITE,
           width: float = 1.5, opacity: float = 1.0) -> str:
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>'
    )


def rect(x: float, y: float, width: float, height: float, *, fill: str,
         stroke: str = "none", radius: float = 0, opacity: float = 1.0) -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'rx="{radius:.2f}" fill="{fill}" stroke="{stroke}" opacity="{opacity}"/>'
    )


def svg_document(width: int, height: int, title_value: str, description: str,
                 body: Iterable[str]) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            f"<title>{html.escape(title_value)}</title>",
            f"<desc>{html.escape(description)}</desc>",
            rect(0, 0, width, height, fill=WHITE),
            *body,
            "</svg>",
            "",
        ]
    )


def write(name: str, content: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    (FIGURES / name).write_text(content, encoding="utf-8")


def improvement(ratio: float) -> float:
    return 100.0 * (1.0 - ratio)


def certified_profile() -> None:
    champion = load("results/champion-certification.json")
    confidence = champion["statistical_confidence"]
    rows = [
        ("Area", confidence["metrics"]["area_total_mwta"]),
        ("Timing", confidence["metrics"]["critical_path_delay_ns"]),
        ("Energy / block", confidence["metrics"]["energy_per_block_nj"]),
        ("Composite PPA", confidence["composite"]),
    ]
    width, height = 1280, 720
    left, right, top, bottom = 110, 70, 145, 105
    plot_w, plot_h = width - left - right, height - top - bottom
    y_min, y_max = -1.0, 13.5
    xs = [left + plot_w * i / 3 for i in range(4)]

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_h

    body: list[str] = [
        text(left, 48, "Certified PPA improvement vs. baseline", size=30, weight=700),
        text(left, 82, "64 paired, fixed and search-disjoint VPR seeds · lower metric values are better", size=17, fill=GRAY),
        rect(left, sy(0.35), plot_w, sy(-0.35) - sy(0.35), fill=LIGHT, opacity=0.55),
    ]
    for tick in [-1, 0, 3, 6, 9, 12]:
        y = sy(tick)
        body.append(line(left, y, width - right, y, stroke=NAVY if tick == 0 else LIGHT, width=2 if tick == 0 else 1))
        body.append(text(left - 16, y + 6, f"{tick:+.0f}%" if tick else "0%", size=15, fill=GRAY, anchor="end"))
    values: list[tuple[float, float, float]] = []
    for _, item in rows:
        estimate = improvement(float(item["estimate"]))
        low = improvement(float(item["ci95_two_sided"][1]))
        high = improvement(float(item["ci95_two_sided"][0]))
        values.append((estimate, low, high))
    path_points = " ".join(f"{x:.1f},{sy(est):.1f}" for x, (est, _, _) in zip(xs, values))
    body.append(f'<polyline points="{path_points}" fill="none" stroke="{BLUE}" stroke-width="4"/>')
    for index, (x, (label, item), (estimate, low, high)) in enumerate(zip(xs, rows, values)):
        body.extend(
            [
                line(x, sy(low), x, sy(high), stroke=BLUE, width=3),
                line(x - 9, sy(low), x + 9, sy(low), stroke=BLUE, width=3),
                line(x - 9, sy(high), x + 9, sy(high), stroke=BLUE, width=3),
                circle(x, sy(estimate), 8, fill=BLUE),
                text(x, height - 62, label, size=17, weight=700, anchor="middle"),
            ]
        )
        status = "neutral" if low <= 0 <= high else "improved"
        label_y = sy(1.25) if index == 0 else (sy(high) - 18 if estimate < 11 else sy(low) + 30)
        body.append(text(x, label_y, f"{estimate:.2f}% · {status}", size=16, weight=700, fill=GREEN if status == "improved" else ORANGE, anchor="middle"))
        body.append(text(x, label_y + 23, f"95% CI {low:.2f}% to {high:.2f}%", size=13, fill=GRAY, anchor="middle"))
    body.append(text(left, height - 18, "Paired log-ratio estimate. The gray band is a visual ±0.35% vicinity of no change, not an acceptance threshold.", size=13, fill=GRAY))
    write(
        "certified-ppa-profile.svg",
        svg_document(width, height, "Certified PPA improvement", "Area is statistically neutral; timing, energy and composite PPA improve with paired 95 percent confidence intervals.", body),
    )


def paired_seed_distributions() -> None:
    baseline = load("results/baseline-certification.json")
    champion = load("results/champion-certification.json")
    base = {int(row["seed"]): row for row in baseline["per_seed"]}
    cand = {int(row["seed"]): row for row in champion["per_seed"]}
    metrics = [
        ("Area", "area_total_mwta", ORANGE),
        ("Timing", "critical_path_delay_ns", BLUE),
        ("Energy", "energy_per_block_nj", TEAL),
        ("Composite", "composite", GREEN),
    ]
    ratios: dict[str, list[tuple[int, float]]] = {}
    for _, metric, _ in metrics:
        values: list[tuple[int, float]] = []
        for seed in sorted(base):
            if metric == "composite":
                logs = [
                    math.log(float(cand[seed][name]) / float(base[seed][name]))
                    for name in ("area_total_mwta", "critical_path_delay_ns", "energy_per_block_nj")
                ]
                ratio = math.exp(statistics.mean(logs))
            else:
                ratio = float(cand[seed][metric]) / float(base[seed][metric])
            values.append((seed, improvement(ratio)))
        ratios[metric] = values

    width, height = 1280, 780
    left, right, top = 180, 70, 145
    panel_h, gap = 115, 22
    x_min, x_max = -1.5, 16.0
    plot_w = width - left - right

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    body: list[str] = [
        text(left, 48, "Every paired certification seed", size=30, weight=700),
        text(left, 82, "Candidate improvement relative to the same baseline seed · right is better", size=17, fill=GRAY),
    ]
    for index, (label, metric, color) in enumerate(metrics):
        y0 = top + index * (panel_h + gap)
        body.append(rect(left, y0, plot_w, panel_h, fill=PALE, radius=8))
        body.append(line(sx(0), y0, sx(0), y0 + panel_h, stroke=NAVY, width=2))
        body.append(text(left - 24, y0 + panel_h / 2 + 6, label, size=18, weight=700, anchor="end"))
        for tick in [0, 5, 10, 15]:
            body.append(line(sx(tick), y0, sx(tick), y0 + panel_h, stroke=LIGHT, width=1))
        for seed, value in ratios[metric]:
            jitter = ((seed * 37) % 83) / 83.0
            cy = y0 + 14 + jitter * (panel_h - 28)
            body.append(circle(sx(value), cy, 4.3, fill=color, stroke=WHITE, width=0.8, opacity=0.76))
        ci = champion["statistical_confidence"]["composite" if metric == "composite" else "metrics"]
        if metric != "composite":
            ci = ci[metric]
        estimate = improvement(float(ci["estimate"]))
        low = improvement(float(ci["ci95_two_sided"][1]))
        high = improvement(float(ci["ci95_two_sided"][0]))
        y_bar = y0 + panel_h - 10
        body.append(line(sx(low), y_bar, sx(high), y_bar, stroke=NAVY, width=5))
        body.append(circle(sx(estimate), y_bar, 6, fill=NAVY, stroke=WHITE, width=1))
        body.append(text(width - right - 12, y0 + 25, f"estimate {estimate:.2f}% · 95% CI {low:.2f}% to {high:.2f}%", size=14, fill=NAVY, anchor="end"))
    axis_y = top + 4 * (panel_h + gap) - gap + 30
    body.append(line(left, axis_y, width - right, axis_y, stroke=NAVY, width=1.5))
    for tick in [-1, 0, 5, 10, 15]:
        body.append(line(sx(tick), axis_y, sx(tick), axis_y + 8, stroke=NAVY, width=1.5))
        body.append(text(sx(tick), axis_y + 29, f"{tick:+.0f}%" if tick else "0%", size=14, fill=GRAY, anchor="middle"))
    body.append(text((left + width - right) / 2, height - 24, "Improvement relative to paired baseline seed", size=16, weight=700, anchor="middle"))
    write(
        "paired-seed-distributions.svg",
        svg_document(width, height, "Paired certification seed distributions", "Each dot is one of 64 paired seeds. Timing, energy, and composite metrics improve in all seeds while area is mixed and neutral.", body),
    )


def search_evolution() -> None:
    history = load("results/search-history.json")
    campaign = load("results/campaign-decision.json")
    by_generation: dict[int, list[dict]] = {}
    for row in history["submissions"]:
        if row["provisional_score"] is not None and row["formal_status"] == "pass":
            by_generation.setdefault(int(row["generation"]), []).append(row)
    current = 0.9742327093555855
    incumbent: list[tuple[int, float]] = [(0, current)]
    selected_ids: dict[int, str] = {}
    for generation in range(1, 21):
        candidates = by_generation.get(generation, [])
        if candidates:
            best = min(candidates, key=lambda item: float(item["provisional_score"]))
            if float(best["provisional_score"]) < current:
                current = float(best["provisional_score"])
                selected_ids[generation] = str(best["candidate_id"])
        incumbent.append((generation, current))

    width, height = 1280, 700
    left, right, top, bottom = 100, 80, 140, 120
    plot_w, plot_h = width - left - right, height - top - bottom
    y_min, y_max = 0.925, 0.982

    def sx(generation: int) -> float:
        return left + plot_w * generation / 20

    def sy(score: float) -> float:
        return top + (y_max - score) / (y_max - y_min) * plot_h

    body: list[str] = [
        text(left, 48, "Search progression and certification correction", size=30, weight=700),
        text(left, 82, "Five-seed ranking guides search; only fixed 64-seed evidence selects the champion", size=17, fill=GRAY),
    ]
    for score in [0.93, 0.94, 0.95, 0.96, 0.97, 0.98]:
        body.append(line(left, sy(score), width - right, sy(score), stroke=LIGHT))
        body.append(text(left - 12, sy(score) + 5, f"{score:.2f}", size=14, fill=GRAY, anchor="end"))
    for generation in [0, 5, 10, 15, 20]:
        body.append(line(sx(generation), top, sx(generation), top + plot_h, stroke=LIGHT))
        body.append(text(sx(generation), top + plot_h + 30, generation, size=14, fill=GRAY, anchor="middle"))
    path = " ".join(f"{sx(g):.1f},{sy(score):.1f}" for g, score in incumbent)
    body.append(f'<polyline points="{path}" fill="none" stroke="{BLUE}" stroke-width="4"/>')
    for generation, candidate_id in selected_ids.items():
        score = dict(incumbent)[generation]
        body.append(circle(sx(generation), sy(score), 7, fill=BLUE))
        if generation in {1, 9, 15, 16}:
            body.append(text(sx(generation), sy(score) - 17, candidate_id, size=13, weight=700, anchor="middle"))

    # The provisional leader g16 was not accepted; g15 is the certified champion.
    g16 = campaign["comparisons_to_previous_incumbent"]["ed8a5913c1a5ddf29da8649b24f27dcdefcfa0b07ba2459a401675ef3cfb1bb6"]
    g15 = campaign["comparisons_to_previous_incumbent"]["743e6c9ffcca6f00d35d5e73ba6f6478a9133a0c55a471c16d6e59d831aeeabc"]
    box_y = top + plot_h + 62
    body.append(rect(left + 610, box_y - 32, 480, 62, fill=PALE, radius=8))
    body.append(text(left + 630, box_y - 7, f"g16 provisional leader → {g16['decision'].replace('_', ' ')}", size=15, weight=700, fill=RED))
    body.append(text(left + 630, box_y + 18, f"g15 certified champion → score {g15['score']:.4f} vs previous incumbent", size=15, weight=700, fill=GREEN))
    body.append(text(left, height - 22, "Provisional score (lower is better)", size=16, weight=700))
    write(
        "search-evolution.svg",
        svg_document(width, height, "Search and certification progression", "The five-seed search initially favors generation 16, but 64-seed certification rejects it for area regression and selects generation 15.", body),
    )


def verification_pipeline() -> None:
    width, height = 1400, 410
    steps = [
        ("Candidate", "sha.v frozen by SHA-256"),
        ("Structural", "interface · lint · synthesis"),
        ("Functional", "cycle trace · NIST"),
        ("Formal", "unbounded EQY · fail closed"),
        ("Search", "5 paired seeds · ranking only"),
        ("Certify", "64 disjoint paired seeds"),
        ("Decision", "confidence gates · champion"),
    ]
    margin, gap = 45, 22
    box_w = (width - 2 * margin - gap * (len(steps) - 1)) / len(steps)
    body: list[str] = [
        text(margin, 46, "Correctness precedes PPA", size=30, weight=700),
        text(margin, 78, "The candidate generator is replaceable; the evaluator contract is fixed", size=17, fill=GRAY),
    ]
    y, box_h = 130, 150
    for index, (heading, sub) in enumerate(steps):
        x = margin + index * (box_w + gap)
        fill = "#EAF2FF" if heading in {"Search", "Certify"} else "#E9F7F4" if heading in {"Functional", "Formal"} else PALE
        body.append(rect(x, y, box_w, box_h, fill=fill, stroke=LIGHT, radius=10))
        body.append(text(x + box_w / 2, y + 53, heading, size=18, weight=700, anchor="middle"))
        words = sub.split(" · ")
        for line_index, word in enumerate(words):
            body.append(text(x + box_w / 2, y + 88 + line_index * 24, word, size=13, fill=GRAY, anchor="middle"))
        body.append(circle(x + 23, y + 22, 12, fill=NAVY))
        body.append(text(x + 23, y + 27, index + 1, size=13, weight=700, fill=WHITE, anchor="middle"))
        if index < len(steps) - 1:
            x1, x2, cy = x + box_w + 4, x + box_w + gap - 4, y + box_h / 2
            body.append(line(x1, cy, x2, cy, stroke=NAVY, width=2))
            body.append(f'<path d="M {x2 - 8:.1f} {cy - 6:.1f} L {x2:.1f} {cy:.1f} L {x2 - 8:.1f} {cy + 6:.1f}" fill="none" stroke="{NAVY}" stroke-width="2"/>')
    body.append(text(margin, 350, "Any failed or inconclusive correctness gate invalidates the candidate before routed PPA is spent.", size=17, weight=700, fill=RED))
    write(
        "verification-pipeline.svg",
        svg_document(width, height, "Verification-first optimization pipeline", "Seven stage flow from hash-frozen RTL through correctness and formal equivalence to search, certification, and evidence-based champion selection.", body),
    )


def netlist_evidence() -> None:
    data = load("results/netlist-seed20-summary.json")
    width, height = 1100, 500
    body: list[str] = [
        text(70, 50, "What changed after synthesis and routing?", size=30, weight=700),
        text(70, 82, "Representative seed 20 · same architecture and channel width", size=17, fill=GRAY),
    ]
    rows = [
        ("Timing graph levels", "timing_graph_levels", "levels", True),
        ("Critical path", "critical_path_delay_ns", "ns", True),
        ("CLB blocks", "clb_blocks", "CLB", True),
        ("ABC .names nodes", "abc_names_nodes", "nodes", None),
    ]
    x_label, x_base, x_champ = 90, 540, 850
    body.extend([
        text(x_base, 125, "Baseline", size=16, weight=700, fill=GRAY, anchor="middle"),
        text(x_champ, 125, "Champion", size=16, weight=700, fill=GREEN, anchor="middle"),
    ])
    for index, (label, key, unit, lower_better) in enumerate(rows):
        y = 175 + index * 72
        base = float(data["baseline"][key])
        champ = float(data["champion"][key])
        delta = 100 * (champ / base - 1)
        color = GRAY if lower_better is None else (GREEN if (delta < 0) == lower_better else ORANGE)
        body.append(line(70, y + 30, 1030, y + 30, stroke=LIGHT))
        body.append(text(x_label, y, label, size=17, weight=700))
        base_fmt = f"{base:.4f}" if "delay" in key else f"{base:.0f}"
        champ_fmt = f"{champ:.4f}" if "delay" in key else f"{champ:.0f}"
        body.append(text(x_base, y, f"{base_fmt} {unit}", size=18, anchor="middle"))
        body.append(text(x_champ, y, f"{champ_fmt} {unit}", size=18, weight=700, fill=color, anchor="middle"))
        body.append(text(1030, y, f"{delta:+.2f}%", size=15, weight=700, fill=color, anchor="end"))
    body.append(text(70, 474, "The champion uses slightly more mapped logic nodes but packs into one fewer CLB and reduces the routed timing depth.", size=14, fill=GRAY))
    write(
        "netlist-evidence.svg",
        svg_document(width, height, "Post-synthesis and post-route evidence", "Seed 20 shows fewer timing graph levels, a shorter critical path, one fewer CLB, and slightly more ABC names nodes.", body),
    )


def main() -> int:
    certified_profile()
    paired_seed_distributions()
    search_evolution()
    verification_pipeline()
    netlist_evidence()
    for path in sorted(FIGURES.glob("*.svg")):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
