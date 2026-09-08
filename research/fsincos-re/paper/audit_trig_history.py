"""Export completed trig evidence from the explicitly named research records.

Checks saved reports and their arithmetic; never executes native instructions
or reruns numerical comparisons. The native FSIN logs retain their weaker,
aggregate-only provenance instead of being presented as a raw-label replay.
"""
from collections import Counter
import json
from pathlib import Path

from suite_support import HERE, PROJECT, digest, write_json


def read(path):
    return json.loads(path.read_text())


def checked_counts(report):
    assert report['status'] == 'PASS' and report['hardware_executions'] == 0
    counts = sum((Counter(r['counts']) for r in report['records']), Counter())
    assert counts == Counter(report['counts'])
    for record in report['records']:
        assert record['status'] == 'PASS' and record['returncode'] == 0
        assert not any(v for k, v in record['counts'].items() if 'miss' in k)
    return counts


def main():
    base = PROJECT / 'tmp/ledger33/current/h1719_two_host_replay'
    report_path = base / 'report.json'
    assert digest(report_path) == 'a6eb46893e2f8a83f5478f6347d4c126f1e3163427b9ebd296b7f89c871f8d84'
    report = read(report_path)
    assert report['status'] == 'PASS_SAVED_LABEL_REPLAYS_BOTH_HOSTS'
    for name, sha in report['evidence'].items():
        assert digest(base / name) == sha, name
    hosts, model_sources = {}, None
    for host, saved in report['hosts'].items():
        directory = base / (host + '-bulk')
        native = read(directory / 'results/report.json')
        common = read(directory / 'retained-results/report.json')
        native_counts, common_counts = checked_counts(native), checked_counts(common)
        assert common['jobs'] == 167
        assert common_counts == Counter(saved['common_retained'])
        assert native_counts == Counter(saved['native_inventory'])
        extra = Counter()
        if host == 'i7':
            for mode in ('rn', 'rd', 'ru'):
                counts = read(directory / 'h633' / (mode + '.json'))
                assert not any(v for k, v in counts.items() if 'miss' in k)
                extra.update(counts)
        assert native_counts + common_counts + extra == Counter(saved['total_counts'])
        sources = {name: sha for name, sha in native['source_sha256'].items()
                   if name.endswith(('.c', '.h')) and not name.startswith('experiments/')}
        for name, sha in sources.items():
            assert digest(PROJECT / name) == sha, name
        assert model_sources is None or model_sources == sources
        model_sources = sources
        cpu_fields = {}
        for line in saved['execution_cpu'].splitlines():
            key, sep, value = line.partition(':')
            if sep and key.strip() in ('vendor_id', 'cpu family', 'model', 'model name', 'stepping', 'microcode'):
                cpu_fields[key.strip()] = value.strip()
        hosts[host] = {key: saved[key] for key in ('total_counts', 'native_inventory',
                      'common_retained', 'h633_additional', 'unavailable_native_modes')}
        hosts[host]['execution_cpu'] = cpu_fields
        hosts[host]['capture_provenance'] = 'Shared retained observations plus available host-specific historical banks; execution CPU is not the origin of every label.'
    write_json(HERE / 'evidence/trig-h1719-summary.json', dict(
        status=report['status'], source_report=str(report_path.relative_to(PROJECT)),
        source_report_sha256=digest(report_path), source_files=model_sources,
        hardware_executed_by_this_audit=False,
        audit_scope='Authenticated all subordinate report hashes and recomputed per-job, per-component and host totals; no raw-label numerical replay in this editorial audit.',
        subordinate_reports_authenticated=len(report['evidence']),
        evidence_sha256=report['evidence'], hosts=hosts, limits=report['limits'],
        observation_unit='Overlapping instruction-row appearances in software replays',
        summary_builder_sha256=digest(Path(__file__))))

    review = PROJECT / 'transfer-tests/review-20260905'
    runs = []
    for name in ('fsin_exhaustive_h1716.log', 'fsin_exhaustive_h1716_bits30.log'):
        path = review / 'xeon_fsin_exhaustive' / name
        line = path.read_text().strip()
        assert line.startswith('SUMMARY ') and len(line.splitlines()) == 1
        fields = dict(item.split('=', 1) for item in line.split()[1:])
        counts = {key: int(fields[key]) for key in ('count', 'inputs', 'observations',
                  'output_misses', 'C1_misses', 'C2_misses', 'C2_output_misses', 'model_interval_failures')}
        assert counts['count'] == counts['inputs']
        assert counts['observations'] == 3 * counts['inputs']
        assert not any(v for k, v in counts.items() if k.endswith(('misses', 'failures')))
        assert fields['mode_mask'] == '7' and int(fields['seed'], 16) == 0x1716
        classes = {k: int(v) for k, v in (x.split(':') for x in fields['classes'].split(','))}
        assert sum(classes.values()) == counts['inputs']
        runs.append(dict(log=str(path.relative_to(PROJECT)), log_sha256=digest(path),
                         summary=line, start=int(fields['start'], 16), counts=counts, classes=classes))
    assert runs[0]['start'] == 0 and runs[1]['start'] == runs[0]['counts']['count']
    checksums = review / 'bank/CHECKSUMS.sha256'
    main_sha = next(line.split()[0] for line in checksums.read_text().splitlines()
                    if line.endswith('  src/fsincos_skylake.c'))
    assert main_sha == digest(PROJECT / 'src/fsincos_skylake.c')
    write_json(HERE / 'evidence/trig-native-fsin-summary.json', dict(
        status='COMPLETED_NATIVE_RUN_LOGS_ZERO_REPORTED_MISSES', runs=runs,
        inputs=sum(r['counts']['inputs'] for r in runs),
        instruction_executions=sum(r['counts']['observations'] for r in runs),
        seed='0x1716', rounding_modes=['rn', 'rd', 'ru'], precision_control=64,
        observation_unit='Native FSIN instruction executions, including range returns and special values',
        hardware_executed_by_this_audit=False,
        audit_scope='Parsed both original completion summaries and checked contiguous counter ranges, class totals, three-mode counts and zero mismatch counters.',
        checked_fields='Result and directed-bound C1 on non-C2 returns; C2 and unchanged operand on range returns; model interval consistency.',
        review_note='notes/REVIEW-20260905-independent-verification.md',
        review_note_sha256=digest(PROJECT / 'notes/REVIEW-20260905-independent-verification.md'),
        review_main_source_sha256=main_sha, review_checksums_sha256=digest(checksums),
        current_comparator_sha256=digest(PROJECT / 'src/fsin_exhaustive.c'),
        source_relation='The review predates H1717; H1717 changed only the paired header, leaving standalone FSIN unchanged. The review identifies the tested build, but these aggregate logs do not independently pin the comparator binary or all its dependencies.',
        limits=['The retained record contains aggregate completion logs, not per-input hardware labels.',
                'A selected binary64-derived traversal is not exhaustive binary64 or raw80 coverage.',
                'Zero/ infinity classes have no sampled inputs; binary64 subnormals convert to normalized raw80.',
                'C1 was not checked on C2 returns. No total of in-range C1 checks is recorded.',
                'No disjointness from other campaigns is claimed.'],
        summary_builder_sha256=digest(Path(__file__))))
    print('PASS: H1719 subordinate reports and source pins; two native FSIN completion logs')


if __name__ == '__main__':
    main()
