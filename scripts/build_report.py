#!/usr/bin/env python3
"""Build the client-facing PDF reports from the certified repository data."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
OUTPUT_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"

NAVY = colors.HexColor("#0A0A0A")
BLUE = colors.HexColor("#0A84FF")
TEAL = BLUE
ORANGE = colors.HexColor("#6A6A6A")
SLATE = colors.HexColor("#6A6A6A")
PALE = colors.HexColor("#F8FBFF")
GRID = colors.HexColor("#E5E5E5")
WHITE = colors.white


def load_json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def register_fonts() -> tuple[str, str, str]:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    bold_candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
    ]
    mono_candidates = [
        Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
        Path("/Library/Fonts/Courier New.ttf"),
    ]
    regular = next((path for path in candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    mono = next((path for path in mono_candidates if path.exists()), None)
    if regular and bold:
        pdfmetrics.registerFont(TTFont("CaseSans", str(regular)))
        pdfmetrics.registerFont(TTFont("CaseSans-Bold", str(bold)))
        if mono:
            pdfmetrics.registerFont(TTFont("CaseMono", str(mono)))
        return "CaseSans", "CaseSans-Bold", "CaseMono" if mono else "Courier"
    return "Helvetica", "Helvetica-Bold", "Courier"


REGULAR, BOLD, MONO = register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=9.4,
            leading=13.2,
            textColor=NAVY,
            spaceAfter=3.2 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=7.6,
            leading=10.2,
            textColor=SLATE,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=7.4,
            leading=9.8,
            textColor=SLATE,
            alignment=TA_CENTER,
            spaceBefore=1.2 * mm,
            spaceAfter=2.5 * mm,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=BOLD,
            fontSize=20,
            leading=23,
            textColor=NAVY,
            spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=BOLD,
            fontSize=14,
            leading=17,
            textColor=NAVY,
            spaceBefore=2 * mm,
            spaceAfter=3 * mm,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName=BOLD,
            fontSize=10.5,
            leading=13,
            textColor=TEAL,
            spaceBefore=1.5 * mm,
            spaceAfter=2 * mm,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=BOLD,
            fontSize=28,
            leading=31,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=6 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=13,
            leading=18,
            textColor=SLATE,
            spaceAfter=4 * mm,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName=BOLD,
            fontSize=12,
            leading=16,
            textColor=NAVY,
            spaceAfter=0,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName=MONO,
            fontSize=7.2,
            leading=9.3,
            textColor=NAVY,
            leftIndent=3 * mm,
            rightIndent=3 * mm,
            borderColor=GRID,
            borderWidth=0.5,
            borderPadding=3 * mm,
            backColor=colors.HexColor("#F7FAFC"),
            spaceBefore=1 * mm,
            spaceAfter=3 * mm,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=6.7,
            leading=8,
            textColor=SLATE,
        ),
    }


ST = styles()


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, ST[style])


def bullet(text: str) -> Paragraph:
    return Paragraph(f"&#8226;&nbsp;&nbsp;{text}", ST["body"])


def callout(text: str, accent=BLUE) -> Table:
    table = Table([[P(text, "callout")]], colWidths=[166 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.8, accent),
                ("LINEBEFORE", (0, 0), (0, -1), 4, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]
        )
    )
    return table


def data_table(rows: list[list[str]], widths: list[float], *, header: bool = True) -> Table:
    converted = []
    for row_index, row in enumerate(rows):
        converted.append(
            [
                Paragraph(
                    str(value),
                    ParagraphStyle(
                        f"Cell-{row_index}",
                        parent=ST["small"],
                        fontName=BOLD if header and row_index == 0 else REGULAR,
                        textColor=WHITE if header and row_index == 0 else NAVY,
                        alignment=TA_LEFT,
                    ),
                )
                for value in row
            ]
        )
    table = Table(converted, colWidths=[width * mm for width in widths], repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.1 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.1 * mm),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
        if len(rows) > 1:
            commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]))
    table.setStyle(TableStyle(commands))
    return table


def render_svg(svg_name: str, width_px: int = 2100) -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    source = ROOT / "figures" / svg_name
    target = TMP_DIR / f"{Path(svg_name).stem}-report.png"
    renderer = shutil.which("rsvg-convert")
    if renderer is None:
        raise RuntimeError("rsvg-convert is required to embed generated SVG figures")
    subprocess.run(
        [renderer, "-w", str(width_px), str(source), "-o", str(target)],
        check=True,
    )
    return target


def figure(svg_name: str, width_mm: float, caption: str, *, max_height_mm: float = 112) -> list:
    path = render_svg(svg_name)
    image = Image(str(path))
    scale = min(
        (width_mm * mm) / image.imageWidth,
        (max_height_mm * mm) / image.imageHeight,
    )
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    return [image, P(caption, "caption")]


def equation(svg_name: str, width_mm: float) -> list:
    path = render_svg(svg_name, width_px=1500)
    image = Image(str(path))
    scale = (width_mm * mm) / image.imageWidth
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    image.hAlign = "CENTER"
    return [Spacer(1, 1.5 * mm), image, Spacer(1, 3.5 * mm)]


class ReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, title: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=22 * mm,
            rightMargin=22 * mm,
            topMargin=21 * mm,
            bottomMargin=18 * mm,
            title=title,
            author="Göther Labs",
            subject="Evaluated technical improvement: SHA-1 RTL optimization on VTR",
            creator="rtl-optimization-case-study reproducible report builder",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates(
            [
                PageTemplate(id="body", frames=[frame], onPage=self._body_page),
            ]
        )

    def _body_page(self, canvas, doc):
        canvas.saveState()
        page_number = canvas.getPageNumber()
        if page_number == 1:
            canvas.setFillColor(WHITE)
            canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
            canvas.setFillColor(BLUE)
            canvas.rect(0, 0, 7 * mm, A4[1], fill=1, stroke=0)
        else:
            canvas.setStrokeColor(GRID)
            canvas.setLineWidth(0.4)
            canvas.line(22 * mm, A4[1] - 14 * mm, A4[0] - 22 * mm, A4[1] - 14 * mm)
            canvas.setFont(REGULAR, 6.8)
            canvas.setFillColor(SLATE)
            canvas.drawString(22 * mm, A4[1] - 10.5 * mm, "Göther Labs / Evaluated technical improvement")
            canvas.drawRightString(A4[0] - 22 * mm, 10 * mm, f"{page_number}")
            canvas.drawString(22 * mm, 10 * mm, "SHA-1 RTL optimization on VTR · 5 August 2026")
        canvas.restoreState()


class InvariantCanvas(Canvas):
    """ReportLab canvas with stable document IDs and timestamps."""

    def __init__(self, *args, **kwargs):
        kwargs["invariant"] = 1
        super().__init__(*args, **kwargs)


def cover_story(title: str, subtitle: str, outcome: str) -> list:
    return [
        Spacer(1, 24 * mm),
        P("Göther Labs / Evaluated technical improvement", "cover_subtitle"),
        P(title, "cover_title"),
        P(subtitle, "cover_subtitle"),
        Spacer(1, 14 * mm),
        Table(
            [[Paragraph(outcome, ParagraphStyle("CoverOutcome", parent=ST["callout"], textColor=NAVY, fontSize=16, leading=22))]],
            colWidths=[150 * mm],
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1.1, BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 7 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7 * mm),
                ]
            ),
        ),
        Spacer(1, 44 * mm),
        P("Prepared by Göther Labs", "cover_subtitle"),
        P("Evidence snapshot: 5 August 2026", "cover_subtitle"),
        Spacer(1, 5 * mm),
        Paragraph(
            "Academic open-FPGA estimate. Not ASIC signoff, a commercial FPGA result, or manufactured silicon.",
            ParagraphStyle("CoverFine", parent=ST["small"], textColor=SLATE),
        ),
        PageBreak(),
    ]


RESULT_ROWS = [
    ["Metric", "Baseline median", "Accepted RTL median", "Paired improvement (95% CI)"],
    ["Total area", "16,614,693 MWTA", "16,614,693 MWTA", "+0.03% (-0.04%, +0.09%) · neutral"],
    ["Critical path", "15.0054 ns", "13.28085 ns", "+11.43% (+10.87%, +11.98%)"],
    ["Energy / block", "12.3896 nJ", "11.6399 nJ", "+6.14% (+5.77%, +6.52%)"],
    ["Composite PPA", "1.000000", "0.940188", "+5.98% (+5.69%, +6.27%)"],
]


DIFF = html.escape(
    "sha.v:129  - assign SHA1_f1_BCD = (B & C) ^ (~B & D);\n"
    "sha.v:129  + assign SHA1_f1_BCD = (B | D) & ((~B) | C);\n\n"
    "sha.v:131  - assign SHA1_f3_BCD = (B & C) ^ (C & D) ^ (B & D);\n"
    "sha.v:131  + assign SHA1_f3_BCD = (B & D) | (C & (B ^ D));\n\n"
    "sha.v:141  - assign SHA1_Wt_1 = W13 ^ W8 ^ W2 ^ W0;\n"
    "sha.v:141  + assign SHA1_Wt_1 = (W13 ^ W8) ^ (W2 ^ W0);\n\n"
    "sha.v:144  - assign next_A = {A[26:0],A[31:27]} + SHA1_ft_BCD + E + Kt + Wt;\n"
    "sha.v:144  + assign next_A = ({A[26:0],A[31:27]} + SHA1_ft_BCD) + (E + Kt + Wt);"
).replace("\n", "<br/>")


def build_executive(path: Path) -> None:
    doc = ReportDocTemplate(str(path), "Executive summary - SHA-1 RTL optimization on VTR")
    story = cover_story(
        "SHA-1 RTL optimization on VTR",
        "Executive result · open 45 nm FPGA proxy",
        "5.98% lower estimated composite PPA across 64 paired implementations",
    )
    story += [
        P("The accepted result", "h1"),
        callout(
            "Four cycle-equivalent RTL rewrites improve critical-path delay by 11.43% and workload energy by 6.14%, while total estimated area remains statistically neutral.",
            TEAL,
        ),
        Spacer(1, 5 * mm),
        data_table(RESULT_ROWS, [34, 32, 32, 68]),
        Spacer(1, 5 * mm),
    ]
    story += figure(
        "certified-ppa-profile.svg",
        166,
        "Paired log-ratio estimates over 64 fixed VPR seeds. Positive values are improvements.",
        max_height_mm=68,
    )
    story += [
        P("Why it is credible", "h2"),
        P(
            "Only sha.v was editable. NIST conformance and cycle tests passed before PPA; pinned EQY proved sequential equivalence; and a 500-mutation qualification rejected all 482 functionally distinguishable cases. Baseline and accepted RTL were then evaluated under the same 64 fixed implementation seeds.",
        ),
        callout(
            "Claims boundary: this is an open academic FPGA estimate at VTR PTM45, not an ASIC or commercial-FPGA result. SHA-1 is used only as a legacy benchmark.",
            ORANGE,
        ),
    ]
    doc.build(story, canvasmaker=InvariantCanvas)


def build_technical(path: Path) -> None:
    doc = ReportDocTemplate(str(path), "SHA-1 RTL optimization on VTR")
    story = cover_story(
        "SHA-1 RTL optimization on VTR",
        "Technical report · reproducible open 45 nm FPGA proxy",
        "Four cycle-equivalent RTL rewrites reduce estimated composite PPA by 5.98%",
    )

    story += [
        P("1. Executive result", "h1"),
        callout(
            "The accepted RTL reduces the equal-weight area-delay-energy score by 5.98% (95% CI: 5.69% to 6.27%) without changing the module interface, state-visible behavior, latency or register count.",
            TEAL,
        ),
        Spacer(1, 5 * mm),
        data_table(RESULT_ROWS, [34, 32, 32, 68]),
        Spacer(1, 5 * mm),
    ]
    story += figure(
        "certified-ppa-profile.svg",
        166,
        "Figure 1. Certified paired improvements. Area is neutral because its interval crosses no change.",
    )
    story += [
        P(
            "All 64 paired seeds favor the accepted RTL for timing, energy and composite score. Area produces 14 wins, 41 ties and 9 losses and is therefore reported as neutral. The result is cumulative for the four-line revision; no exact per-line PPA attribution is claimed.",
        ),
        PageBreak(),
        P("2. Module and benchmark", "h1"),
        P(
            "The evaluated module is a sequential implementation of SHA-1 compression. It consumes a 512-bit message block through a 32-bit command/data interface and updates a 160-bit chaining state through 80 rounds of Boolean mixing, rotations, a message schedule and modulo-2^32 addition. A legal block occupies 80 busy cycles.",
        ),
        P("Frozen public interface", "h2"),
        P(
            html.escape(
                "module sha1(clk_i, rst_i, text_i, text_o, cmd_i, cmd_w_i, cmd_o);\n"
                "  input clk_i, rst_i, cmd_w_i;\n"
                "  input [31:0] text_i;  output [31:0] text_o;\n"
                "  input [3:0] cmd_i;    output [3:0] cmd_o;\n"
                "endmodule"
            ).replace("\n", "<br/>"),
            "code",
        ),
        P(
            "Only sha.v may change. Reset behavior, command protocol, digest read order, latency, throughput and every observable cycle are fixed. The accepted source is therefore an optimization of the same module, not a redesign of the surrounding system.",
        ),
        P("Why SHA-1 is used", "h2"),
        P(
            "SHA-1 is a legacy benchmark, not a recommended security primitive. It is useful here because it combines sequential control, word-level arithmetic and nonlinear Boolean logic with authoritative conformance vectors. It provides a comprehensible test vehicle for the method without exposing proprietary RTL.",
        ),
        P("Provenance and corrected reference", "h2"),
        P(
            "The starting artifact is the public "
            '<link href="https://github.com/verilog-to-routing/vtr-verilog-to-routing/blob/95f5c6de9e158371ba7185bf97c07a84153735d6/vtr_flow/benchmarks/verilog/sha.v" color="#0A84FF"><u>VTR SHA benchmark</u></link> '
            "at pinned "
            '<link href="https://github.com/verilog-to-routing/vtr-verilog-to-routing/commit/95f5c6de9e158371ba7185bf97c07a84153735d6" color="#0A84FF"><u>commit 95f5c6de...</u></link>. '
            "The upstream RTL does not produce the standard digest for abc. A separate conformance correction creates the frozen golden source. The correction is historical preparation and is not counted as an optimization. The complete "
            '<link href="https://github.com/verilog-to-routing/vtr-verilog-to-routing" color="#0A84FF"><u>VTR repository</u></link> '
            "is linked for independent inspection.",
        ),
        callout(
            "Corrected reference: SHA1(abc) = a9993e364706816aba3e25717850c26c9cd0d89d",
            BLUE,
        ),
        PageBreak(),
        P("3. Evaluation contract", "h1"),
        P(
            "A PPA comparison is meaningful only when accepted RTL and baseline share the same functional, physical and statistical contract. The repository freezes each item below in a machine-readable manifest and includes the exact evaluator snapshot.",
        ),
        data_table(
            [
                ["Contract dimension", "Frozen choice"],
                ["Editable artifact", "sha.v only; accepted source frozen by SHA-256"],
                ["Functional behavior", "Exact interface, reset, protocol, latency, output order and cycle behavior"],
                ["Conformance", "NIST SHA-1 Short and Long Message corpus; 129 accepted-RTL cases"],
                ["Formal", "EQY commit 6734d8c2...; fail closed; 2 CPU, 7 GB, 10 min"],
                ["Physical flow", "VTR/VPR commit 95f5c6de... under pinned Linux/amd64 image"],
                ["Architecture", "k6_N10_I40_Fi6_L4_frac0_ff1_45nm.xml"],
                ["Power", "VTR PTM45, 0.9 V, 85 C; fixed 5,000-cycle active and idle traces"],
                ["PPA comparison", "64 fixed, paired VPR seeds"],
                ["Primary metrics", "Total MWTA, critical-path delay, energy per completed block"],
            ],
            [45, 121],
        ),
        Spacer(1, 5 * mm),
        P(
            "The accepted RTL cannot alter testbenches, activity, architecture, tool flags, seeds or parsers. The evaluator owns acceptance and keeps the published claim independent from how the source revision was proposed.",
        ),
        PageBreak(),
        P("4. Verification before PPA", "h1"),
    ]
    story += figure(
        "verification-pipeline.svg",
        166,
        "Figure 2. PPA is reached only after source, functional, NIST and formal gates pass.",
    )
    story += [
        P("Gate semantics", "h2"),
        data_table(
            [
                ["Gate", "Purpose", "Failure behavior"],
                ["Source/interface", "Reject interface drift, extra modules and simulation-only constructs", "Invalid RTL"],
                ["Functional", "Check reset, protocol, cycle behavior and known answers", "Invalid RTL"],
                ["NIST", "129 Short/Long conformance cases", "Invalid RTL"],
                ["EQY", "Unbounded cycle-equivalence proof after reset", "Fail, timeout or inconclusive invalidates"],
                ["64-seed PPA", "Fixed paired evidence and acceptance", "Applies statistical gates"],
            ],
            [28, 87, 51],
        ),
        P("Formal scope", "h2"),
        P(
            "The proof is conservative and structure-aware: it compares public outputs and stable internal cut points to converge within the laptop resource envelope. It supports local cycle-exact rewrites but may reject an output-equivalent revision that substantially recodes state or retimes registers. That conservatism does not weaken a reported pass.",
        ),
        P("Mutation qualification", "h2"),
        P(
            "This MCY experiment qualifies the frozen verification stack by mutating the corrected baseline. It is neither a comparison across proposed candidates nor an accepted-RTL-versus-baseline PPA measurement.",
        ),
        data_table(
            [
                ["MCY result", "Count"],
                ["Detected by simulation", "454"],
                ["Rejected only by formal", "28"],
                ["Proved equivalent", "18"],
                ["Inconclusive", "0"],
            ],
            [125, 41],
        ),
        P(
            "Of 500 deterministic mutations, 18 were formally proved equivalent and all 482 functionally distinguishable mutations were rejected: 454 by simulation and 28 only by formal. This demonstrates complementary test and formal sensitivity; it does not prove absence of all possible defects.",
        ),
        PageBreak(),
        P("5. Exact baseline-to-accepted diff", "h1"),
        P(
            "Source file: <b>sha.v</b>. Line numbers are identical in the corrected baseline and accepted RTL: 129, 131, 141 and 144.",
        ),
        P(DIFF, "code"),
        callout(
            "No register, state transition, port, command, latency or output statement changed. EQY proves the accepted revision cycle-equivalent to the corrected baseline.",
            TEAL,
        ),
        P("Review principle", "h2"),
        P(
            "The transformations are deliberately reviewable. Boolean and modular arithmetic explain why each rewrite is mathematically legal; full-circuit formal equivalence is still the acceptance authority because widths, signedness, reset and sequential context can invalidate an apparently obvious source-level argument.",
        ),
        P("Attribution boundary", "h2"),
        P(
            "The reported PPA improvement belongs to the four changes together. No full 64-seed ablation matrix is included, so it would be misleading to assign an exact percentage to any one line. The following pages explain the intent and possible synthesis consequence of each change, not a measured isolated contribution.",
        ),
        PageBreak(),
        P("6. Rewrite 1: SHA-1 choose function", "h1"),
        P("Source: <b>sha.v:129</b> in both frozen revisions."),
    ]
    story += figure(
        "rewrite-1-choose.svg",
        166,
        "Figure 3. Conceptual logic structure. The FPGA mapper remains free to choose the final LUT implementation.",
        max_height_mm=66,
    )
    story += [
        P("Why they are equivalent", "h2"),
        *equation("rewrite-1-choose-equation.svg", 54),
        P(
            "The products BC and not-B·D are mutually exclusive because B and not-B cannot both be one, so their XOR equals OR. Expanding the accepted product-of-sums gives BC OR not-B·D OR CD. The CD consensus term is redundant: when C=D=1, either B=1 makes BC true or B=0 makes not-B·D true. Both forms therefore select C when B is one and D otherwise.",
        ),
        P(
            "The source-level proof explains the local identity. EQY separately proved the complete sequential circuit cycle-equivalent, including actual Verilog widths, reset and state behavior.",
        ),
        PageBreak(),
        P("7. Rewrite 2: factored majority", "h1"),
        P("Source: <b>sha.v:131</b> in both frozen revisions."),
    ]
    story += figure(
        "rewrite-2-majority.svg",
        166,
        "Figure 4. The accepted form factors the three-input majority around B XOR D.",
        max_height_mm=66,
    )
    story += [
        P("Why they are equivalent", "h2"),
        *equation("rewrite-2-majority-equation.svg", 50),
        P(
            "The first two lines are the same XOR polynomial after factoring C from BC XOR CD. The terms BD and B XOR D cannot both be one: if BD=1, then B=D=1 and B XOR D=0. Their XOR can therefore be replaced by OR. Operationally, if B equals D their common value decides the majority; if they differ, C decides it.",
        ),
        P(
            "EQY proved this identity in the complete circuit. Physically, the factorization exposes a different topology that can reduce logic depth or routing pressure after mapping; the later netlist evidence supports only the cumulative four-rewrite result, not an isolated attribution.",
        ),
        PageBreak(),
        P("8. Rewrite 3: balanced message-schedule XOR", "h1"),
        P("Source: <b>sha.v:141</b> in both frozen revisions."),
    ]
    story += figure(
        "rewrite-3-xor.svg",
        166,
        "Figure 5. The accepted RTL makes two parallel first-level XOR operations explicit.",
        max_height_mm=66,
    )
    story += [
        P("Why they are equivalent", "h2"),
        *equation("rewrite-3-xor-equation.svg", 67),
        P(
            "Bitwise XOR is associative for every bit position, so regrouping does not change any result bit and introduces no carry. Parentheses make two parallel first-level operations explicit before the final XOR. A synthesizer may rebalance the baseline itself, but the written grouping can influence intermediate optimization, LUT packing and routing topology.",
        ),
        P(
            "EQY proved that the regrouped message schedule produces the same observable sequence in the complete SHA-1 state machine.",
        ),
        PageBreak(),
        P("9. Rewrite 4: reassociated 32-bit accumulator", "h1"),
        P("Source: <b>sha.v:144</b> in both frozen revisions. R denotes rotate-left-by-5 of A and f denotes SHA1_ft_BCD."),
    ]
    story += figure(
        "rewrite-4-accumulator.svg",
        166,
        "Figure 6. Serial source grouping versus two partial-sum branches before the final addition.",
        max_height_mm=66,
    )
    story += [
        P("Why they are equivalent", "h2"),
        *equation("rewrite-4-accumulator-equation.svg", 88),
        P(
            "Every operand and the assigned result is a 32-bit unsigned vector. Addition is associative in arithmetic modulo 2^32: discarding an overflow carry at an intermediate grouping cannot change the final low 32 bits. The accepted grouping therefore changes the exposed dependency structure, not the numerical result.",
        ),
        P(
            "This identity depends on the declared widths and unsigned vector semantics. EQY confirmed the actual Verilog interpretation over the complete sequential design, rather than relying on algebra alone.",
        ),
        PageBreak(),
        P("10. Physical proxy and power model", "h1"),
        P("Open 45 nm FPGA target", "h2"),
        P(
            "The target is VTR's homogeneous k6_N10_I40_Fi6_L4_frac0_ff1_45nm architecture: six-input LUTs clustered ten per logic block, with the architecture's routing and timing model. Power uses VTR PTM45 properties at 0.9 V and 85 C. MWTA is a minimum-width-transistor-area abstraction, not a physical square-micrometer area.",
        ),
        P("Fixed activity", "h2"),
        P(
            "Two 5,000-cycle ACE traces are frozen and hashed. The active trace continuously executes diverse legal blocks and completes 60 blocks; the idle trace keeps the clock active after reset with an inactive interface. Port order is checked against the synthesized BLIF. Active and idle analyses reuse the same placement and route.",
        ),
        P("Energy metric", "h2"),
        callout(
            "Energy per block = active total power x routed workload time / 60 completed blocks",
            BLUE,
        ),
        P(
            "This metric measures modeled energy to complete the fixed corpus. It is intentionally different from instantaneous active power and from idle power. All three remain visible in the evidence so that a favorable energy score cannot conceal an unfavorable power trade-off.",
        ),
        P("Runtime envelope", "h2"),
        P(
            "The Linux/amd64 container is capped at two CPUs, 7 GB RAM and 512 processes with runtime networking disabled. The accepted RTL certification reports 1,091.82 seconds elapsed on the qualified Apple Silicon laptop. Host contention affects wall time, not source hashes, seed identities or parsed measurements.",
        ),
        PageBreak(),
        P("11. Statistical method and score", "h1"),
        P(
            "Accepted RTL and baseline use the same 64 VPR seeds. Pairing removes much of the unrelated between-seed placement/routing variation. Ratios are analyzed in log space because PPA comparisons are multiplicative and because the geometric mean preserves reciprocal symmetry.",
        ),
        P("Per-seed composite: r = cube_root(r_area x r_delay x r_energy)", "code"),
        P("Published estimate: exp(mean(log(r_seed)))", "code"),
        P(
            "Two-sided 95% Student-t intervals use 63 degrees of freedom. The fixed sample remains 64 and is not extended after inspecting the result. The baseline is exactly 1.0 in paired-ratio space by construction; its absolute seed-to-seed variability remains available in the raw records.",
        ),
        P("Acceptance", "h2"),
        bullet("All functional, NIST, synthesis, formal, route, power and integrity checks pass."),
        bullet("At least one primary metric has a material improvement."),
        bullet("No primary metric has a statistically supported regression."),
        bullet("The composite upper one-sided 95% bound is below 1.0."),
        bullet("Worst-case and evidence-integrity gates remain within the frozen policy."),
        P(
            "The scalar score is a compact summary, not a replacement for engineering review. Area, delay, energy, power, resources and uncertainty are always reported alongside it.",
        ),
        PageBreak(),
        P("12. Certified 64-seed result", "h1"),
    ]
    story += figure(
        "paired-seed-distributions.svg",
        166,
        "Figure 7. Paired seed distributions. Each mark compares accepted RTL and baseline under the same VPR seed.",
    )
    story += [
        data_table(RESULT_ROWS, [34, 32, 32, 68]),
        Spacer(1, 4 * mm),
        data_table(
            [
                ["Metric", "Wins / ties / losses"],
                ["Area", "14 / 41 / 9"],
                ["Timing", "64 / 0 / 0"],
                ["Energy", "64 / 0 / 0"],
                ["Composite", "64 / 0 / 0"],
            ],
            [92, 74],
        ),
        P(
            "The paired estimate is the inferential headline. A simple ratio of medians gives similar but not identical values because the median of ratios is not generally the ratio of medians.",
        ),
        PageBreak(),
        P("13. Power-throughput trade-off", "h1"),
        data_table(
            [
                ["Informative metric", "Baseline median", "Accepted RTL median", "Raw median change"],
                ["Fmax", "66.6426 MHz", "75.2964 MHz", "+12.99%"],
                ["Active total power", "9.9125 mW", "10.4900 mW", "+5.83%"],
                ["Active dynamic power", "5.0713 mW", "5.7018 mW", "+12.43%"],
                ["Active static power", "4.8394 mW", "4.7916 mW", "-0.99%"],
                ["Idle total power", "4.4670 mW", "4.6550 mW", "+4.21%"],
                ["Energy / block", "12.3896 nJ", "11.6399 nJ", "-6.05%"],
            ],
            [48, 38, 40, 40],
        ),
        Spacer(1, 5 * mm),
        callout(
            "The accepted RTL consumes more active power per unit time but less modeled energy per completed block because it finishes the workload sooner.",
            ORANGE,
        ),
        Spacer(1, 5 * mm),
        P(
            "This is a genuine trade-off, not a contradiction. The declared objective values energy per operation and timing while constraining area. A product constrained by peak power, thermal density or idle power could use a different acceptance policy.",
        ),
        P(
            "The evidence retains total, dynamic and static active power plus idle power so that the composite score cannot hide this design choice.",
        ),
        PageBreak(),
        P("14. Representative implementation evidence", "h1"),
    ]
    story += figure(
        "netlist-evidence.svg",
        166,
        "Figure 8. Seed 20 illustrates how the cumulative source change affects mapped and routed structure.",
    )
    story += [
        P(
            "The accepted RTL has nine more ABC .names nodes, yet packs into one fewer CLB and reduces the timing graph by four levels. This rules out a simplistic claim that fewer generic mapped nodes caused the result. The better interpretation is that the new topology gives VTR a more favorable packing and routing solution.",
        ),
        P(
            "Seed 20 is illustrative, not the statistical proof. Repeatability comes from the 64 paired implementations, in which timing, energy and composite all favor the accepted RTL.",
        ),
        PageBreak(),
        P("15. Reproducibility", "h1"),
        P("Fast evidence audit", "h2"),
        P("make verify", "code"),
        P(
            "The audit checks the RTL identities, formal and NIST evidence references, the exact 64-seed pairing, all metric log-ratio estimates, confidence intervals and the decision rule. It needs Python 3 only and performs no new EDA measurement.",
        ),
        P("Full pinned rerun", "h2"),
        P("./reproduce/build-image.sh", "code"),
        P(
            "The build checks out VTR recursively at the pinned commit and constructs the exact Linux/amd64 evaluator image. Accepted RTL certification runs in a new bind-mounted results directory with networking disabled. Generated failures remain failures; JSON is never edited into success.",
        ),
        P("Evidence archive", "h2"),
        P(
            "The complete accepted-RTL evidence is distributed separately because its 70 MB compressed size and thousands of intermediate files are unsuitable for normal Git history. The measurement archive remains identified by SHA-256 9983b1fef4509b9a9a592af8134be39eaa7545e5269ac7332206e86db7cce3e8.",
        ),
        P("Clean-room expectation", "h2"),
        P(
            "A valid independent rerun starts from a clean checkout, builds or retrieves the pinned image, writes to a new evidence directory and uses the fixed certification seed pool. The public compact JSON is an auditable summary, not a substitute for the full archive when reviewing tool logs.",
        ),
        PageBreak(),
        P("16. Limitations and transfer", "h1"),
        P("Claims boundary", "h2"),
        bullet("Academic VTR open-FPGA estimate; not a commercial FPGA, ASIC, signoff or silicon measurement."),
        bullet("No extracted parasitics, PVT corners, clock-tree signoff, IR drop, EM, DRC/LVS, package, yield or production test."),
        bullet("Formal equivalence is conservative and structure-aware; it may reject legal microarchitectural redesigns."),
        bullet("The 64-seed confidence interval models implementation randomness only, not process, voltage, temperature, workload or tool-version uncertainty."),
        bullet("No exact PPA contribution is assigned to an individual rewrite without ablation evidence."),
        bullet("SHA-1 is a legacy benchmark and must not be presented as a modern security recommendation."),
        P("Transferable customer-pilot method", "h2"),
        P(
            "The commercial value is the evaluator architecture: freeze the customer's golden behavior and implementation context; hash the proposed RTL; prove correctness before PPA; evaluate it on a fixed paired pool; and publish raw metrics, uncertainty and trade-offs. A proprietary pilot would substitute customer-owned RTL, formal strategy, libraries, constraints, activity and signoff reports for VTR.",
        ),
        callout(
            "The optimization generator may be an engineer, evolutionary system or coding agent. Acceptance remains owned by the frozen customer-specific evaluator.",
            TEAL,
        ),
        PageBreak(),
        P("17. Conclusion and artifact identities", "h1"),
        P(
            "A four-line, cycle-equivalent RTL change produced a repeatable 5.98% composite improvement under the declared VTR 45 nm contract. Timing and energy improved in every paired seed; area remained neutral. The result is small, reviewable, formally proved and statistically explicit.",
        ),
        data_table(
            [
                ["Artifact", "SHA-256"],
                ["Corrected baseline sha.v", "191a4f2148a4efda7aadd24480eb13d78a1d2c0c7e8a3fcc37c44f6a8e8011e5"],
                ["Accepted sha.v", "743e6c9ffcca6f00d35d5e73ba6f6478a9133a0c55a471c16d6e59d831aeeabc"],
                ["EQY PASS marker", "ba3b47c5fbb189844a827ae395e816024c967b83444a06eccb71f9e34498ab07"],
                ["EQY driver log", "203f2ab1a1db8aadcbdbf5be88e5478b1abcb51e213e941557889e1474b9cbce"],
                ["Full evidence archive", "9983b1fef4509b9a9a592af8134be39eaa7545e5269ac7332206e86db7cce3e8"],
            ],
            [48, 118],
        ),
        Spacer(1, 5 * mm),
        P("Primary references", "h2"),
        bullet("VTR/VPR: https://docs.verilogtorouting.org/en/latest/vpr/"),
        bullet("VTR power estimation: https://docs.verilogtorouting.org/en/latest/vtr/power_estimation/"),
        bullet("EQY: https://github.com/YosysHQ/eqy"),
        bullet("NIST secure hashing validation: https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program/secure-hashing"),
    ]
    doc.build(story, canvasmaker=InvariantCanvas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--executive-only", action="store_true")
    mode.add_argument("--technical-only", action="store_true")
    args = parser.parse_args()

    # Loading these files here makes missing or malformed certified inputs fail the report build.
    accepted = load_json("results/accepted-certification.json")
    baseline = load_json("results/baseline-certification.json")
    assert accepted["certified"] and accepted["valid"]
    assert len(accepted["per_seed"]) == len(baseline["per_seed"]) == 64

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    executive = OUTPUT_DIR / "executive-summary.pdf"
    technical = OUTPUT_DIR / "technical-report.pdf"
    if not args.technical_only:
        build_executive(executive)
        (REPORT_DIR / "executive-summary.pdf").write_bytes(executive.read_bytes())
        print(f"wrote {executive}")
    if not args.executive_only:
        build_technical(technical)
        print(f"wrote {technical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
