#!/usr/bin/env python3
"""Private exact-center representation checks, with aggregate-only output.

Never serialize private names, text, hashes or per-operand membership. A
positive possible tuple/value prevents a clean result. No hardware, freshness
policy mutation, manifest freeze, PDF authoring or emulator change.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from collections import Counter
from fractions import Fraction
from pathlib import Path
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest
from h1690_exact_center_public_inventory import BANK, patterns

LOCKS = {
    BANK: 'c9b28e70b337b3fe3ce2fa75debc8b1c97f5d18168ebc1e1c4eb528bc8d617f1',
    'experiments/h1690_exact_center_public_inventory.py': '4a47b748768ffaa9f8b194f659cb309644f0a1d562b8416301cc70fe2e9edc16',
}
DECIMAL = re.compile(r'(?<![0-9a-z_.])[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[-+]?[0-9]+)?(?![0-9a-z_.])', re.I)


def representations(operands):
    numeric = set()
    binary = set()
    decimal_fields = []
    for op in operands:
        se, sig = (int(w, 16) for w in op.split())
        e = (se & 0x7fff) - 16383 - 63
        magnitude = Fraction(sig * (1 << e)) if e >= 0 else Fraction(sig, 1 << -e)
        numeric.add(-magnitude if se & 0x8000 else magnitude)
        # Standard80-bit memory; common se-first structs with/without padding;
        # all consistent big/little-endian field encodings, not a binary parser.
        for endian in ('little', 'big'):
            sf, mw = se.to_bytes(2, endian), sig.to_bytes(8, endian)
            binary.update((mw + sf, sf + mw, sf + b'\0' * 6 + mw))
        decimal_fields.append(str(se) + r'[\s:,"\[\]]+' + str(sig))
    paired_decimal = re.compile(r'(?<![0-9])(?:' + '|'.join(decimal_fields) + r')(?![0-9])')
    return numeric, binary, paired_decimal


def inspect(private, operands):
    pair = re.compile(patterns(operands), re.I)
    values, binary, decimal_fields = representations(operands)
    counts = Counter()
    for path in sorted(private.rglob('*')):
        if not path.is_file():
            continue
        counts['files_examined'] += 1
        raw = path.read_bytes()
        counts['bytes_examined'] += len(raw)
        counts['possible_binary_struct_occurrences'] += sum(raw.count(p) for p in binary)
        views = []
        if raw.startswith(b'%PDF'):
            proc = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode or proc.stderr:
                raise RuntimeError('Private PDF extraction diagnostic; audit incomplete')
            views.append(proc.stdout.decode('utf-8'))
            counts['PDF_files_extracted'] += 1
            counts['nonempty_PDF_page_texts'] += sum(bool(p.strip()) for p in proc.stdout.split(b'\f'))
        else:
            try:
                views.append(raw.decode('utf-8'))
                counts['UTF8_files'] += 1
            except UnicodeDecodeError:
                views.append(raw.decode('latin1'))
                counts['ASCII_preserving_8bit_or_binary_files'] += 1
            # Search UTF16 renderings in addition to the ASCII-preserving
            # view; a successful decode is NOT a claimed format identification.
            for encoding in ('utf-16-le', 'utf-16-be'):
                try:
                    views.append(raw.decode(encoding))
                    counts['additional_UTF16_views'] += 1
                except UnicodeError:
                    counts['nondecodable_UTF16_views'] += 1
            if raw.startswith(b'\0\0\0\1Bud1'):
                counts['desktop_metadata_magic_files'] += 1
            elif b'\0' in raw:
                counts['other_NUL_containing_non_PDF_files'] += 1
        for text in views:
            counts['decoded_characters_examined'] += len(text)
            counts['possible_paired_hex80_occurrences'] += len(pair.findall(text))
            counts['possible_paired_decimal_field_occurrences'] += len(decimal_fields.findall(text))
            for match in DECIMAL.finditer(text):
                token = match.group()
                # Refuse absurd exponents instead of allocating huge integers;
                # none of these targets has |decimal exponent| above20.
                exponent = re.search(r'e([-+]?[0-9]+)$', token, re.I)
                if exponent and (len(exponent.group(1)) > 4 or abs(int(exponent.group(1))) > 100):
                    counts['out_of_target_range_decimal_exponents'] += 1
                    continue
                if len(token) > 256:
                    counts['long_numeric_tokens_unparsed'] += 1
                    continue
                try:
                    value = Fraction(token)
                except ValueError:
                    counts['numeric_parse_failures'] += 1
                    continue
                counts['exact_numeric_tokens_examined'] += 1
                counts['possible_exact_numeric_value_occurrences'] += value in values
    positive = sum(counts[name] for name in (
        'possible_binary_struct_occurrences', 'possible_paired_hex80_occurrences',
        'possible_paired_decimal_field_occurrences', 'possible_exact_numeric_value_occurrences'))
    return counts, positive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--private-ledger-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, private, out = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    for name, expected in LOCKS.items():
        assert digest(root / name) == expected, name
    bank = json.loads((root / BANK).read_text())
    targets = {r['operand'] for r in bank['operands'] if any('center' in k for k in r['kinds'])}
    assert len(targets) == 28
    # Synthetic public positive controls cover each representation family.
    values, binary, decimal_fields = representations(targets)
    pair = re.compile(patterns(targets), re.I)
    for op in targets:
        se, sig = op.split()
        assert pair.search(se + ':' + sig)
        assert decimal_fields.search(str(int(se, 16)) + ' ' + str(int(sig, 16)))
        assert int(sig, 16).to_bytes(8, 'little') + int(se, 16).to_bytes(2, 'little') in binary
    assert len(values) == 28
    counts, positive = inspect(private, targets)
    out.mkdir(parents=True)
    report = dict(experiment='h1691_private_center_representation_audit',
        status='POSSIBLE_PRIVATE_COLLISION_UNRESOLVED' if positive else 'NO_MATCH_IN_CHECKED_PRIVATE_REPRESENTATIONS',
        counts=dict(counts), possible_collision_occurrences=positive,
        private_identities_contents_hashes_membership_lists_published=False,
        scope='Paired hex80 text (including extracted PDFs and UTF16 views), paired decimal se/sig fields, exact rational numeric literals, and specified80-bit/common-struct byte layouts. This is not arbitrary compressed/encrypted/binary-schema/dynamic-generator/image-content completeness.',
        policy='Any positive possible tuple/value must be resolved before a clean audit; no per-operand private membership is serialized.',
        freshness_clearance=False, hardware_execution='none', manifest_frozen=False,
        paper_default_or_candidate_change=False,
        sha256=dict(script=digest(Path(__file__)), PUBLIC_evidence_only=LOCKS))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'counts', 'possible_collision_occurrences')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
