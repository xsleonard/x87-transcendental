#!/usr/bin/env python3
"""Separate small-denormal operand evidence from incidental signature matches.

Read-only local provenance audit. No eligibility decision, manifest freeze,
capture, private identifiers/contents/hashes, or numerical model change.
The historical significand-only rejection policy remains unchanged.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from h1640_remaining_scope_freshness import save


SIGNATURE = r'000000000000000[1-9a-f]'
# Include padded and short hexadecimal forms, 0x prefixes, tabs, colon
# notation, and a single-line JSON pair. These are positive lexical evidence,
# not a proof that arbitrary source code or a binary encodes no such operand.
PAIR = r'(?<![0-9a-f])(?:0x)?(?:0000|8000)[\s:,"\[\]]+(?:0x)?0{0,15}[1-9a-f](?![0-9a-f])'
PACKED = r'(?<![0-9a-f])(?:0000|8000)000000000000000[1-9a-f](?![0-9a-f])'
SEARCH = '(?:'+SIGNATURE+'|'+PAIR+'|'+PACKED+')'
PAIR_RE = re.compile(PAIR, re.I)
SIG_RE = re.compile(SIGNATURE, re.I)
PACKED_RE = re.compile(PACKED, re.I)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def scan(root, excluded, *, private=False):
    command = ['rg', '--json', '--pcre2', '--hidden', '--no-ignore',
               '--search-zip', '--text', '--ignore-case', '--glob', '!**/.git/**']
    for path in excluded:
        command += ['--glob', '!**/'+path.relative_to(root).as_posix()+'/**']
    command += [SEARCH, str(root)]
    counts, signatures, operand_files, all_files = Counter(), set(), set(), set()
    inventory = {}
    # Error output is never surfaced verbatim: rg may include private names.
    # Use a file so a large error stream cannot deadlock the JSON consumer.
    with tempfile.TemporaryFile() as errors:
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        assert child.stdout is not None
        for line in child.stdout:
            event = json.loads(line)
            if event['type'] != 'match':
                continue
            data = event['data']
            if 'text' not in data['path']:
                child.terminate()
                child.wait()
                raise RuntimeError('Non-text path; provenance incomplete')
            path = Path(data['path']['text'])
            assert not any(path.is_relative_to(p) for p in excluded)
            body = (data['lines']['text'] if 'text' in data['lines'] else
                    base64.b64decode(data['lines']['bytes']).decode('latin1'))
            all_files.add(path)
            sigs = {s.lower() for s in SIG_RE.findall(body)}
            signatures.update(sigs)
            paired = bool(PAIR_RE.search(body) or PACKED_RE.search(body))
            counts['matching_lines'] += 1
            counts['operand_lexical_lines'] += paired
            counts['signature_only_lines'] += not paired
            if paired:
                operand_files.add(path)
            if not private:
                name = path.relative_to(root).as_posix()
                row = inventory.setdefault(name, dict(signature_lines=0,
                    operand_lexical_lines=0, first_operand_line=None,
                    signature_values=set()))
                row['signature_lines'] += bool(sigs)
                row['signature_values'].update(sigs)
                row['operand_lexical_lines'] += paired
                if paired and row['first_operand_line'] is None:
                    row['first_operand_line'] = data['line_number']
        child.stdout.close()
        code = child.wait()
        errors.seek(0, 2)
        error_size = errors.tell()
    if code not in (0, 1) or error_size:
        raise RuntimeError(f'Incomplete provenance scan: exit={code}, diagnostic_bytes={error_size}')
    counts.update(matching_files=len(all_files), operand_lexical_files=len(operand_files),
                  visible_candidate_significands=len(signatures))
    if private:
        # No per-significand membership, paths, lines, content or private hashes.
        return dict(counts= dict(counts), files_examined=sum(p.is_file() for p in root.rglob('*')),
                    identities_contents_or_hashes_published=False)
    for name, row in inventory.items():
        row['signature_values'] = sorted(row['signature_values'])
        row['sha256'] = digest(root/name)
    return dict(counts=dict(counts), inventory=inventory)


def modern_campaigns(root):
    """Authenticate actual capture prestates, not proposed software operands."""
    campaigns = []
    for name in ('h1649', 'h1656', 'h1662'):
        base = root/'transfer-tests'/name
        opened = json.loads((base/'OPENED.json').read_text())
        manifest = json.loads((base/'manifest.json').read_text())
        freeze = json.loads((base/'FREEZE.json').read_text())
        assert digest(base/'manifest.json') == freeze['sha256']['manifest']
        raw = base/'hardware-output/state-output.txt'
        small = []
        raw_count = 0
        with raw.open() as source:
            for line in source:
                fields = dict(word.split('=', 1) for word in line.split())
                se, sig = (int(w, 16) for w in fields['B_R0'].split(':'))
                if se in (0, 0x8000) and 1 <= sig <= 15:
                    small.append(dict(case=fields['CASE'], instruction=fields['INSN'],
                                      before_control=fields['B_CW'], before_status=fields['B_SW']))
                raw_count += 1
        assert len(manifest) == raw_count
        # Preserve the marker contents separately only through their PUBLIC
        # hash. Require OPENED_ONCE, without depending on incidental key names.
        assert 'OPENED_ONCE' in json.dumps(opened)
        campaigns.append(dict(campaign=name, actual_rows=raw_count,
            small_denormal_before_rows=len(small), matches=small,
            sha256={key:digest(base/key) for key in ('OPENED.json', 'FREEZE.json',
                'manifest.json', 'hardware-output/state-output.txt')}))
    return campaigns


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--private-ledger-dir', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args()
    root, private, out = a.root.resolve(), a.private_ledger_dir.resolve(), a.output_dir.resolve()
    assert private.is_dir() and not out.exists() and out.is_relative_to(root)
    # Do not turn this very audit into its own evidence. Software appearances
    # elsewhere are retained and explicitly distinguished from observations.
    out.mkdir(parents=True)
    print('Scanning public lexical provenance, including compressed text.', flush=True)
    public = scan(root, [private, out])
    print('Scanning private history locally; only aggregate counts leave the scanner.', flush=True)
    hidden = scan(private, [], private=True)
    campaigns = modern_campaigns(root)
    save(out/'public_inventory.json', public)
    report = dict(experiment='h1665_small_denormal_provenance',
        status='PROVENANCE_INVENTORY_NOT_FRESHNESS_CLEARANCE',
        public_counts=public['counts'], private_aggregate=hidden, modern_campaigns=campaigns,
        hardware_execution='none', manifest_frozen=False, freshness_policy_changed=False,
        candidate_default_or_paper_changed=False,
        claim_boundary='Signature-only appearances are not hardware coverage. Lexical operand matches need source/manifest reconciliation. No absence theorem over arbitrary binary/decimal/dynamically generated operands, no fresh-tuple clearance and no universal silicon proof.',
        sha256=dict(script=digest(Path(__file__)), public_inventory=digest(out/'public_inventory.json')))
    save(out/'report.json', report)
    print(json.dumps({k:report[k] for k in ('status', 'public_counts', 'private_aggregate')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
