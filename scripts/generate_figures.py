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
NAVY = "#0A0A0A"
BLUE = "#0A84FF"
TEAL = BLUE
ORANGE = "#6A6A6A"
GREEN = BLUE
RED = "#0A0A0A"
GRAY = "#6A6A6A"
LIGHT = "#E5E5E5"
PALE = "#F8FBFF"
WHITE = "#FFFFFF"
ARROW_DEFS = (
    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{GRAY}"/></marker></defs>'
)


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def text(x: float, y: float, value: object, *, size: int = 18, weight: int = 400,
         fill: str = NAVY, anchor: str = "start", family: str = "Inter, Arial, Helvetica, sans-serif") -> str:
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


def arrow(x1: float, y1: float, x2: float, y2: float, *, stroke: str = GRAY,
          width: float = 2) -> str:
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{width}" marker-end="url(#arrow)"/>'
    )


def node(body: list[str], x: float, y: float, width: float, height: float,
         label: str, *, accepted: bool = False, input_node: bool = False) -> None:
    fill = WHITE if input_node else ("#EAF2FF" if accepted else PALE)
    stroke = BLUE if accepted and not input_node else LIGHT
    body.append(rect(x, y, width, height, fill=fill, stroke=stroke, radius=7))
    body.append(text(x + width / 2, y + height / 2 + 6, label, size=17,
                     weight=700 if not input_node else 400, anchor="middle"))


def comparison_panels(body: list[str], title_value: str) -> None:
    body.extend([
        ARROW_DEFS,
        text(55, 48, title_value, size=30, weight=700),
        rect(40, 78, 640, 365, fill=WHITE, stroke=LIGHT, radius=10),
        rect(720, 78, 640, 365, fill=WHITE, stroke=LIGHT, radius=10),
        text(360, 116, "Corrected baseline", size=19, weight=700, fill=GRAY, anchor="middle"),
        text(1040, 116, "Accepted RTL", size=19, weight=700, fill=BLUE, anchor="middle"),
    ])


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
    accepted = load("results/accepted-certification.json")
    confidence = accepted["statistical_confidence"]
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
        text(left, 82, "64 fixed, paired VPR seeds · lower metric values are better", size=17, fill=GRAY),
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
    for x, (label, _), (estimate, low, high) in zip(xs, rows, values):
        body.extend(
            [
                line(x, sy(low), x, sy(high), stroke=BLUE, width=3),
                line(x - 9, sy(low), x + 9, sy(low), stroke=BLUE, width=3),
                line(x - 9, sy(high), x + 9, sy(high), stroke=BLUE, width=3),
                circle(x, sy(estimate), 8, fill=BLUE),
                text(x, height - 62, label, size=17, weight=700, anchor="middle"),
            ]
        )
    body.append(text(left, height - 18, "Paired log-ratio estimate. The gray band is a visual ±0.35% vicinity of no change, not an acceptance threshold.", size=13, fill=GRAY))
    write(
        "certified-ppa-profile.svg",
        svg_document(width, height, "Certified PPA improvement", "Area is statistically neutral; timing, energy and composite PPA improve with paired 95 percent confidence intervals.", body),
    )


def paired_seed_distributions() -> None:
    baseline = load("results/baseline-certification.json")
    accepted = load("results/accepted-certification.json")
    base = {int(row["seed"]): row for row in baseline["per_seed"]}
    cand = {int(row["seed"]): row for row in accepted["per_seed"]}
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
        text(left, 82, "Accepted RTL relative to the same baseline seed · right is better", size=17, fill=GRAY),
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
        ci = accepted["statistical_confidence"]["composite" if metric == "composite" else "metrics"]
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


def verification_pipeline() -> None:
    width, height = 1400, 410
    steps = [
        ("Accepted RTL", "sha.v frozen by SHA-256"),
        ("Structural", "interface · lint · synthesis"),
        ("Functional", "cycle trace · NIST"),
        ("Formal", "unbounded EQY · fail closed"),
        ("PPA", "64 fixed paired seeds"),
        ("Decision", "metric and confidence gates"),
    ]
    margin, gap = 45, 22
    box_w = (width - 2 * margin - gap * (len(steps) - 1)) / len(steps)
    body: list[str] = [
        text(margin, 46, "Correctness precedes PPA", size=30, weight=700),
        text(margin, 78, "The accepted RTL is checked under one fixed functional and physical contract", size=17, fill=GRAY),
    ]
    y, box_h = 130, 150
    for index, (heading, sub) in enumerate(steps):
        x = margin + index * (box_w + gap)
        fill = "#EAF2FF" if heading in {"PPA", "Decision"} else PALE
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
    body.append(text(margin, 350, "Any failed or inconclusive correctness gate invalidates the RTL before routed PPA is evaluated.", size=17, weight=700, fill=RED))
    write(
        "verification-pipeline.svg",
        svg_document(width, height, "Verification-first optimization pipeline", "Six-stage flow from hash-frozen RTL through correctness and formal equivalence to paired PPA and an evidence-based acceptance decision.", body),
    )


def choose_rewrite() -> None:
    width, height = 1400, 485
    body: list[str] = []
    comparison_panels(body, "Rewrite 1 · SHA-1 choose function")

    for x, y, label in [(75, 145, "B"), (75, 215, "C"), (75, 305, "NOT B"), (75, 375, "D")]:
        node(body, x, y, 92, 46, label, input_node=True)
    node(body, 285, 175, 125, 54, "AND B·C")
    node(body, 285, 335, 125, 54, "AND ¬B·D")
    node(body, 495, 255, 100, 54, "XOR")
    node(body, 610, 255, 52, 54, "f1")
    body.extend([
        arrow(167, 168, 285, 190), arrow(167, 238, 285, 214),
        arrow(167, 328, 285, 350), arrow(167, 398, 285, 374),
        arrow(410, 202, 495, 270), arrow(410, 362, 495, 294),
        arrow(595, 282, 610, 282),
    ])

    for x, y, label in [(755, 145, "B"), (755, 215, "D"), (755, 305, "NOT B"), (755, 375, "C")]:
        node(body, x, y, 92, 46, label, input_node=True)
    node(body, 965, 175, 125, 54, "OR B+D", accepted=True)
    node(body, 965, 335, 125, 54, "OR ¬B+C", accepted=True)
    node(body, 1175, 255, 100, 54, "AND", accepted=True)
    node(body, 1290, 255, 52, 54, "f1", accepted=True)
    body.extend([
        arrow(847, 168, 965, 190), arrow(847, 238, 965, 214),
        arrow(847, 328, 965, 350), arrow(847, 398, 965, 374),
        arrow(1090, 202, 1175, 270), arrow(1090, 362, 1175, 294),
        arrow(1275, 282, 1290, 282),
    ])
    write(
        "rewrite-1-choose.svg",
        svg_document(width, height, "SHA-1 choose rewrite", "Corrected baseline and accepted Boolean networks for the SHA-1 choose function in sha.v line 129.", body),
    )


def majority_rewrite() -> None:
    width, height = 1400, 485
    body: list[str] = []
    comparison_panels(body, "Rewrite 2 · factored SHA-1 majority")

    for x, y, label in [(70, 150, "B"), (70, 245, "C"), (70, 340, "D")]:
        node(body, x, y, 82, 46, label, input_node=True)
    node(body, 255, 145, 115, 50, "AND B·C")
    node(body, 255, 240, 115, 50, "AND C·D")
    node(body, 255, 335, 115, 50, "AND B·D")
    node(body, 445, 190, 88, 50, "XOR")
    node(body, 550, 285, 88, 50, "XOR")
    node(body, 640, 285, 30, 50, "f3")
    body.extend([
        arrow(152, 173, 255, 162), arrow(152, 268, 255, 180),
        arrow(152, 268, 255, 257), arrow(152, 363, 255, 275),
        arrow(152, 173, 255, 352), arrow(152, 363, 255, 370),
        arrow(370, 170, 445, 207), arrow(370, 265, 445, 223),
        arrow(533, 215, 550, 302), arrow(370, 360, 550, 318),
        arrow(638, 310, 640, 310),
    ])

    for x, y, label in [(755, 150, "B"), (755, 245, "C"), (755, 340, "D")]:
        node(body, x, y, 82, 46, label, input_node=True)
    node(body, 930, 150, 115, 50, "AND B·D", accepted=True)
    node(body, 930, 315, 115, 50, "XOR B⊕D", accepted=True)
    node(body, 1090, 285, 135, 50, "AND C·(B⊕D)", accepted=True)
    node(body, 1245, 220, 78, 50, "OR", accepted=True)
    node(body, 1330, 220, 30, 50, "f3", accepted=True)
    body.extend([
        arrow(837, 173, 930, 167), arrow(837, 363, 930, 183),
        arrow(837, 173, 930, 332), arrow(837, 363, 930, 348),
        arrow(837, 268, 1090, 302), arrow(1045, 340, 1090, 318),
        arrow(1045, 175, 1245, 237), arrow(1225, 310, 1245, 253),
        arrow(1323, 245, 1330, 245),
    ])
    write(
        "rewrite-2-majority.svg",
        svg_document(width, height, "SHA-1 majority rewrite", "Corrected baseline and accepted Boolean networks for the SHA-1 majority function in sha.v line 131.", body),
    )


def xor_rewrite() -> None:
    width, height = 1400, 485
    body: list[str] = []
    comparison_panels(body, "Rewrite 3 · balanced message-schedule XOR")

    for x, y, label in [(70, 145, "W13"), (70, 220, "W8"), (70, 295, "W2"), (70, 370, "W0")]:
        node(body, x, y, 82, 46, label, input_node=True)
    node(body, 245, 175, 88, 50, "XOR")
    node(body, 405, 245, 88, 50, "XOR")
    node(body, 560, 315, 88, 50, "XOR")
    body.extend([
        arrow(152, 168, 245, 190), arrow(152, 243, 245, 210),
        arrow(333, 200, 405, 260), arrow(152, 318, 405, 280),
        arrow(493, 270, 560, 330), arrow(152, 393, 560, 350),
    ])

    for x, y, label in [(750, 145, "W13"), (750, 220, "W8"), (750, 295, "W2"), (750, 370, "W0")]:
        node(body, x, y, 82, 46, label, input_node=True)
    node(body, 950, 175, 115, 50, "XOR pair", accepted=True)
    node(body, 950, 335, 115, 50, "XOR pair", accepted=True)
    node(body, 1180, 255, 115, 50, "Final XOR", accepted=True)
    body.extend([
        arrow(832, 168, 950, 190), arrow(832, 243, 950, 210),
        arrow(832, 318, 950, 350), arrow(832, 393, 950, 370),
        arrow(1065, 200, 1180, 270), arrow(1065, 360, 1180, 290),
    ])
    write(
        "rewrite-3-xor.svg",
        svg_document(width, height, "Balanced XOR rewrite", "Serial and explicitly balanced XOR groupings for the message schedule in sha.v line 141.", body),
    )


def accumulator_rewrite() -> None:
    width, height = 1400, 485
    body: list[str] = []
    comparison_panels(body, "Rewrite 4 · reassociated 32-bit accumulator")

    for x, y, label in [(65, 135, "R"), (65, 200, "f"), (65, 265, "E"), (65, 330, "Kt"), (65, 395, "Wt")]:
        node(body, x, y, 72, 42, label, input_node=True)
    node(body, 220, 165, 72, 48, "+")
    node(body, 345, 230, 72, 48, "+")
    node(body, 470, 295, 72, 48, "+")
    node(body, 595, 360, 72, 48, "+")
    body.extend([
        arrow(137, 156, 220, 178), arrow(137, 221, 220, 198),
        arrow(292, 189, 345, 243), arrow(137, 286, 345, 263),
        arrow(417, 254, 470, 308), arrow(137, 351, 470, 328),
        arrow(542, 319, 595, 373), arrow(137, 416, 595, 393),
    ])

    for x, y, label in [(745, 135, "R"), (745, 200, "f"), (745, 285, "E"), (745, 350, "Kt"), (745, 415, "Wt")]:
        node(body, x, y, 72, 42, label, input_node=True)
    node(body, 920, 165, 105, 48, "R + f", accepted=True)
    node(body, 920, 315, 105, 48, "E + Kt", accepted=True)
    node(body, 1080, 365, 105, 48, "+ Wt", accepted=True)
    node(body, 1240, 255, 105, 48, "Final +", accepted=True)
    body.extend([
        arrow(817, 156, 920, 178), arrow(817, 221, 920, 198),
        arrow(817, 306, 920, 328), arrow(817, 371, 920, 348),
        arrow(1025, 339, 1080, 378), arrow(817, 436, 1080, 398),
        arrow(1025, 189, 1240, 268), arrow(1185, 389, 1240, 290),
    ])
    write(
        "rewrite-4-accumulator.svg",
        svg_document(width, height, "32-bit accumulator rewrite", "Serial and grouped modulo-2^32 accumulator structures for sha.v line 144.", body),
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
    x_label, x_base, x_accepted = 90, 540, 850
    body.extend([
        text(x_base, 125, "Baseline", size=16, weight=700, fill=GRAY, anchor="middle"),
        text(x_accepted, 125, "Accepted RTL", size=16, weight=700, fill=BLUE, anchor="middle"),
    ])
    for index, (label, key, unit, lower_better) in enumerate(rows):
        y = 175 + index * 72
        base = float(data["baseline"][key])
        accepted = float(data["accepted"][key])
        delta = 100 * (accepted / base - 1)
        color = GRAY if lower_better is None else (GREEN if (delta < 0) == lower_better else ORANGE)
        body.append(line(70, y + 30, 1030, y + 30, stroke=LIGHT))
        body.append(text(x_label, y, label, size=17, weight=700))
        base_fmt = f"{base:.4f}" if "delay" in key else f"{base:.0f}"
        accepted_fmt = f"{accepted:.4f}" if "delay" in key else f"{accepted:.0f}"
        body.append(text(x_base, y, f"{base_fmt} {unit}", size=18, anchor="middle"))
        body.append(text(x_accepted, y, f"{accepted_fmt} {unit}", size=18, weight=700, fill=color, anchor="middle"))
        body.append(text(1030, y, f"{delta:+.2f}%", size=15, weight=700, fill=color, anchor="end"))
    body.append(text(70, 474, "The accepted RTL uses slightly more mapped logic nodes but packs into one fewer CLB and reduces the routed timing depth.", size=14, fill=GRAY))
    write(
        "netlist-evidence.svg",
        svg_document(width, height, "Post-synthesis and post-route evidence", "Seed 20 shows fewer timing graph levels, a shorter critical path, one fewer CLB, and slightly more ABC names nodes.", body),
    )


def main() -> int:
    certified_profile()
    paired_seed_distributions()
    verification_pipeline()
    choose_rewrite()
    majority_rewrite()
    xor_rewrite()
    accumulator_rewrite()
    netlist_evidence()
    for path in sorted(FIGURES.glob("*.svg")):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
