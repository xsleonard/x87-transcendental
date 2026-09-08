"""Authenticate new adversaries and the complete two-context corpus comparison."""
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


def authenticate_job(name):
    job = BASE / name
    manifest, complete = read(job / 'MANIFEST.json'), read(job / 'COMPLETE.json')
    score, ledger = read(job / 'SCORE.json'), read(job / 'LEDGER-AUDIT.json')
    assert complete['state'] == 'OBSERVED'
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert complete['hardware_sha256'] == score['hardware_sha256']
    assert manifest['rows'] == complete['rows'] == score['counts']['rows']
    assert ledger['integrity'] == 'ok'
    assert any(row[1:] == [name, 'OBSERVED', manifest['rows']] for row in ledger['compressed_batches'])
    for file, sha in manifest['files'].items():
        assert digest(job / file) == sha
    for file, sha in manifest['source_pins'].items():
        assert digest(job / 'sources' / file) == sha == digest(HERE / file)
    for file in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        preflight = read(job / file)
        assert preflight['rows'] == manifest['rows'] and preflight['C_frozen_Python_differences'] == 0
        assert preflight['binary_sha256'] == read(BASE / 'd0040' / file)['binary_sha256']
    assert read(job / 'SSH_CAPTURE_RETURN.json')['returncode'] == 0
    return score


def main():
    scores = {name: authenticate_job(name) for name in ('d0042', 'd0043', 'd0044')}
    assert scores['d0042']['counts']['rows'] == scores['d0044']['counts']['rows'] == 2485048
    assert scores['d0043']['counts']['rows'] == 4612536
    cross = {}
    for name in ('d0043', 'd0044'):
        job = BASE / name
        report = read(job / 'CROSS-CPU-VERIFICATION.json')
        assert report['verifier_sha256'] == digest(HERE / 'finalize_d0043_i7.py')
        for file, sha in report['evidence_sha256'].items():
            assert digest(job / file) == sha
        cross[name] = report['counts']
    hypothesis = read(BASE / 'd0042/STRUCTURAL-HYPOTHESIS.json')
    assert digest(BASE / 'd0042/STRUCTURAL-HYPOTHESIS.json') == read(BASE / 'd0042/DISPATCHED.json')['structural_hypothesis_sha256']
    assert digest(BASE / 'd0042/CONTROL-DIFFERENCES.jsonl.gz') == hypothesis['sparse_predictions_sha256']
    control = read(BASE / 'd0042/NODE-CONTROL-SCORE.json')
    assert control['hypothesis_sha256'] == digest(BASE / 'd0042/STRUCTURAL-HYPOTHESIS.json')
    assert control['baseline_score_sha256'] == digest(BASE / 'd0042/SCORE.json')
    assert control['source_sha256'] == digest(HERE / 'score_d0042_controls.py')
    mining = read(BASE / 'd0041-inner-ties/REPORT.json')
    for name, sha in mining['source_sha256'].items():
        assert digest(HERE / name) == sha
    assert digest(BASE / 'd0041-inner-ties/candidate-pool.tsv') == mining['pool_sha256'] == hypothesis['pool_sha256']
    assert digest(BASE / 'd0041-inner-ties/REPORT.json') == hypothesis['mining_report_sha256']
    paper = read(BASE / 'd0030-paper-verification.json')
    source_manifest = HERE / 'paper/generated/SOURCE-MANIFEST.json'
    assert digest(source_manifest) == paper['source_manifest_sha256']
    for path, sha in read(source_manifest)['files'].items():
        assert digest(ROOT / path) == sha
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == paper['pdf_sha256']
    corpus_path = HERE / 'corpus-v1/CATALOG-D0042.json'
    corpus = read(corpus_path)
    assert len(corpus['packs']) == 18 and corpus['counts']['rows'] == 7097584
    assert corpus['exact_tuple_duplicates'] == 0
    for pack in corpus['packs'].values():
        assert digest(HERE / 'corpus-v1' / pack['path']) == pack['sha256']
    assert digest(HERE / 'corpus-v1/CATALOG-D0040.json') == corpus['previous_catalog']['sha256']
    assert digest(HERE / 'corpus-v1/extensions/d0042/MANIFEST.json') == corpus['extension_manifest_sha256']
    assert cross['d0043']['rows'] + cross['d0044']['rows'] == corpus['counts']['rows']
    covered_packs = {}
    identity_paths = []
    for job_name in ('d0043', 'd0044'):
        reference = read(BASE / job_name / 'SKYLAKE-REFERENCE.json')
        i7_start_path = BASE / job_name / 'STARTED.json'
        i7_start = read(i7_start_path)
        assert i7_start['identity'].split()[1] == '000506e3'
        assert i7_start['microcode'] == ['0xf0']
        identity_paths.append(i7_start_path)
        for name, source in reference['source_packs'].items():
            assert name not in covered_packs
            pack = corpus['packs'][name]
            assert source['rows'] == pack['counts']['rows']
            assert source['input_sha256'] == pack['sha256']
            assert source['source_manifest_sha256'] == pack['source_manifest_sha256']
            start_path = BASE / name / 'STARTED.json'
            start = read(start_path)
            assert start['identity'].split()[1] == '00050654'
            assert start['microcode'] == ['0x1']
            identity_paths.append(start_path)
            covered_packs[name] = dict(i7_job=job_name, rows=source['rows'],
                                      input_sha256=source['input_sha256'])
    assert set(covered_packs) == set(corpus['packs'])
    tests = {}
    for name in ('test_d0041_d0043.py', 'test_compressed_guard.py',
                 'test_compressed_pipeline.py', 'test_score_stream.py'):
        result = subprocess.run([sys.executable, str(HERE / name)],
                                text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        tests[name] = dict(returncode=result.returncode, stdout=result.stdout,
                           stderr=result.stderr, source_sha256=digest(HERE / name))
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    has_differences = any(score['counts'][key] for score in scores.values() for key in
        ('candidate_misses', 'candidate_C1_misses', 'exception_misses', 'before_exception_misses'))
    has_differences |= any(value for counts in cross.values()
                           for key, value in counts.items() if key != 'rows')
    paths = [BASE / 'd0041-inner-ties/REPORT.json', BASE / 'd0041-inner-ties/SANITIZED-MINER.json',
        BASE / 'd0042/NODE-CONTROL-SCORE.json', BASE / 'd0043/CROSS-CPU-VERIFICATION.json',
        BASE / 'd0044/CROSS-CPU-VERIFICATION.json', corpus_path]
    paths.extend(identity_paths)
    for name in scores:
        paths.extend(BASE / name / file for file in ('MANIFEST.json', 'COMPLETE.json', 'SCORE.json', 'LEDGER-AUDIT.json'))
    save(BASE / 'd0041-d0044-verification.json', dict(
        status='PASS_EVIDENCE_WITH_DIFFERENCES' if has_differences else 'PASS',
        observed_model_or_transfer_differences=has_differences,
        new_skylake_rows=2485048, corpus_rows_per_cpu=7097584, corpus_packs=18,
        skylake_prospective_V7_rows=4938688, scores={k: v['counts'] for k, v in scores.items()},
        cross_cpu_counts=cross, node_control_counts=control['counts'],
        tests=tests, two_context_pack_coverage=covered_packs,
        cpu_contexts=dict(skylake=dict(signature='00050654', microcode='0x1'),
                          i7=dict(signature='000506e3', microcode='0xf0')),
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        verifier_sha256=digest(Path(__file__)), numerical_model_changed=False,
        paper_changed=False, goal_complete=False, hardware_executed=False,
        limits='All current corpus inputs were compared on these two CPU/configuration contexts. This is not exhaustive raw80 coverage, all-generation transfer, or identification of masked internal tie behavior.'))
    print('PASS evidence audit; observed model/transfer differences:', has_differences,
          '; unique corpus rows per CPU:', corpus['counts']['rows'], flush=True)


if __name__ == '__main__':
    main()
