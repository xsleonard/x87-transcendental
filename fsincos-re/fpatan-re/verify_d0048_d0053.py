"""Authenticate the new search evidence without executing hardware."""
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

from compressed_guard import digest
from d0045_tie_observability import target_and_correction
from d0053_exact_local_tie_boxes import local_domains
from d0049_algebraic_tie_preimages import invert_target, fraction, graph
import d0031_internal_rounding_coverage as audit
from prepare import save

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = HERE.parent / 'tmp/fpatan-re'


def read(path):
    return json.loads(path.read_text())


def main():
    output = BASE / 'd0048-d0053-verification.json'
    assert not output.exists()
    pins, searches, exact_boxes = {}, {}, {}
    changed_squares, pending = {node: set() for node in range(3)}, []
    for name in ('d0049-node2-pilot', 'd0049-node0-wide', 'd0049-node1-wide',
                 'd0049-node2-wide', 'd0049-node2-expanded',
                 'd0053-node0-box28', 'd0053-node0-box36', 'd0053-node1-box36'):
        directory = BASE / name
        report = read(directory / 'REPORT.json')
        assert report['hardware_executed'] is False
        assert digest(directory / 'targets.tsv') == report['target_sha256']
        for source, sha in report['source_sha256'].items():
            assert digest(HERE / source) == sha
        counts, seen = Counter(), set()
        local = name.startswith('d0053')
        with (directory / 'targets.tsv').open() as stream:
            for line in stream:
                p = line.split()
                if p[0] != 'T':
                    continue
                node, exponent, um = int(p[1]), int(p[3]), int(p[4], 16)
                counts['ties'] += 1
                counts['H_changed'] += int(p[6])
                counts['first_outer_changed'] += int(p[7])
                counts['parity' + p[5]] += 1
                if int(p[6]):
                    changed_squares[node].add((exponent, um))
                if local:
                    assert um not in seen
                    seen.add(um)
                    t, h = target_and_correction(node, um * audit.two(exponent - 63))
                    _, other = target_and_correction(node, um * audit.two(exponent - 63), True)
                    self_event = audit.event(t, 64)
                    assert self_event['relation'] == 'tie' and self_event['parity'] == int(p[5])
                    assert (h != other) == bool(int(p[6]))
        for key, value in counts.items():
            assert report['counts'].get(key, 0) == value
        if local:
            expected, total = set(), 0
            domains = local_domains(report['node'], report['square_exponent'],
                int(report['low'], 16), int(report['high'], 16))
            assert domains == report['domains']
            for d in domains:
                for j in range(d['count']):
                    total += 1
                    expected.update(invert_target(d, d['first'] + j * d['modulus']))
            assert total == report['counts']['target_searches'] and seen == expected
            exact_boxes[name] = dict(low=report['low'], high=report['high'], counts=report['counts'],
                full_fraction_replay='PASS', complete_inverse_reenumeration='PASS')
        else:
            searches[name] = report['counts']
        pending += report['witnesses']
        pins[str(directory / 'REPORT.json')] = digest(directory / 'REPORT.json')
        pins[str(directory / 'targets.tsv')] = digest(directory / 'targets.tsv')
        print('Authenticated', name, dict(counts), flush=True)

    legacy = {}
    for node in range(3):
        directory = BASE / f'd0047-node{node}-carry'
        original = read(directory / 'REPORT.json')
        failed = read(directory / 'CVC5-CROSSCHECK.json')
        assert digest(directory / 'query.smt2') == original['query_sha256'] == failed['query_sha256']
        assert failed['returncode'] == 1 and failed['outcome']['result'] == 'error'
        assert "AssertionError: ['unknown (TIMEOUT)']" in failed['stderr']
        assert digest(HERE / 'd0048_carry_query_crosscheck.py') == failed['source_sha256']
        legacy[str(node)] = dict(solver_text='unknown (TIMEOUT)', wrapper_result='error',
                                original_preserved=True)
        for name in ('REPORT.json', 'query.smt2', 'CVC5-CROSSCHECK.json'):
            pins[str(directory / name)] = digest(directory / name)

    queries = {}
    for name in ('node0-fixed', 'node1-fixed', 'node0-box28', 'node0-box36', 'node1-box36'):
        directory = BASE / ('d0050-' + name)
        report = read(directory / 'REPORT.json')
        assert digest(directory / 'query.smt2') == report['query_sha256']
        for source, sha in report['source_sha256'].items():
            assert digest(Path(source)) == sha
        expected = 'unsat' if name == 'node0-fixed' else 'sat' if name == 'node1-fixed' else 'unknown'
        assert report['result'] == expected
        queries[name] = dict(result=report['result'], low=report['low'], high=report['high'])
        for file in ('REPORT.json', 'query.smt2'):
            pins[str(directory / file)] = digest(directory / file)
        cross = directory / 'CVC5.json'
        if cross.exists():
            receipt = read(cross)
            assert receipt['returncode'] == 0 and receipt['outcome']['result'] == 'unknown'
            assert receipt['outcome']['reason'] == 'TIMEOUT'
            assert receipt['query_sha256'] == report['query_sha256']
            assert receipt['source_sha256'] == digest(HERE / 'd0051_solver_crosscheck.py')
            pins[str(cross)] = digest(cross)

    barrier = BASE / 'd0052-wide-masking.json'
    for path, sha in read(barrier)['artifact_sha256'].items():
        assert digest(Path(path)) == sha
    pins[str(barrier)] = digest(barrier)
    tests = {}
    for name in ('test_d0049_algebraic_inverse.py', 'test_d0050_d0051.py', 'test_d0053_local_boxes.py'):
        run = subprocess.run([sys.executable, str(HERE / name)], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        tests[name] = dict(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
        pins[str(HERE / name)] = digest(HERE / name)
    paper = read(BASE / 'd0030-paper-verification.json')
    manifest = HERE / 'paper/generated/SOURCE-MANIFEST.json'
    assert digest(manifest) == paper['source_manifest_sha256']
    for path, sha in read(manifest)['files'].items():
        assert digest(ROOT / path) == sha
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == paper['pdf_sha256']
    previous = read(BASE / 'd0045-d0046-verification.json')
    catalog = HERE / 'corpus-v1/CATALOG-D0046.json'
    assert digest(catalog) == previous['evidence_sha256'][str(catalog.relative_to(ROOT))]
    assert previous['identified_among_fixed_rules'] == {'table:correction_sum': 'nearest-even'}
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    save(output, dict(status='PASS_SEARCH_AND_LOCAL_BOX_AUDIT', search_counts=searches,
        exact_local_boxes=exact_boxes, unique_changed_H_squares={str(n): len(s) for n, s in changed_squares.items()},
        pending_endpoint_candidates=pending, legacy_cvc5=legacy, affine_queries=queries,
        tests=tests, evidence_sha256=pins, source_sha256=digest(Path(__file__)),
        identified_among_fixed_rules=previous['identified_among_fixed_rules'],
        unresolved_nodes=previous['unresolved_nodes'], numerical_model_changed=False,
        paper_changed=False, corpus_changed=False, hardware_executed=False, goal_complete=False))
    print('PASS_SEARCH_AND_LOCAL_BOX_AUDIT; unresolved:', previous['unresolved_nodes'], flush=True)


if __name__ == '__main__':
    main()
