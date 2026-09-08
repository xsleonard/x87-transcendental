"""Authenticate the complete D0037-D0040 evidence chain without new hardware."""
import json
from pathlib import Path
import subprocess
import sys

from compressed_guard import digest
from prepare import save
import d0038_numerator_width_certificate as certificate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = HERE.parent / 'tmp/fpatan-re'


def read(path):
    return json.loads(path.read_text())


def main():
    job = BASE / 'd0040'
    manifest = read(job / 'MANIFEST.json')
    complete = read(job / 'COMPLETE.json')
    dispatch = read(job / 'DISPATCHED.json')
    hypothesis = read(job / 'STRUCTURAL-HYPOTHESIS.json')
    score = read(job / 'SCORE.json')
    control = read(job / 'CORRECTION-CONTROL-SCORE.json')
    assert complete['state'] == 'OBSERVED'
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256'] == hypothesis['manifest_sha256']
    assert digest(job / 'STRUCTURAL-HYPOTHESIS.json') == dispatch['structural_hypothesis_sha256'] == control['hypothesis_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert complete['hardware_sha256'] == score['hardware_sha256'] == control['hardware_sha256']
    assert digest(job / 'SCORE.json') == control['baseline_score_sha256']
    for name, expected in manifest['files'].items():
        assert digest(job / name) == expected
    for name, expected in manifest['source_pins'].items():
        assert digest(job / 'sources' / name) == expected
        assert digest(HERE / name) == expected
    assert digest(job / 'correction-ties-odd.txt.gz') == hypothesis['alternative_predictions_sha256']
    rows = manifest['rows']
    assert rows == complete['rows'] == score['counts']['rows'] == control['counts']['rows'] == 956608
    for name in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        preflight = read(job / name)
        assert preflight['rows'] == rows and preflight['C_frozen_Python_differences'] == 0
        assert preflight['binary_sha256'] == read(BASE / 'd0036' / name)['binary_sha256']
    assert read(job / 'SSH_CAPTURE_RETURN.json')['returncode'] == 0
    ledger = read(job / 'LEDGER-AUDIT.json')
    assert ledger['integrity'] == 'ok'
    assert any(batch[1:] == ['d0040', 'OBSERVED', rows] for batch in ledger['compressed_batches'])
    mining_path = BASE / 'd0039-correction-ties/REPORT.json'
    mining = read(mining_path)
    assert digest(mining_path) == hypothesis['mining_report_sha256']
    assert digest(BASE / 'd0039-correction-ties/candidate-pool.tsv') == mining['pool_sha256'] == hypothesis['candidate_pool_sha256']
    for name, expected in mining['source_sha256'].items():
        assert digest(HERE / name) == expected
    census = read(BASE / 'd0037-polynomial-node-census/REPORT.json')
    for name, expected in census['source_sha256'].items():
        assert digest(HERE / name) == expected
    assert json.loads(json.dumps(certificate.build())) == read(BASE / 'd0038-numerator-width-certificate.json')
    paper = read(BASE / 'd0030-paper-verification.json')
    source_manifest = HERE / 'paper/generated/SOURCE-MANIFEST.json'
    assert digest(source_manifest) == paper['source_manifest_sha256']
    for name, expected in read(source_manifest)['files'].items():
        assert digest(ROOT / name) == expected
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == paper['pdf_sha256']
    corpus_path = HERE / 'corpus-v1/CATALOG-D0040.json'
    corpus = read(corpus_path)
    assert corpus['counts']['rows'] == 3655928 + rows and corpus['exact_tuple_duplicates'] == 0
    assert digest(HERE / 'corpus-v1/CATALOG-D0036.json') == corpus['previous_catalog']['sha256']
    for pack in corpus['packs'].values():
        assert digest(HERE / 'corpus-v1' / pack['path']) == pack['sha256']
    assert digest(HERE / 'corpus-v1/extensions/d0040/MANIFEST.json') == corpus['extension_manifest_sha256']
    checks = []
    for command in ([sys.executable, str(HERE / 'test_d0037_d0040.py')], ['git', 'diff', '--check']):
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        checks.append(dict(command=command, returncode=result.returncode,
                           stdout=result.stdout, stderr=result.stderr))
    missed = control['counts']['baseline_union_misses']
    assert missed == len(control['baseline_misses'])
    if not missed:
        assert all(score['counts'][k] == 0 for k in ('candidate_misses', 'candidate_C1_misses',
            'exception_misses', 'before_exception_misses'))
        assert control['counts']['control_union_misses'] == hypothesis['counts']['union_separators'] == 708
    paths = [job / name for name in ('MANIFEST.json', 'STRUCTURAL-HYPOTHESIS.json',
        'C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json', 'DISPATCHED.json', 'COMPLETE.json',
        'SCORE.json', 'CORRECTION-CONTROL-SCORE.json', 'LEDGER-AUDIT.json')]
    paths += [mining_path, BASE / 'd0037-polynomial-node-census/REPORT.json',
              BASE / 'd0038-numerator-width-certificate.json', corpus_path]
    save(BASE / 'd0040-adversarial-verification.json', dict(
        status='PASS_EVIDENCE_AUDIT_MODEL_FALSIFIED' if missed else 'PASS',
        model_falsified=bool(missed), native_rows=rows, baseline_counts=score['counts'],
        control_counts=control['counts'], scale_groups=control['exact_scale_groups'],
        corpus_rows=corpus['counts']['rows'], corpus_packs=len(corpus['packs']),
        prospective_V7_observations=1497032 + rows,
        evidence_sha256={str(path.relative_to(ROOT)): digest(path) for path in paths},
        analysis_source_sha256={path.name: digest(path) for path in
            (Path(__file__), HERE / 'score_d0040_control.py', HERE / 'extend_corpus_d0040.py', HERE / 'test_d0037_d0040.py')},
        checks=checks, numerical_source_sha256=digest(HERE / 'fpatan_candidate.c'),
        paper_unchanged=True, pdf_sha256=paper['pdf_sha256'],
        new_hardware_executed=False, goal_complete=False,
        limits='One bounded prospective campaign on the reported Skylake context, not exhaustive hardware equivalence or complete adversarial coverage.'))
    print('PASS evidence audit; model falsified:', bool(missed), '; corpus rows:', corpus['counts']['rows'], flush=True)


if __name__ == '__main__':
    main()
