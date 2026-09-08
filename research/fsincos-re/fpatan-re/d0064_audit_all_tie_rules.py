"""Re-derive all four fixed-rule identifications from authenticated raw rows.

This audit does not treat a PASS report as the proof. It reconstructs each
targeted counterfactual from the exact graph, validates the frozen sparse
controls, parses every native result, and independently counts which rules
survive. The result is scoped to four fixed local rules in the reconstructed
graph and recorded Skylake context, not arbitrary state-dependent silicon.
"""
from collections import Counter
import gzip
import json
from pathlib import Path
import subprocess
import sys

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare_d0042 import values
from protocol import validate_output
from prepare import save

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = HERE.parent / 'tmp/fpatan-re'
TARGETS = (
    (0, 'direct:odd_inner_sum', 'd0063'),
    (1, 'direct:even_inner_sum', 'd0057'),
    (2, 'table:odd_sum', 'd0061'),
    (3, 'table:correction_sum', 'd0046'),
)
RULES = ('nearest-even', 'nearest-odd', 'ties-away', 'ties-zero')


def read(path):
    return json.loads(path.read_text())


def audit_job(node, name, job_name):
    job = BASE / job_name
    manifest, complete = read(job / 'MANIFEST.json'), read(job / 'COMPLETE.json')
    hypothesis, dispatch = read(job / 'STRUCTURAL-HYPOTHESIS.json'), read(job / 'DISPATCHED.json')
    recorded = read(job / 'TIE-RULE-SCORE.json')
    assert complete['state'] == 'OBSERVED'
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256'] == hypothesis['manifest_sha256']
    assert digest(job / 'STRUCTURAL-HYPOTHESIS.json') == dispatch['structural_hypothesis_sha256'] == recorded['hypothesis_sha256']
    assert digest(job / 'CONTROL-DIFFERENCES.jsonl.gz') == hypothesis['sparse_predictions_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    for filename, sha in manifest['files'].items():
        assert digest(job / filename) == sha
    for filename, sha in manifest['source_pins'].items():
        assert digest(job / 'sources' / filename) == sha == digest(HERE / filename)
    for filename in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        preflight = read(job / filename)
        assert preflight['rows'] == manifest['rows'] and preflight['C_frozen_Python_differences'] == 0
    start = read(job / 'STARTED.json')
    assert start['identity'].split()[1] == '00050654' and start['microcode'] == ['0x1']
    ledger = read(job / 'LEDGER-AUDIT.json')
    assert ledger['integrity'] == 'ok'
    assert any(row[0] == '00050654:0x1' and row[1:] == [job_name, 'OBSERVED', manifest['rows']]
               for row in ledger['compressed_batches'])
    overrides = {}
    with gzip.open(job / 'CONTROL-DIFFERENCES.jsonl.gz', 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            if row['node'] == node:
                assert row['id'] not in overrides
                overrides[row['id']] = row
    counts, seen_modes, seen_overrides = Counter(), set(), set()
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'predictions.txt.gz', 'rt') as predictions, \
         gzip.open(job / 'hardware.txt.gz', 'rt') as hardware:
        for line, frozen, native in zip(inputs, predictions, hardware, strict=True):
            ident, rc, pc, ys, ym, xs, xm = line.split()
            observed = validate_output(native, line)
            y = audit.Raw80(int(ys, 16), int(ym, 16))
            x = audit.Raw80(int(xs, 16), int(xm, 16))
            base_angles, alternative_angles, events = values(audit.core_key(y, x))
            event, parity = events[node]
            quadrant = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
            sign = -1 if y.se & 32768 else 1
            base, c1 = audit.SPEC['pack_angle'](sign * base_angles[quadrant], rc.upper())
            reference = (base.se, base.sig, c1, 32, 0)
            assert frozen.split()[0] == ident
            assert reference == tuple(int(word, 16) for word in frozen.split()[1:])
            alternate = reference
            if event == 'tie':
                result, flag = audit.SPEC['pack_angle'](sign * alternative_angles[node][quadrant], rc.upper())
                alternate = (result.se, result.sig, flag, 32, 0)
                counts[f'target_ties:parity{parity}'] += 1
            override = overrides.get(ident)
            assert alternate == (tuple(override['alternative']) if override else reference)
            if override:
                assert override['parity'] == parity and event == 'tie' and alternate != reference
                seen_overrides.add(ident)
                counts[f'endpoint_separators:parity{parity}'] += 1
            actual = (observed['se'], observed['sig'], observed['C1'],
                      observed['sw'] & 63, observed['before'] & 63)
            counts['rows'] += 1
            counts['baseline_full_misses'] += actual != reference
            seen_modes.add(rc)
            for rule in RULES:
                use_other = event == 'tie' and (rule == 'nearest-odd'
                    or (rule == 'ties-away' and parity == 0)
                    or (rule == 'ties-zero' and parity == 1))
                prediction = alternate if use_other else reference
                counts[rule + ':union_misses'] += actual != prediction
    assert seen_modes == {'rn', 'rd', 'ru', 'rz'}
    assert seen_overrides == set(overrides)
    assert counts['rows'] == manifest['rows'] == complete['rows']
    assert counts['baseline_full_misses'] == counts['nearest-even:union_misses'] == 0
    assert all(counts[f'endpoint_separators:parity{p}'] > 0 for p in (0, 1))
    assert all(counts[rule + ':union_misses'] > 0 for rule in RULES[1:])
    for rule in RULES:
        assert counts[rule + ':union_misses'] == recorded['counts'][f'node{node}:{rule}:union_misses']
    for parity in (0, 1):
        assert counts[f'endpoint_separators:parity{parity}'] == hypothesis['counts'][f'node{node}:separators:parity{parity}']
    print('PASS independently reconstructed hardware discrimination:', name, dict(counts), flush=True)
    return dict(node=node, name=name, job=job_name, identified_rule='nearest-even',
                counts=counts, context='00050654:0x1',
                manifest_sha256=digest(job / 'MANIFEST.json'),
                hypothesis_sha256=digest(job / 'STRUCTURAL-HYPOTHESIS.json'),
                complete_sha256=digest(job / 'COMPLETE.json'),
                hardware_sha256=complete['hardware_sha256'],
                hardware_gzip_sha256=complete['hardware_gzip_sha256'])


def main():
    output = BASE / 'd0064-all-four-tie-rules.json'
    assert not output.exists()
    results = [audit_job(*target) for target in TARGETS]
    assert {r['name'] for r in results} == {name for _, name, _ in TARGETS}
    assert sum(r['counts']['rows'] for r in results) == 28456
    receipt = read(BASE / 'd0063-verification.json')
    assert receipt['status'] == 'PASS_AUTHENTICATED_TIE_DISCRIMINATION_AUDIT'
    assert receipt['identified_among_fixed_rules'] == {r['name']: 'nearest-even' for r in results}
    assert receipt['unresolved_nodes'] == []
    catalog_path = HERE / 'corpus-v1/CATALOG-D0063.json'
    catalog = read(catalog_path)
    assert catalog['counts']['rows'] == 7126040 and catalog['exact_tuple_duplicates'] == 0
    for _, _, job in TARGETS:
        pack = catalog['packs'][job]
        assert digest(HERE / 'corpus-v1' / pack['path']) == pack['sha256']
        assert pack['sha256'] == digest(BASE / job / 'inputs.txt.gz')
    publication = read(BASE / 'd0030-paper-verification.json')
    source_manifest = HERE / 'paper/generated/SOURCE-MANIFEST.json'
    assert digest(source_manifest) == publication['source_manifest_sha256']
    for path, sha in read(source_manifest)['files'].items():
        assert digest(ROOT / path) == sha
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == publication['pdf_sha256']
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'test_d0059_short_boundary.py',
        'test_d0061_discriminators.py', 'test_d0063_discriminators.py'],
        cwd=HERE, text=True, capture_output=True)
    assert tests.returncode == 0, tests.stderr
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    save(output, dict(status='PASS_ALL_FOUR_FIXED_TIE_RULES_IDENTIFIED',
        objective='figure out which tie rule is the correct rule', results=results,
        all_four_named_additions_identified=True, unresolved_target_additions=[],
        combined_challenge_rows=28456, current_corpus_rows=7126040,
        tests=dict(returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr),
        final_native_audit_sha256=digest(BASE / 'd0063-verification.json'),
        corpus_catalog_sha256=digest(catalog_path), source_sha256=digest(Path(__file__)),
        production_and_publication_unchanged=True, hardware_executed=False,
        scope='Uniquely nearest/even among nearest/even, nearest/odd, ties-away and ties-zero at each of the four named RN64 additions in the fixed numerical graph and recorded Skylake 00050654:0x1 context. Both retained parities have endpoint-visible native counterexamples to alternatives. Not a universal numerical, arbitrary state-dependent, or cross-CPU proof.'))
    print('PASS all four fixed tie rules independently identified as nearest/even.', flush=True)


if __name__ == '__main__':
    main()
