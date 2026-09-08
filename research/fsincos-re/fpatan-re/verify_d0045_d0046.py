"""Authenticate the tie-discrimination evidence without new hardware."""
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
    paths = []
    searches = {}
    for name in ('node0-upper', 'node1-upper', 'node2-upper', 'node3-upper', 'node3-sanitized'):
        directory = BASE / ('d0045-' + name)
        report = read(directory / 'REPORT.json')
        assert report['status'] == 'VERIFIED_BOUNDED_TIE_OBSERVABILITY_SEARCH'
        assert digest(directory / 'miner.tsv') == report['target_sha256']
        assert digest(directory / 'miner.log') == report['log_sha256']
        for source, sha in report['source_sha256'].items():
            assert digest(HERE / source) == sha
        searches[name] = report['counts']
        paths.append(directory / 'REPORT.json')
    job = BASE / 'd0046'
    manifest, complete = read(job / 'MANIFEST.json'), read(job / 'COMPLETE.json')
    score, rules = read(job / 'SCORE.json'), read(job / 'TIE-RULE-SCORE.json')
    hypothesis = read(job / 'STRUCTURAL-HYPOTHESIS.json')
    assert complete['state'] == 'OBSERVED'
    assert complete['rows'] == manifest['rows'] == score['counts']['rows'] == rules['counts']['rows'] == 22064
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256'] == hypothesis['manifest_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert score['hardware_sha256'] == rules['hardware_sha256'] == complete['hardware_sha256']
    assert digest(job / 'SCORE.json') == rules['baseline_score_sha256']
    assert digest(job / 'STRUCTURAL-HYPOTHESIS.json') == rules['hypothesis_sha256']
    assert rules['hypothesis_sha256'] == read(job / 'DISPATCHED.json')['structural_hypothesis_sha256']
    assert digest(job / 'CONTROL-DIFFERENCES.jsonl.gz') == hypothesis['sparse_predictions_sha256']
    assert digest(BASE / 'd0045-node3-upper/REPORT.json') == hypothesis['mining_report_sha256']
    assert digest(HERE / 'score_d0046_ties.py') == rules['scorer_sha256']
    for file, sha in manifest['files'].items():
        assert digest(job / file) == sha
    for file, sha in manifest['source_pins'].items():
        assert digest(job / 'sources' / file) == sha == digest(HERE / file)
    for file in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        preflight = read(job / file)
        assert preflight['rows'] == manifest['rows'] and preflight['C_frozen_Python_differences'] == 0
        assert preflight['binary_sha256'] == read(BASE / 'd0042' / file)['binary_sha256']
    start, ledger = read(job / 'STARTED.json'), read(job / 'LEDGER-AUDIT.json')
    assert start['identity'].split()[1] == '00050654' and start['microcode'] == ['0x1']
    assert ledger['integrity'] == 'ok'
    assert any(row[1:] == ['d0046', 'OBSERVED', 22064] for row in ledger['compressed_batches'])
    assert read(job / 'SSH_CAPTURE_RETURN.json')['returncode'] == 0
    counts = rules['counts']
    if not counts['baseline_union_misses']:
        assert all(score['counts'][key] == 0 for key in
            ('candidate_misses', 'candidate_C1_misses', 'exception_misses', 'before_exception_misses'))
        for rule, expected in (('nearest-even', 0), ('nearest-odd', 366), ('ties-away', 224), ('ties-zero', 142)):
            assert counts[f'node3:{rule}:union_misses'] == expected
    catalog_path = HERE / 'corpus-v1/CATALOG-D0046.json'
    catalog = read(catalog_path)
    assert catalog['counts']['rows'] == 7119648 and len(catalog['packs']) == 19
    assert catalog['exact_tuple_duplicates'] == 0
    assert catalog['previous_catalog']['sha256'] == digest(HERE / 'corpus-v1/CATALOG-D0042.json')
    for pack in catalog['packs'].values():
        assert digest(HERE / 'corpus-v1' / pack['path']) == pack['sha256']
    assert catalog['extension_manifest_sha256'] == digest(HERE / 'corpus-v1/extensions/d0046/MANIFEST.json')
    paper = read(BASE / 'd0030-paper-verification.json')
    source_manifest = HERE / 'paper/generated/SOURCE-MANIFEST.json'
    assert digest(source_manifest) == paper['source_manifest_sha256']
    for file, sha in read(source_manifest)['files'].items():
        assert digest(ROOT / file) == sha
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == paper['pdf_sha256']
    tests = subprocess.run([sys.executable, str(HERE / 'test_d0045_d0046.py')], text=True, capture_output=True)
    assert tests.returncode == 0, tests.stderr
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    paths += [job / name for name in ('MANIFEST.json', 'STRUCTURAL-HYPOTHESIS.json',
        'C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json', 'DISPATCHED.json', 'STARTED.json',
        'COMPLETE.json', 'SCORE.json', 'TIE-RULE-SCORE.json', 'LEDGER-AUDIT.json')]
    paths.append(catalog_path)
    queries = {}
    for node in range(3):
        directory = BASE / f'd0047-node{node}-carry'
        report = read(directory / 'REPORT.json')
        assert report['source_sha256'] == digest(HERE / 'd0047_tie_carry_smt.py')
        assert report['query_sha256'] == digest(directory / 'query.smt2')
        assert report['concrete_template_replay'] == 'PASS'
        assert report['result'] == 'unknown' and report['reason_unknown'] == 'timeout'
        queries[str(node)] = dict(result=report['result'], timeout_ms=report['timeout_ms'],
                                 global_exclusion_proved=False)
        paths.extend((directory / 'REPORT.json', directory / 'query.smt2'))
    save(BASE / 'd0045-d0046-verification.json', dict(status='PASS_EVIDENCE_AUDIT',
        baseline_misses=counts['baseline_union_misses'], native_counts=score['counts'],
        tie_rule_counts=counts, software_search_counts=searches,
        remaining_node_queries=queries,
        identified_among_fixed_rules={'table:correction_sum': 'nearest-even'} if not counts['baseline_union_misses'] else {},
        unresolved_nodes=['direct:odd_inner_sum', 'direct:even_inner_sum', 'table:odd_sum'],
        corpus_rows=7119648, corpus_packs=19, new_skylake_rows=22064,
        previous_two_context_rows=7097584,
        checks=dict(stdout=tests.stdout, stderr=tests.stderr, returncode=tests.returncode),
        evidence_sha256={str(path.relative_to(ROOT)): digest(path) for path in paths},
        source_sha256={name: digest(HERE / name) for name in
            ('verify_d0045_d0046.py', 'test_d0045_d0046.py', 'score_d0046_ties.py', 'extend_corpus_d0046.py')},
        hardware_executed=False, numerical_model_changed=False, paper_changed=False, goal_complete=False,
        limits='Only exposed fixed tie rules are discriminated. The three masked additions remain unresolved. This is not a universal raw80, arbitrary state-dependent rule, or all-CPU proof.'))
    print('PASS evidence audit; baseline misses:', counts['baseline_union_misses'],
          '; three other node tie rules remain unresolved', flush=True)


if __name__ == '__main__':
    main()
