#!/usr/bin/env python3
"""Render the saved research record; no EDA, search or acceptance is performed."""
from pathlib import Path
from html import escape
import json
import shutil

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
OUTPUT = REPO / 'output/pdf/SERV-1.4.0-Development-Study.pdf'
DATA = json.loads((ROOT / 'results/development.json').read_text())
CONTRACT = json.loads((ROOT / 'contract.json').read_text())
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
NAVY = colors.HexColor('#18344A')
TEAL = colors.HexColor('#126C72')
GREY = colors.HexColor('#5B6470')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleServ', fontName='Helvetica-Bold', fontSize=25, leading=29, textColor=NAVY, spaceAfter=18))
styles.add(ParagraphStyle(name='SectionServ', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=TEAL, spaceBefore=13, spaceAfter=8))
styles.add(ParagraphStyle(name='BodyServ', fontName='Helvetica', fontSize=10, leading=14.5, spaceAfter=9))
styles.add(ParagraphStyle(name='SmallServ', fontName='Helvetica', fontSize=8.5, leading=12, textColor=GREY, spaceAfter=7))
styles.add(ParagraphStyle(name='CodeServ', fontName='Courier', fontSize=7.6, leading=11, spaceAfter=8))
story = []

def text(value, style='BodyServ'):
    story.append(Paragraph(value, styles[style]))

def section(title):
    text(title, 'SectionServ')

def table(rows, widths):
    cells = [[Paragraph(escape(str(c)), styles['SmallServ']) for c in r] for r in rows]
    t = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E8F1F3')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEBELOW', (0,0), (-1,0), 0.8, TEAL),
        ('LINEBELOW', (0,1), (-1,-1), 0.3, colors.HexColor('#D9E1E7')),
        ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 7), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

text('SERV 1.4.0<br/>Development study', 'TitleServ')
text('<b>PAUSED RESEARCH | 12 DEVELOPMENT PAIRS | FINAL ACCEPTANCE PENDING</b>', 'SmallServ')
text('Record prepared 13 October 2026. The study was paused by the user on 12 October 2026. This package preserves the best saved implementation and its evidence. It is a research record alongside the three accepted portfolio cases.')
section('Best saved result')
b, o, ratios = DATA['baseline_arithmetic_means'], DATA['optimized_arithmetic_means'], DATA['geometric_metric_ratios']
table([
    ['Metric', 'Baseline mean', 'Optimized mean', 'Paired change'],
    ['Total area', f"{b['area_total_mwta']:,.1f} MWTA", f"{o['area_total_mwta']:,.1f} MWTA", '5.9467% lower'],
    ['Critical path', f"{b['critical_path_delay_ns']:.6f} ns", f"{o['critical_path_delay_ns']:.6f} ns", '0.0721% higher'],
    ['Active total power', f"{1000*b['active_total_power_w']:.6f} mW", f"{1000*o['active_total_power_w']:.6f} mW", '4.3802% lower'],
    ['Packed CLBs', '46', '43', '6.5217% fewer'],
    ['Mapped flip-flops', '181', '181', 'Unchanged'],
    ['Composite PPA', '1.000000', f"{DATA['score']:.6f}", f"{DATA['improvement_percent']:.4f}% lower"],
], [122, 133, 133, 121])
text('Metric means are arithmetic means. Paired changes use geometric means of per-pair ratios. The composite equally weights the log area, delay and power ratios. A small timing increase remains visible.', 'SmallServ')
section('Scope of the result')
text('The estimates use the pinned academic VTR/PTM 45 nm flow, a homogeneous LUT6 target and ACE probabilistic activity at 0.9 V and 85 C. MWTA is the minimum-width transistor-area unit, not square millimetres. The result is not measured silicon, board power, workload energy, ASIC signoff or commercial-FPGA characterization.')
text('<b>3.4516% is a development selection result.</b> The current candidate has no held-out certification result and no final 64-pair result. The original greater-than-10% objective remains unmet.')
story.append(PageBreak())

text('Design and implementation', 'TitleServ')
section('Frozen measurement boundary')
text('SERV is a bit-serial 32-bit RISC-V processor. The top is serv_synth_wrapper with PRE_REGISTER=1, RESET_STRATEGY=MINI, WITH_CSR=1, RF_WIDTH=2, W=1, MDU=0, COMPRESSED=0 and ALIGN=0. Instruction/data buses and register-file addresses, data and handshakes are part of the protected boundary.')
text('The baseline contains eighteen files, all byte-identical to the pinned SERV 1.4.0 commit. The optimized tree also has eighteen files; the exact patch changes ten. Total source length is 3,562 baseline lines and 4,137 optimized lines, including comments, blank lines and inactive parameter alternatives. Source length is not a physical area estimate.')
section('What the combined candidate changes')
text('The candidate combines a three-bit representation of the high register-file phase with earlier decoder, buffer, PC and control rewrites. The frozen wrapper selects RF_HIGH_PHASE_FORM=1, DECODER_CAPTURE_USAGE_FORM=3, PC_WORD_ENABLE_FORM=3, DATA_WORD_ENABLE_FORM=3 and BUFFER_CONTROL_FORM=3. The result belongs to this complete selected implementation; component percentages cannot be added or attributed independently.')
section('Capacity and physical state')
table([
    ['Quantity', 'Baseline', 'Optimized'],
    ['GPR words / RAM-backed CSR words', '32 / 4', '32 / 4'],
    ['Bits per register word', '32', '32'],
    ['External register storage', '1,152 bits / 144 bytes', '1,152 bits / 144 bytes'],
    ['Logical rows / SRAM interface', '576 rows / 2 bits', '576 rows / 2 bits'],
    ['Mapped wrapper state', '181 flip-flops', '181 flip-flops'],
], [227, 141, 141])
text('The external SRAM is excluded from mapped wrapper area. Its storage capacity is unchanged. The wrapper flip-flop count and external register-file storage describe different resources.', 'SmallServ')
section('Correctness records')
text('Saved source gates include lint at W=1 and W=4 and sequential equivalence with 357 proved / zero unproved obligations. RTL-to-measured-netlist equivalence covers 126 primary output bits and all 181 state bits: 307 proved / zero unproved for each design. Undefined initialization is preserved in the proof.')
text('Two recorded 4,096-cycle simulations per design compare defined RTL output bits; unknown RTL bits are skipped. These simulations supplement the formal record. The evidence establishes RTL-boundary equivalence and does not certify full RISC-V ISA compliance.')
story.append(PageBreak())

text('Search and stopping point', 'TitleServ')
section('Closed revision-2 exploration')
table([
    ['Recorded activity', 'Count / status'],
    ['Registered exploratory candidates', '2,812'],
    ['Candidates with valid PPA measurements', '2,621'],
    ['Candidates excluded without PPA', '191'],
    ['Selected RF-phase cohort', '36 measured candidates'],
    ['Best candidate paired development comparison', '12 pairs / 24 implementations'],
    ['Held-out certification / final publication', '0 / 0 completed pairs for current leader'],
], [316, 193])
text('Exploration counts are not independent acceptance trials. Later searches used the best candidate and other promising parents, including combinations on intermediate STATE variants. No completed validated combination superseded this leader.')
section('Flow repair and historical results')
text('The adopted revision-2 flow lowers subtraction through standard Yosys mapping before Parmys, applied equally to baseline and candidates. This repair followed a discrepancy between source RTL and a measured mapped implementation. Historical measurements are kept separate from the present result.')
text('An apparent 11.10461% gain was rejected for mapping incoherence. The historical 4.4778% gain was not recertified after the flow repair. Two older exploratory 64-pair replicas are not final certification of this candidate. None is promoted as the current publication result.')
section('Last incomplete family')
text('Nine branch/trap variants were prepared. Thirty-six full elaborations and three native banks completed, with 786,624 configuration-clocks checked. Six native banks remained pending. No PPA measurement was completed for that family; no improvement is assigned to it.')
section('Original acceptance rule remains pending')
text('The study reserved a held-out twelve-pair certification sample and a final 64-pair publication sample. Both remain unexecuted for the leader. The original editorial rule requires a point score and one-sided 95% upper score bound strictly below 0.90, plus the declared primary-metric and multiplicity rules. A descriptive interval from selected development data is not a confirmatory test.')
text('The user paused the search after repeated storage stops. The best source and evidence are preserved. Registering this paused research record does not change the experimental acceptance rule or turn it into an accepted fourth portfolio case.')
story.append(PageBreak())

text('Evidence and verification', 'TitleServ')
section('Public package')
text('The package includes baseline and optimized RTL, an exact unified patch, a contract projection, upstream provenance, the original leader and pause records, projected measurement records, all 24 timing/area and power reports, flow logs and measured BLIF netlists. It also includes saved source lint/formal logs, mapped formal logs/models/scripts and simulation completion logs.')
text('The original development audit is preserved. The full exploration archive, optimizer and private execution infrastructure are outside this package. No downloadable full exploration archive or newly executed EDA replay is claimed.')
text('Private host path prefixes in four simulation logs are replaced by a stable label. Their projection provenance records original and public hashes; all other bytes are preserved.', 'SmallServ')
section('Run the saved-evidence verifier')
text('python3 experiments/serv-1.4.0/verify.py<br/>python3 verify.py', 'CodeServ')
text('The verifier checks exact source identities, upstream Git blob identities, the patch, package checksums, fixed evidence authorities, proof closure markers, measured netlist identities and the arithmetic recomputed from the saved raw reports. It also checks that certification and final-pair completion remain false.')
text('Expected result: saved research evidence PASS; development_pairs=12; improvement=3.4516%; held_out_certification_pairs=0; final_pairs=0; publication_accepted=False.', 'SmallServ')
text('<b>Verification scope:</b> consistency of saved evidence. It does not rerun EDA, independently regenerate a formal proof, certify PPA, or constitute external assurance.')
section('Pinned identities')
for title, value in [
    ('SERV upstream commit', '7d9cde4e6ca4f4c84d7512a752a4c187537dd373'),
    ('Baseline RTL tree SHA-256', CONTRACT['baseline_tree_sha256']),
    ('Optimized RTL tree SHA-256', CONTRACT['optimized_tree_sha256']),
    ('VTR commit', CONTRACT['vtr_commit']),
]:
    text(escape(title) + '<br/>' + escape(value), 'CodeServ')
section('Source, licensing and further reading')
text('Baseline and derived RTL retain upstream ISC headers. The upstream ISC license is bundled. Original presentation and verification work follows the repository MIT license. SERV, its authors and tool providers do not endorse this study.')
text('Primary source: github.com/olofk/serv at the commit above. Package references: README.md, contract.json, provenance.json, results/development.json, results/measurements.json and results/pause-record.json. Repository methodology and audit scope: METHODOLOGY.md and AUDIT.md.', 'SmallServ')

def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#C8D6DF'))
    canvas.line(43, 39, A4[0]-43, 39)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GREY)
    canvas.drawString(43, 26, 'Gother Labs | SERV 1.4.0 | Paused development research')
    canvas.drawRightString(A4[0]-43, 26, str(document.page))
    canvas.restoreState()

doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=43, leftMargin=43,
    topMargin=45, bottomMargin=56, title='SERV 1.4.0 - Paused development study',
    author='Gother Labs', invariant=1)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
shutil.copyfile(OUTPUT, ROOT / 'technical-report.pdf')
shutil.copyfile(OUTPUT, REPO / 'SERV-1.4.0-Development-Study.pdf')
print(OUTPUT)
