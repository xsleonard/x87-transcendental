#!/usr/bin/env python3
"""Locate exact-center operand spellings in public history, including archives.

This is a provenance worklist, not a freshness decision. An input-looking
line, source constant, proposed tuple or output word is not automatically a
hardware observation. Private history is excluded and never named in output.
"""
from __future__ import annotations
import argparse
import base64
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

BANK = 'tmp/ledger33/current/h1639_remaining_scope_proposals/bank.json'
LOCKS = {
    BANK: 'c9b28e70b337b3fe3ce2fa75debc8b1c97f5d18168ebc1e1c4eb528bc8d617f1',
    'tmp/ledger33/current/h1689_exact_center_contract/report.json': 'd67d1522c46576b3fd381040d1b84bd627eb48526baf4487f18117aca607a039',
}


def patterns(operands):
    # Preserve paired exponent/significand, not merely a ubiquitous significand.
    # Accommodate the repository's colon, slash, tuple and packed spellings.
    separator = r'[\s:,/"\[\]]*'
    return r'(?<![0-9a-z_])(?:' + '|'.join(
        '(?:0x)?' + op.split()[0] + separator + '(?:0x)?' + op.split()[1]
        for op in sorted(operands)) + r')(?![0-9a-z_])'


def normalized(match):
    word = re.sub(r'[^0-9a-f]', '', match.lower().replace('0x', ''))
    assert len(word) == 20
    return word[:4] + ' ' + word[4:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--private-ledger-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, private, out = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and private.is_relative_to(root)
    assert not out.exists() and out.is_relative_to(root)
    for name, expected in LOCKS.items():
        assert digest(root / name) == expected, name
    bank = json.loads((root / BANK).read_text())
    targets = {r['operand'] for r in bank['operands'] if any('center' in k for k in r['kinds'])}
    assert len(targets) == 28
    pattern = patterns(targets)
    for op in targets:
        se, sig = op.split()
        for text in (op, se + ':' + sig, se + '/' + sig, se + sig, '["' + se + '","' + sig + '"]'):
            found = re.search(pattern, text, re.I)
            assert found and normalized(found.group()) == op
        assert not re.search(pattern, 'a' + se + ':' + sig, re.I)
    out.mkdir(parents=True)
    command = ['rg', '--json', '--pcre2', '--hidden', '--no-ignore', '--search-zip',
               '--text', '--ignore-case', '--glob', '!**/.git/**',
               '--glob', '!**/' + private.relative_to(root).as_posix() + '/**',
               '--glob', '!**/' + out.relative_to(root).as_posix() + '/**',
               pattern, str(root)]
    inventory, counts = {}, Counter()
    with tempfile.TemporaryFile() as diagnostics:
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=diagnostics)
        assert child.stdout is not None
        for line in child.stdout:
            event = json.loads(line)
            if event['type'] != 'match':
                continue
            data = event['data']
            if 'text' not in data['path']:
                child.terminate(); child.wait()
                raise RuntimeError('Non-text public path; inventory incomplete')
            path = Path(data['path']['text']).resolve()
            assert path.is_relative_to(root) and not path.is_relative_to(private) and not path.is_relative_to(out)
            name = path.relative_to(root).as_posix()
            row = inventory.setdefault(name, dict(matching_lines=0, first_line=data['line_number'],
                operands=set(), role_hints=Counter()))
            body = (data['lines']['text'] if 'text' in data['lines'] else
                    base64.b64decode(data['lines']['bytes']).decode('latin1'))
            row['matching_lines'] += 1
            for sub in data['submatches']:
                match = sub['match'].get('text')
                if match is None:
                    match = base64.b64decode(sub['match']['bytes']).decode('ascii')
                op = normalized(match)
                assert op in targets
                row['operands'].add(op)
                counts['literal_occurrences'] += 1
            stripped = body.strip()
            if re.fullmatch(r'[0-9a-fA-F]{4}\s+[0-9a-fA-F]{16}', stripped):
                role = 'raw_two_column_input_shape'
            elif re.search(r'\bB_R0\s*=', body, re.I):
                role = 'before_register_record_shape'
            elif re.match(r'OK\s', stripped, re.I):
                role = 'output_line_shape_not_input'
            elif re.search(r'"operand"\s*:', body):
                role = 'json_operand_field_shape_not_execution_proof'
            else:
                role = 'other_text_or_binary_shape'
            row['role_hints'][role] += 1
            counts['matching_lines'] += 1
        child.stdout.close()
        code = child.wait()
        diagnostics.seek(0, 2)
        diagnostic_bytes = diagnostics.tell()
    if code not in (0, 1) or diagnostic_bytes:
        raise RuntimeError(f'Public inventory incomplete: exit={code}, diagnostic_bytes={diagnostic_bytes}')
    for name, row in inventory.items():
        row['operands'] = sorted(row['operands'])
        row['role_hints'] = dict(row['role_hints'])
        row['sha256'] = digest(root / name)
    counts['matching_files'] = len(inventory)
    prefixes = Counter('/'.join(name.split('/')[:2]) for name in inventory)
    save(out / 'public_inventory.json', inventory)
    report = dict(experiment='h1690_exact_center_public_inventory',
        status='PUBLIC_PAIRED_OPERAND_WORKLIST_NOT_FRESHNESS_CLEARANCE',
        counts=dict(counts), path_prefix_counts=dict(prefixes), operands=sorted(targets),
        scope='Current public repository text/compressed-text and binary textual spellings, paired80-bit fields; no cross-line JSON-field binding, decimal/dynamic generator absence theorem, private or unavailable remote archive claim.',
        next='Resolve each positive file to input/source/proposal/output and instruction-specific capture mapping; a role hint is not a verified classification.',
        hardware_execution='none', private_ledger_access='none', freshness_clearance=False,
        candidate_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS,
                    public_inventory=digest(out / 'public_inventory.json')))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'counts', 'path_prefix_counts')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
