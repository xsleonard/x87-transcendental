"""Authenticate i7/Skylake comparison, including separately reported raw SW."""
from collections import Counter
import argparse
import gzip
import json
from pathlib import Path

from compressed_guard import digest
from prepare import save
from protocol import validate_output

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
ROOT = HERE.parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', choices=('d0043', 'd0044'), default='d0043')
    args = parser.parse_args()
    job = BASE / args.job
    reference = json.loads((job / 'SKYLAKE-REFERENCE.json').read_text())
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    start = json.loads((job / 'STARTED.json').read_text())
    score = json.loads((job / 'SCORE.json').read_text())
    ledger = json.loads((job / 'LEDGER-AUDIT.json').read_text())
    expected_rows = reference['counts']['rows']
    assert complete['state'] == 'OBSERVED' and complete['rows'] == expected_rows
    assert complete['manifest_sha256'] == digest(job / 'MANIFEST.json')
    assert digest(job / 'SKYLAKE-REFERENCE.json') == manifest['reference_receipt_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert start['identity'].split()[1] == '000506e3' and start['microcode'] == ['0xf0']
    assert ledger['integrity'] == 'ok'
    assert any(row[1:] == [args.job, 'OBSERVED', expected_rows] for row in ledger['compressed_batches'])
    for name, sha in manifest['files'].items():
        assert digest(job / name) == sha
    for name, sha in manifest['source_pins'].items():
        assert digest(job / 'sources' / name) == sha == digest(HERE / name)
    for name in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        preflight = json.loads((job / name).read_text())
        assert preflight['rows'] == expected_rows and preflight['C_frozen_Python_differences'] == 0
        assert preflight['binary_sha256'] == json.loads((BASE / 'd0040' / name).read_text())['binary_sha256']
    counts = Counter()
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, gzip.open(job / 'hardware.txt.gz', 'rt') as i7:
        for name, source in reference['source_packs'].items():
            old = BASE / name
            old_complete = json.loads((old / 'COMPLETE.json').read_text())
            assert digest(old / 'COMPLETE.json') == source['completion_sha256']
            compressed = old_complete.get('format') == 'fpatan-gzip-v2'
            path = old / ('hardware.txt.gz' if compressed else 'hardware.txt')
            assert digest(path) == old_complete['hardware_gzip_sha256' if compressed else 'hardware_sha256']
            rows = 0
            with (gzip.open(path, 'rt') if compressed else path.open()) as skylake:
                for sky_line in skylake:
                    expected = next(inputs)
                    i7_line = next(i7)
                    a, b = validate_output(sky_line, expected), validate_output(i7_line, expected)
                    rows += 1
                    counts['rows'] += 1
                    counts['result_differences'] += (a['se'], a['sig']) != (b['se'], b['sig'])
                    counts['C1_differences'] += a['C1'] != b['C1']
                    counts['arithmetic_exception_differences'] += (a['sw'] & 63) != (b['sw'] & 63)
                    counts['preload_exception_differences'] += (a['before'] & 63) != (b['before'] & 63)
                    counts['raw_after_status_differences'] += a['sw'] != b['sw']
                    counts['raw_before_status_differences'] += a['before'] != b['before']
                    counts['undefined_C0_C2_C3_differences'] += bool((a['sw'] ^ b['sw']) & 0x4500)
                    counts['other_after_status_differences'] += bool((a['sw'] ^ b['sw']) & ~0x4500)
            assert rows == source['rows']
            print('Compared i7/Skylake pack', name, rows, flush=True)
        assert next(inputs, None) is None and next(i7, None) is None
    assert counts['rows'] == complete['rows']
    for a, b in (('result_differences', 'candidate_misses'), ('C1_differences', 'candidate_C1_misses'),
                 ('arithmetic_exception_differences', 'exception_misses'), ('preload_exception_differences', 'before_exception_misses')):
        assert counts[a] == score['counts'][b]
    paper = json.loads((BASE / 'd0030-paper-verification.json').read_text())
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == paper['pdf_sha256']
    assert digest(HERE / 'fpatan_candidate.c') == paper['numerical_source_sha256']
    evidence = ('MANIFEST.json', 'SKYLAKE-REFERENCE.json', 'C-PREFLIGHT.json',
        'C-SANITIZED-PREFLIGHT.json', 'HISTORY.json', 'STAGED.json', 'DISPATCHED.json',
        'STARTED.json', 'COMPLETE.json', 'SCORE.json', 'LEDGER-AUDIT.json')
    save(job / 'CROSS-CPU-VERIFICATION.json', dict(status='AUTHENTICATED_CROSS_CPU_COMPARISON',
        counts=counts, i7_identity=start['identity'], i7_microcode=start['microcode'],
        host='142.132.217.243', configured_host_source='experiments/h1725_full_campaign.py',
        mistaken_earlier_address='142.132.217.24',
        evidence_sha256={name: digest(job / name) for name in evidence},
        verifier_sha256=digest(Path(__file__)), numerical_model_changed=False, paper_changed=False,
        hardware_executed=False, distinct_input_tuples=counts['rows'],
        limits='Comparison of two recorded CPU/configuration contexts on this corpus, not all raw80 inputs or all x87 generations. CPU observations are not additional distinct corpus inputs.'))
    print(json.dumps(counts, indent=2), flush=True)


if __name__ == '__main__':
    main()
