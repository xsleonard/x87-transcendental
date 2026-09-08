"""Audit native tie discrimination, corpus incorporation, and frozen sources."""
import json
from pathlib import Path
import subprocess
import sys

from compressed_guard import digest
from prepare import save

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = HERE.parent / 'tmp/fpatan-re'


def read(path):
    return json.loads(path.read_text())


def main():
    output = BASE / 'd0063-verification.json'
    assert not output.exists()
    job = BASE / 'd0063'
    manifest, complete = read(job / 'MANIFEST.json'), read(job / 'COMPLETE.json')
    hypothesis, score = read(job / 'STRUCTURAL-HYPOTHESIS.json'), read(job / 'SCORE.json')
    rules, dispatch = read(job / 'TIE-RULE-SCORE.json'), read(job / 'DISPATCHED.json')
    assert complete['state'] == 'OBSERVED'
    assert complete['rows'] == manifest['rows'] == score['counts']['rows'] == rules['counts']['rows'] == 872
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256'] == hypothesis['manifest_sha256']
    assert digest(job / 'STRUCTURAL-HYPOTHESIS.json') == dispatch['structural_hypothesis_sha256'] == rules['hypothesis_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert score['hardware_sha256'] == rules['hardware_sha256'] == complete['hardware_sha256']
    assert digest(job / 'SCORE.json') == rules['baseline_score_sha256']
    assert digest(job / 'CONTROL-DIFFERENCES.jsonl.gz') == hypothesis['sparse_predictions_sha256']
    assert rules['scorer_sha256'] == digest(HERE / 'score_d0046_ties.py')
    for name, sha in manifest['files'].items():
        assert digest(job / name) == sha
    for name, sha in manifest['source_pins'].items():
        assert digest(job / 'sources' / name) == sha == digest(HERE / name)
    assert manifest['counts']['selected_pairs'] == manifest['counts']['generated_pairs'] == 216
    for name, sha in hypothesis['mining_report_sha256'].items():
        assert digest(BASE / name / 'REPORT.json') == sha
    for name in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        preflight = read(job / name)
        assert preflight['rows'] == 872 and preflight['C_frozen_Python_differences'] == 0
        assert preflight['binary_sha256'] == read(BASE / 'd0046' / name)['binary_sha256']
    start, ledger = read(job / 'STARTED.json'), read(job / 'LEDGER-AUDIT.json')
    assert start['identity'].split()[1] == '00050654' and start['microcode'] == ['0x1']
    assert ledger['integrity'] == 'ok'
    assert any(row[1:] == ['d0063', 'OBSERVED', 872] for row in ledger['compressed_batches'])
    assert read(job / 'SSH_CAPTURE_RETURN.json')['returncode'] == 0
    counts = rules['counts']
    assert counts['node0:separators:parity0'] == hypothesis['counts']['node0:separators:parity0'] == 10
    assert counts['node0:separators:parity1'] == hypothesis['counts']['node0:separators:parity1'] == 8
    identified = counts['baseline_union_misses'] == 0
    if identified:
        for rule, expected in (('nearest-even', 0), ('nearest-odd', 18), ('ties-away', 10), ('ties-zero', 8)):
            assert counts[f'node0:{rule}:union_misses'] == expected
        for key in ('candidate_misses', 'candidate_C1_misses', 'exception_misses', 'before_exception_misses'):
            assert score['counts'][key] == 0
    assert score['counts']['PC_value_or_status_differences'] == 0
    catalog_path = HERE / 'corpus-v1/CATALOG-D0063.json'
    catalog = read(catalog_path)
    assert catalog['counts']['rows'] == 7126040 and len(catalog['packs']) == 22
    assert catalog['exact_tuple_duplicates'] == 0
    assert catalog['previous_catalog']['sha256'] == digest(HERE / 'corpus-v1/CATALOG-D0061.json')
    for pack in catalog['packs'].values():
        assert digest(HERE / 'corpus-v1' / pack['path']) == pack['sha256']
    assert catalog['extension_manifest_sha256'] == digest(HERE / 'corpus-v1/extensions/d0063/MANIFEST.json')
    filter_receipt = BASE / 'd0059-filter-verification.json'
    filtering = read(filter_receipt)
    assert filtering['status'] == 'PASS_CORRECTED_SHORT_ODD_FILTER_AUDIT'
    for path, sha in filtering['evidence_sha256'].items():
        assert digest(Path(path)) == sha
    tests = subprocess.run([sys.executable, str(HERE / 'test_d0063_discriminators.py')], text=True, capture_output=True)
    assert tests.returncode == 0, tests.stderr
    paper = read(BASE / 'd0030-paper-verification.json')
    source_manifest = HERE / 'paper/generated/SOURCE-MANIFEST.json'
    assert digest(source_manifest) == paper['source_manifest_sha256']
    for path, sha in read(source_manifest)['files'].items():
        assert digest(ROOT / path) == sha
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == paper['pdf_sha256']
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    paths = [job / name for name in ('MANIFEST.json', 'STRUCTURAL-HYPOTHESIS.json',
        'DISPATCHED.json', 'STARTED.json', 'COMPLETE.json', 'SCORE.json', 'TIE-RULE-SCORE.json',
        'C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json', 'LEDGER-AUDIT.json')]
    paths += [catalog_path, filter_receipt, BASE / 'd0059-short-wide-replay/REPORT.json', BASE / 'd0058-filter-failure.json', BASE / 'd0057-verification.json', BASE / 'd0061-verification.json', BASE / 'd0062-long-prefix2/REPORT.json', BASE / 'd0060-offsets-verification/REPORT.json']
    previous = read(BASE / 'd0061-verification.json')
    assert previous['status'] == 'PASS_AUTHENTICATED_TIE_DISCRIMINATION_AUDIT'
    resolved = dict(previous['identified_among_fixed_rules'])
    assert resolved == {'table:correction_sum': 'nearest-even', 'direct:even_inner_sum': 'nearest-even', 'table:odd_sum': 'nearest-even'}
    if identified:
        resolved['direct:odd_inner_sum'] = 'nearest-even'
    unresolved = []
    if not identified:
        unresolved.append('direct:odd_inner_sum')
    save(output, dict(status='PASS_AUTHENTICATED_TIE_DISCRIMINATION_AUDIT',
        baseline_misses=counts['baseline_union_misses'], native_counts=score['counts'],
        tie_rule_counts=counts, identified_among_fixed_rules=resolved, unresolved_nodes=unresolved,
        new_skylake_rows=872, previous_two_context_rows=7097584, corpus_rows=7126040,
        tests=dict(returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr),
        evidence_sha256={str(path.relative_to(ROOT)): digest(path) for path in paths},
        source_sha256=digest(Path(__file__)), hardware_executed=False,
        numerical_model_changed=False, paper_changed=False, goal_complete=False,
        limits='Fixed-rule discrimination in the frozen operation graph and recorded Skylake context; no universal silicon proof or transfer to i7 for the new extension is claimed.'))
    print('PASS authenticated audit; identified:', resolved, '; unresolved:', unresolved, flush=True)


if __name__ == '__main__':
    main()


