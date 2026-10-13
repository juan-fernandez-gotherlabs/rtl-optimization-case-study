#!/usr/bin/env python3
"""Verify saved SERV research evidence; this does not run EDA or certify PPA."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
BASELINE = '29b5ea77526b3b972ba99c8702524e87035e5a921db6f1a59bb822599203ba91'
OPTIMIZED = 'b25b924a34318591d7cfec7097fc5d265a372316757893b2d51a095c5ba01fbe'
TREES = {'baseline': BASELINE, 'optimized': OPTIMIZED}
METRICS = ('area_total_mwta', 'critical_path_delay_ns', 'active_total_power_w')
RTL_FILES = (
    'serv_aligner.v', 'serv_alu.v', 'serv_bufreg.v', 'serv_bufreg2.v',
    'serv_compdec.v', 'serv_csr.v', 'serv_ctrl.v', 'serv_debug.v',
    'serv_decode.v', 'serv_immdec.v', 'serv_mem_if.v', 'serv_rf_if.v',
    'serv_rf_ram.v', 'serv_rf_ram_if.v', 'serv_rf_top.v', 'serv_state.v',
    'serv_synth_wrapper.v', 'serv_top.v',
)
AUTHORITIES = {
    'results/development.json': '58f497968fcec928b2bc969ddc8b4d2b1860df2ff24af232b9a28655a5820d0b',
    'results/measurements.json': 'd2bfa0d5eadf9775fe334551f5c7a6a78e1ebf3b4ce0c77c68dc3a5888c97388',
    'results/pause-record.json': 'c11efa7c86b0e4e453f12f8259a8536bddd7bc06fb0d69fb2e5d2586b12b96f1',
    'results/development-leader.json': 'e62d65acc4a71448712c7a5b3c9cfb4b6c7c37515f871b07e966203f0e83363b',
    'contract.json': 'f84ed125c52e3f9c7eaef3c318203e17dab87355dd6009d9fe0c7a9281f3734c',
    'provenance.json': 'd89fd3f28ac1b1e831d99026ad0404c28cac54644cf940d3d906765bd0385827',
    'evidence/original-development-audit.json': 'b6981facd21cee25d16d2227d96ebdffe185db1bf1f5d3c880937a032c7fddec',
    'evidence/original-development-summary.json': 'aa7d308318a43ad559b48f0ca4e4b67d1728f1a988f9e69c57948a6d557e6de4',
    'evidence/mapped-formal/baseline/result.json': 'f297a4f452baca2de5cecde7dacdc39375c30d5e498e6cc529f182cbd5827349',
    'evidence/mapped-formal/optimized/result.json': '8b7abca7ae95dec4d8f2c25086e3be03aa704bd763f3a12993d799dc9bd1064e',
    'evidence/correctness/baseline/formal.log': '03b15157f461114ce01c82454dd76d5912f2a1bfd7e8a2fa66a7a4674372e270',
    'evidence/correctness/optimized/formal.log': '5aee95f07b860f5316b294be69d8c2f730b55289141f45244cb8ac22a791dd8d',
    'evidence/simulation/provenance.json': 'f8866fd4a77a6fa5aeaedffd4eea1f5a6bc939e6510cd4690636ddac50df509a',
    'results/confirmation64.json': '2a39a8c018d80203413dc669316c185fc12a2e085e22f89f001a285d565999b4',
    'results/confirmation64-report-data.json': '2be22fffba34e9a472649ec598db772f9ce0adb43d7d8ab25f59d8d2a2382b55',
}


class VerificationError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise VerificationError(message)


def sha(path):
    require(path.is_file() and not path.is_symlink(), f'missing or unsafe file: {path}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative):
    value = json.loads((ROOT / relative).read_text())
    require(isinstance(value, dict), f'expected JSON object: {relative}')
    return value


def files():
    return {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
            if p.is_file() and p.name not in {'SHA256SUMS', '.DS_Store'}
            and not set(p.relative_to(ROOT).parts) & {'__pycache__', 'output', 'tmp'}}


def write_manifest():
    (ROOT / 'SHA256SUMS').write_text(''.join(f'{sha(ROOT / p)}  {p}\n' for p in sorted(files())))


def verify_manifest():
    seen = {}
    for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        require(match is not None, 'malformed checksum')
        digest, relative = match.groups()
        path = PurePosixPath(relative)
        require(not path.is_absolute() and '..' not in path.parts, 'unsafe checksum path')
        require(relative not in seen, 'duplicate checksum path')
        seen[relative] = digest
    require(set(seen) == files(), 'checksum coverage differs')
    for relative, digest in seen.items():
        require(sha(ROOT / relative) == digest, f'checksum mismatch: {relative}')
    for relative, digest in AUTHORITIES.items():
        require(sha(ROOT / relative) == digest, f'fixed authority mismatch: {relative}')


def tree_digest(label):
    directory = ROOT / 'rtl' / label
    require(sorted(p.name for p in directory.iterdir()) == sorted(RTL_FILES), 'RTL file set changed')
    result = hashlib.sha256()
    for name in RTL_FILES:
        sha(directory / name)
        result.update(name.encode() + b'\0' + (directory / name).read_bytes() + b'\0')
    return result.hexdigest()


def verify_rtl():
    for label, digest in TREES.items():
        require(tree_digest(label) == digest, f'{label} RTL identity changed')
    provenance = load('provenance.json')
    require(len(provenance['files']) == 18, 'upstream file count changed')
    require({x['path'] for x in provenance['files']} == {'rtl/' + n for n in RTL_FILES}, 'upstream coverage changed')
    for entry in provenance['files']:
        p = ROOT / 'rtl/baseline' / PurePosixPath(entry['path']).name
        b = p.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()
        require(blob == entry['upstream_git_blob'] and sha(p) == entry['sha256'], 'upstream identity mismatch')
    expected = ''.join(''.join(difflib.unified_diff(
        (ROOT / 'rtl/baseline' / name).read_text().splitlines(keepends=True),
        (ROOT / 'rtl/optimized' / name).read_text().splitlines(keepends=True),
        fromfile='baseline/' + name, tofile='optimized/' + name,
    )) for name in sorted(RTL_FILES))
    require((ROOT / 'rtl/changes.patch').read_text() == expected, 'exact patch differs')


def statements(path):
    joined, rows = '', []
    for raw in path.read_text().splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line.endswith('\\'):
            joined += line[:-1] + ' '
        else:
            rows.append((joined + line).split())
            joined = ''
    require(not joined, 'unfinished BLIF statement')
    return rows


def blif_identity(path):
    return hashlib.sha256(json.dumps(statements(path), separators=(',', ':')).encode()).hexdigest()


def number(pattern, text, label):
    match = re.search(pattern, text, re.M)
    require(match is not None, f'missing raw {label}')
    value = float(match.group(1))
    require(math.isfinite(value) and value > 0, f'invalid raw {label}')
    return value


def parse_metrics(directory, seed):
    for filename in ['vpr.crit_path.out', 'serv_synth_wrapper.power']:
        require((directory / filename).is_file(), f'missing raw report: {filename}')
    report = (directory / 'vpr.crit_path.out').read_text()
    require('VPR succeeded' in report, 'VPR completion absent')
    logic = number(r'Total used logic block area:\s*([0-9.eE+-]+)', report, 'logic area')
    routing = number(r'Total routing area:\s*([0-9.eE+-]+)', report, 'routing area')
    delay = number(r'Final critical path delay \(least slack\):\s*([0-9.eE+-]+) ns', report, 'delay')
    clb = int(number(r'^\s*clb\s*:\s*(\d+)\s*$', report, 'CLB count'))
    power = number(r'^Total\s+([0-9.eE+-]+)\s', (directory / 'serv_synth_wrapper.power').read_text(), 'power')
    return {'seed': seed, 'area_total_mwta': logic + routing, 'used_logic_area_mwta': logic,
            'routing_area_mwta': routing, 'critical_path_delay_ns': delay,
            'active_total_power_w': power, 'clb_count': clb}


def verify_recorded_correctness():
    simulation_projection = load('evidence/simulation/provenance.json')
    entries = simulation_projection['files']
    require({entry['path'] for entry in entries} == {
        f'evidence/simulation/{label}/{mode}.log' for label in TREES
        for mode in ['defined-output', 'rom-sanity']
    }, 'simulation projection coverage differs')
    for entry in entries:
        require(sha(ROOT / entry['path']) == entry['public_sha256'], 'public simulation projection differs')
    for label, digest in TREES.items():
        source = load(f'evidence/correctness/{label}/source-correctness.json')
        require(source['candidate_tree_sha256'] == digest, 'source proof RTL binding differs')
        require(all(source[k] == 'pass' for k in ['lint_w1', 'lint_w4', 'formal_status', 'structural_lint']), 'source gate failed')
        source_log = (ROOT / f'evidence/correctness/{label}/formal.log').read_text()
        require('357 are proven and 0 are unproven' in source_log, 'source equivalence not closed')
        for width in ['w1', 'w4']:
            log = (ROOT / f'evidence/correctness/{label}/lint_{width}.log').read_text()
            require(not re.search(r'^%Warning-(UNDRIVEN|MULTIDRIVEN|UNOPTFLAT):', log, re.M), 'structural warning')
        proof = load(f'evidence/mapped-formal/{label}/result.json')
        require(proof['candidate_tree_sha256'] == digest and proof['status'] == 'pass', 'mapped proof identity or status differs')
        require(proof['counts'] == [307, 0] and proof['original_candidate_ff_bits'] == 181, 'mapped proof incomplete')
        require(all(proof[k] is True for k in ['every_primary_and_proposed_state_alias_included_in_proof',
                    'all_original_candidate_ff_bits_bound_once', 'undefined_register_initialization_preserved']), 'mapped state evidence incomplete')
        for filename, expected in proof['files_sha256'].items():
            require(filename in {'gate-aligned.v', 'formal.log', 'direct-equivalence.ys'}, 'unexpected proof file')
            require(sha(ROOT / f'evidence/mapped-formal/{label}' / filename) == expected, 'mapped proof file differs')
        gate = (ROOT / f'evidence/mapped-formal/{label}/gate-aligned.v').read_text()
        require(not re.search(r'^initial\s+n\d+', gate, re.M), 'mapped proof forces undefined initialization')
        log = (ROOT / f'evidence/mapped-formal/{label}/formal.log').read_text()
        require('307 are proven and 0 are unproven' in log and 'Equivalence successfully proven!' in log, 'mapped formal closure absent')
        for mode in ['defined-output', 'rom-sanity']:
            require('PASS' in (ROOT / f'evidence/simulation/{label}/{mode}.log').read_text(), 'recorded simulation failed')


def near(actual, expected, label):
    require(math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-14), f'recomputed {label} differs')


def verify_measurements():
    contract = load('contract.json')
    data = load('results/measurements.json')
    result = load('results/development.json')
    require(data['development_only'] is True and len(data['rows']) == 24, 'development record coverage differs')
    records = {}
    for row in data['rows']:
        label, seed = row['variant'], row['metrics']['seed']
        require(label in TREES and seed in range(5001, 5013), 'unexpected variant or seed')
        require((label, seed) not in records, 'duplicate paired measurement')
        require(row['rtl_tree_sha256'] == TREES[label], 'measurement RTL identity differs')
        require(row['image_id'] == contract['image_id'] and row['synthesis_template_sha256'] == contract['synthesis_template_sha256'], 'measurement environment differs')
        directory = ROOT / 'evidence/ppa' / label / str(seed)
        require(parse_metrics(directory, seed) == row['metrics'], 'raw metric extraction differs')
        for filename, digest in row['report_sha256'].items():
            require(filename in {'vpr.crit_path.out', 'serv_synth_wrapper.power', 'flow_driver.log'}, 'unexpected report name')
            require(sha(directory / filename) == digest, 'original report hash differs')
        blif = directory / 'serv_synth_wrapper.pre-vpr.blif'
        require(sha(blif) == row['blif_sha256'], 'measured netlist differs')
        first = ROOT / 'evidence/ppa' / label / '5001/serv_synth_wrapper.pre-vpr.blif'
        require(blif_identity(blif) == blif_identity(first), 'new netlist needs a distinct proof')
        latches = [s for s in statements(blif) if s[0] == '.latch']
        require(len(latches) == 181 and len({s[2] for s in latches}) == 181, 'measured FF count differs')
        require(row['mapped_simulation_statuses'] == ['pass', 'pass'], 'mapped simulations not closed')
        records[label, seed] = row['metrics']
    require(set(records) == {(v, s) for v in TREES for s in range(5001, 5013)}, 'paired pool differs')
    logs = {m: [math.log(records['optimized', s][m] / records['baseline', s][m]) for s in range(5001, 5013)] for m in METRICS}
    for metric in METRICS:
        near(math.exp(statistics.mean(logs[metric])), result['geometric_metric_ratios'][metric], metric)
        for label in TREES:
            near(statistics.mean(records[label, s][metric] for s in range(5001, 5013)), result[label + '_arithmetic_means'][metric], label + ' mean ' + metric)
    score = math.exp(statistics.mean(statistics.mean(logs[m][i] for m in METRICS) for i in range(12)))
    near(score, result['score'], 'score')
    near((1 - score) * 100, result['improvement_percent'], 'improvement')
    require(all(result['geometric_metric_ratios'][m] <= 1 for m in [METRICS[0], METRICS[2]]), 'development guards fail')
    for label in TREES:
        require({records[label, s]['clb_count'] for s in range(5001, 5013)} == {result['clb_counts'][label]}, 'CLB count differs')
        proof = load(f'evidence/mapped-formal/{label}/result.json')
        require(proof['blif_sha256'] == sha(ROOT / f'evidence/ppa/{label}/5001/serv_synth_wrapper.pre-vpr.blif'), 'proof-to-measurement binding differs')
    require(sha(ROOT / 'evidence/synthesis-v2.tcl') == contract['synthesis_template_sha256'], 'synthesis repair changed')
    return result


def verify_status(result):
    require(result['status'] == 'paused_development', 'study status changed')
    for flag in ['certified', 'publication_accepted', 'strict10_goal_achieved']:
        require(result[flag] is False, f'unsupported claim: {flag}')
    require(result['development_pairs'] == 12 and result['held_out_certification_pairs_completed'] == 0
            and result['final_pairs_completed'] == 0, 'held-out certification remains pending')
    require(result['closed_revision2_exploration'] == {'registered': 2812, 'measured': 2621, 'excluded_without_PPA': 191}, 'closed search accounting differs')
    require(result['external_sram']['RAM_capacity_bits'] == 1152 and result['external_sram']['RAM_logical_rows'] == 576, 'external memory scope differs')


def verify_final64():
    result = load('results/confirmation64.json')
    display = load('results/confirmation64-report-data.json')
    require(result['status'] == 'complete_and_audited' and result['pairs'] == 64
            and result['implementations_audited'] == 128, 'final sample incomplete')
    rows = result['all_rows']
    require([row['seed'] for row in rows] == list(range(6001, 6065)), 'final paired pool differs')
    require(result['frozen_candidate_RTL_sha256'] == OPTIMIZED, 'final candidate differs')
    require(display['audited_result_sha256'] == sha(ROOT / 'results/confirmation64.json'), 'report data authority differs')
    logs = {m: [] for m in METRICS}
    composite_logs = []
    for row in rows:
        seed = row['seed']
        for label in TREES:
            directory = ROOT / 'evidence/final64' / label / str(seed)
            require(parse_metrics(directory, seed) == row[label], 'final raw metric extraction differs')
            first = ROOT / 'evidence/ppa' / label / '5001/serv_synth_wrapper.pre-vpr.blif'
            require(blif_identity(directory / 'serv_synth_wrapper.pre-vpr.blif') == blif_identity(first), 'final netlist needs another proof')
        for metric in METRICS:
            ratio = row['optimized'][metric] / row['baseline'][metric]
            near(ratio, row['ratios'][metric], 'final per-pair ratio')
            logs[metric].append(math.log(ratio))
        composite = statistics.mean(logs[m][-1] for m in METRICS)
        near(math.exp(composite), row['composite_ratio'], 'final per-pair score')
        composite_logs.append(composite)
    logs['composite'] = composite_logs
    for metric, values in logs.items():
        mean = statistics.mean(values)
        se = statistics.stdev(values) / 8
        expected = result['statistics']['confidence']['composite'] if metric == 'composite' else result['statistics']['confidence']['metrics'][metric]
        near(mean, expected['mean_log_ratio'], 'final mean log ratio')
        near(mean - 1.6694022217068127 * se, expected['lower'], 'final lower acceptance bound')
        near(mean + 1.6694022217068127 * se, expected['upper'], 'final upper acceptance bound')
        point = display['metrics'][metric]
        near(math.exp(mean), point['ratio'], 'display ratio')
        near(100 * (1-math.exp(mean + 1.9983405425207417 * se)), point['lower_improvement_percent'], 'display lower interval')
        near(100 * (1-math.exp(mean - 1.9983405425207417 * se)), point['upper_improvement_percent'], 'display upper interval')
        ratios = [math.exp(value) for value in values]
        require(point['wins'] == sum(v < 1 for v in ratios) and point['ties'] == sum(v == 1 for v in ratios)
                and point['losses'] == sum(v > 1 for v in ratios), 'final win/tie/loss count differs')
    near(math.exp(statistics.mean(composite_logs)), result['statistics']['score'], 'final score')
    delay_lower = result['statistics']['confidence']['metrics']['critical_path_delay_ns']['lower']
    require(delay_lower > 0 and result['statistics']['acceptance_decision'] == 'evidence_regression', 'timing regression concealed')
    require(result['strict10_result_on_fixed64'] is False and result['editorial_publication_accepted'] is False
            and result['held_out_certification_12_completed'] is False, 'unsupported final acceptance claim')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-manifest', action='store_true')
    args = parser.parse_args(argv)
    if args.write_manifest:
        write_manifest()
        return 0
    verify_manifest()
    verify_rtl()
    verify_recorded_correctness()
    result = verify_measurements()
    verify_status(result)
    final = verify_final64()
    print('SERV 1.4.0 saved research evidence: PASS')
    print(f'development_pairs=12; improvement={result["improvement_percent"]:.4f}%')
    print(f'final_pairs=64; final_improvement={final["statistics"]["improvement_percent"]:.4f}%')
    print('timing_regression=1.9478%; acceptance=evidence_regression')
    print('held_out_certification_pairs=0; publication_accepted=False')
    print('Scope: saved evidence consistency; no fresh EDA execution or PPA certification.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (VerificationError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'SERV 1.4.0 saved research evidence: FAIL: {error}', file=sys.stderr)
        raise SystemExit(1) from error
