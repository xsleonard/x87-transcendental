"""Authenticate the F2XM1 correction and replay existing raw80 captures.

This needs the retained research archive and a current portable model binary.
It never runs a native x87 capture or changes historical evidence.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from suite_support import (HERE, PROJECT, digest, sibling_constants, write_json,
                           before_f2xm1_correction_digest, reference_ast_digest)

sys.path.insert(0, str(PROJECT / "docs"))
import sibling_reference


def verify(binary):
    archive = PROJECT / "tmp/verification-expansion/f2xm1"
    final = json.loads((archive / "FINAL-VERIFICATION.json").read_text())
    assert final['status'] == 'COMPLETE_TWO_CPU_VERIFICATION_AND_REVIEWABLE_CORRECTION'
    for name, sha in final['evidence_sha256'].items():
        assert digest(archive / name) == sha, name
    pins = json.loads((archive / 'SOURCE-PINS.json').read_text())
    historical_reference = archive / 'baseline/docs/sibling_reference.py'
    assert digest(historical_reference) == pins['docs/sibling_reference.py']
    assert before_f2xm1_correction_digest(PROJECT / 'src/fsincos_skylake.c') == pins['src/fsincos_skylake.c']
    old_ast = reference_ast_digest(historical_reference)
    assert reference_ast_digest(PROJECT / 'docs/sibling_reference.py', True) == old_ast
    for name, sha in pins.items():
        if name not in ('src/fsincos_skylake.c', 'docs/sibling_reference.py'):
            assert digest(PROJECT / name) == sha, name
    constants = sibling_constants()

    @lru_cache(maxsize=None)
    def expected(se, sig, rc):
        return sibling_reference.evaluate('F2XM1', se, sig, rc, constants)

    jobs = {}
    for name in ('f0001', 'f0002'):
        folder = archive / name
        complete = json.loads((folder / 'COMPLETE.json').read_text())
        manifest = json.loads((folder / 'MANIFEST.json').read_text())
        assert complete['state'] == 'OBSERVED' and complete['ledger_integrity'] == 'ok'
        assert digest(folder / 'MANIFEST.json') == complete['manifest_sha256']
        assert digest(folder / 'inputs.txt.gz') == manifest['files']['inputs.txt.gz']
        assert digest(folder / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
        groups = defaultdict(list)
        counts = Counter()
        raw_hash = hashlib.sha256()
        with gzip.open(folder / 'inputs.txt.gz', 'rt') as requests, gzip.open(folder / 'hardware.txt.gz', 'rt') as observed:
            for request, observation in zip(requests, observed, strict=True):
                f, h = request.split(), observation.split()
                assert len(f) == 5 and len(h) == 11 and h[:5] == f
                rc, pc = f[1], int(f[2])
                se, sig = int(f[3], 16), int(f[4], 16)
                cw, before, after, end, hs, hm = (int(v, 16) for v in h[5:])
                assert cw == (0x7f | {24: 0, 53: 0x200, 64: 0x300}[pc]
                              | ("rn", "rd", "ru", "rz").index(rc) << 10)
                assert ((before >> 11) & 7, (after >> 11) & 7, (end >> 11) & 7) == (7, 7, 0)
                raw, pushed, c1, c2 = expected(se, sig, rc)
                assert raw == (hs, hm) and pushed is None
                assert c1 == ((after >> 9) & 1) and c2 == ((after >> 10) & 1)
                groups[rc].append((f'{se:04x} {sig:016x}', f'OK {hs:04x} {hm:016x}'))
                counts.update(rows=1, reference_result_misses=0, reference_C1_misses=0)
                counts[f'RC:{rc}'] += 1
                counts[f'PC:{pc}'] += 1
                raw_hash.update(observation.encode())
        assert counts['rows'] == complete['rows'] == manifest['rows'] == 54128
        assert raw_hash.hexdigest() == complete['hardware_sha256']
        for rc, rows in groups.items():
            run = subprocess.run([str(binary), '--batch', '--f2xm1', f'--rc={rc}'],
                                 input='\n'.join(r[0] for r in rows) + '\n',
                                 capture_output=True, text=True, check=True)
            assert run.stdout.splitlines() == [r[1] for r in rows], (name, rc)
        counts['C_output_misses'] = 0
        jobs[name] = dict(counts=dict(counts), signature=manifest['signature'],
                          microcode=manifest['microcode'], hardware_sha256=raw_hash.hexdigest(),
                          manifest_sha256=digest(folder / 'MANIFEST.json'),
                          complete_sha256=digest(folder / 'COMPLETE.json'))
        print(name, counts['rows'], 'current C/reference checks pass', flush=True)
    assert jobs['f0001']['hardware_sha256'] == jobs['f0002']['hardware_sha256']
    return dict(status='PASS_INTEGRATED_F2XM1_CORRECTION', hardware_executed=False,
                current_c_sha256=digest(PROJECT / 'src/fsincos_skylake.c'),
                current_reference_sha256=digest(PROJECT / 'docs/sibling_reference.py'),
                previous_c_sha256=pins['src/fsincos_skylake.c'],
                previous_reference_sha256=pins['docs/sibling_reference.py'],
                previous_reference_ast_sha256=old_ast,
                verifier_sha256=digest(Path(__file__)), binary_sha256=digest(binary),
                cases_per_processor=54128, processor_observations=108256,
                original_result_misses_per_processor=8658, original_C1_misses_per_processor=3177,
                frozen_C_correction_before_capture=final['C_correction_frozen_before_capture'],
                saved_result_regression_rows=915162,
                regression_receipt_sha256=digest(archive / 'DIRECT-SAVED-REPLAY.txt'),
                jobs=jobs, original_campaign_receipt_sha256=digest(archive / 'FINAL-VERIFICATION.json'),
                limits='Finite raw80 challenge. Current C outputs and rational result/C1 are replayed; exception hypotheses are separate. Historical holds and arbitrary state are not passes.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Choose a new receipt path; prior evidence is preserved.')
    write_json(args.out, verify(args.binary.resolve()))


if __name__ == '__main__':
    main()
