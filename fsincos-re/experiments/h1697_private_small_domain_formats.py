#!/usr/bin/env python3
"""Aggregate-only private format audit for the unreserved small complement.

This does not clear a capture. Denormal values use exponent 1-bias, not the
normal E-bias formula. Scientific literals are tested for exact equality and
possible directed rounding to a target. Unknown schemas/images remain open.
No private path, text, hash or per-operand membership is returned or written.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from collections import Counter
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest
from h1691_private_center_representation_audit import DECIMAL

SIGNIFICANDS = frozenset((5, 6, 9, 10, 11, 12, 13, 14))
UNIT_DENOMINATOR = 1 << 16445
LOCKS = {
    'experiments/h1691_private_center_representation_audit.py': '7e39e927b0504298cd9088b80b18fe198455818206e02cf6d28aa8250ef8b480',
    'tmp/ledger33/current/h1688_generated_small_operand_provenance/historically_reported_reservations.json': '79d3012fc501ec64329a7cd9974b6428d0102b911d594cb8a84fb4e49b92d3a1',
}
HEX_FLOAT = re.compile(r'(?<![0-9a-z_.])[-+]?0x(?:[0-9a-f]+(?:\.[0-9a-f]*)?|\.[0-9a-f]+)p[-+]?[0-9]+(?![0-9a-z_.])', re.I)


def possible_value(value):
    """All four final RC results lie among floor/ceil on this denormal grid."""
    q = abs(value) * UNIT_DENOMINATOR
    floor = q.numerator // q.denominator
    ceiling = floor + (q.denominator != 1)
    return q.denominator == 1 and floor in SIGNIFICANDS, bool({floor, ceiling} & SIGNIFICANDS)


def patterns():
    # Allow short or padded hex and prefixed fields, packed80 and JSON pairs.
    sep = r'[\s:,/"\[\]]+'
    sig = r'0*(?:5|6|9|a|b|c|d|e)'
    pair = re.compile(r'(?<![0-9a-z_])(?:0x)?(?:0{1,4}|8000)' + sep +
                      r'(?:0x)?' + sig + r'(?![0-9a-z_])', re.I)
    packed = re.compile(r'(?<![0-9a-z_])(?:0000|8000)000000000000000[569abcde](?![0-9a-z_])', re.I)
    decimal_fields = re.compile(r'(?<![0-9a-z_])(?:0|32768)' + sep +
                               r'(?:5|6|9|10|11|12|13|14)(?![0-9a-z_])', re.I)
    binary = set()
    for se in (0, 0x8000):
        for s in SIGNIFICANDS:
            for endian in ('little', 'big'):
                a, b = se.to_bytes(2, endian), s.to_bytes(8, endian)
                binary.update((b + a, a + b, a + b'\0' * 6 + b))
    return pair, packed, decimal_fields, binary


def numeric_counts(text):
    counts = Counter()
    for match in DECIMAL.finditer(text):
        token = match.group()
        if len(token) > 20000:
            counts['numeric_tokens_unparsed_length'] += 1; continue
        try:
            value = Decimal(token)
        except InvalidOperation:
            counts['numeric_tokens_unparsed_decimal'] += 1; continue
        counts['decimal_tokens_examined'] += 1
        # |target| is about 1e-4950. Even either adjacent denormal cannot be
        # selected by a decimal outside this deliberately wider decade window.
        if not value or not -4952 <= value.adjusted() <= -4949:
            counts['decimal_values_outside_small_rounding_window'] += 1; continue
        exact, possible = possible_value(Fraction(value))
        counts['decimal_values_in_small_rounding_window'] += 1
        counts['possible_exact_decimal_value_occurrences'] += exact
        counts['possible_decimal_rounded_value_occurrences'] += possible
    for match in HEX_FLOAT.finditer(text):
        token = match.group()
        if len(token) > 20000:
            counts['numeric_tokens_unparsed_length'] += 1; continue
        mantissa, exponent = token.lower().lstrip('+-')[2:].split('p')
        if len(exponent.lstrip('+-')) > 6:
            counts['hex_values_outside_small_rounding_window'] += 1; continue
        after = len(mantissa.split('.')[1]) if '.' in mantissa else 0
        integer = int(mantissa.replace('.', ''), 16)
        power = int(exponent) - 4 * after
        counts['hex_float_tokens_examined'] += 1
        if not integer or not -16447 <= integer.bit_length() - 1 + power <= -16440:
            counts['hex_values_outside_small_rounding_window'] += 1; continue
        value = Fraction(integer << power) if power >= 0 else Fraction(integer, 1 << -power)
        exact, possible = possible_value(value)
        counts['possible_exact_hex_value_occurrences'] += exact
        counts['possible_hex_rounded_value_occurrences'] += possible
    return counts


def synthetic_controls():
    pair, packed, decimal_fields, binary = patterns()
    checks = Counter()
    for se in (0, 0x8000):
        for sig in SIGNIFICANDS:
            for text in (f'{se:04x}:{sig:016x}', f'0x{se:x} 0x{sig:x}', f'["{se:04x}","{sig:016x}"]'):
                assert pair.search(text); checks['hex_pair_positive'] += 1
            assert packed.search(f'{se:04x}{sig:016x}'); checks['packed_positive'] += 1
            assert decimal_fields.search(f'{se} {sig}'); checks['decimal_fields_positive'] += 1
            assert sig.to_bytes(8, 'little') + se.to_bytes(2, 'little') in binary
            checks['binary_positive'] += 1
            value = Fraction(sig, UNIT_DENOMINATOR)
            assert possible_value(value) == (True, True)
            assert possible_value(-value) == (True, True)
            assert numeric_counts(f'0x{sig:x}p-16445')['possible_exact_hex_value_occurrences'] == 1
            checks['denormal_value_positive'] += 1
    # These scientific literals could round to5/6 ulps; the old center-only
    # exponent cutoff would skip them. Neither is an exact target value.
    c = numeric_counts('2e-4950 -2e-4950')
    assert c['possible_decimal_rounded_value_occurrences'] == 2 and not c['possible_exact_decimal_value_occurrences']
    checks['extreme_decimal_rounded_positive'] += 2
    for text in ('0', '1', '5e-100', '1e-9000', '0x1p-16000', '0x1p-17000'):
        assert not any(v for k, v in numeric_counts(text).items() if k.startswith('possible_'))
        checks['numeric_negative'] += 1
    return dict(checks)


def inspect(private):
    pair, packed, decimal_fields, binary = patterns()
    counts = Counter()
    for path in sorted(private.rglob('*')):
        if not path.is_file(): continue
        raw = path.read_bytes(); counts['files_examined'] += 1; counts['bytes_examined'] += len(raw)
        counts['possible_binary_struct_occurrences'] += sum(raw.count(x) for x in binary)
        views = []
        if raw.startswith(b'%PDF'):
            proc = subprocess.run(['pdftotext', '-layout', str(path), '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode or proc.stderr:
                raise RuntimeError('Private PDF extraction incomplete; diagnostics withheld')
            views.append(proc.stdout.decode('utf-8'))
            counts['PDF_files_extracted'] += 1
            counts['nonempty_PDF_page_texts'] += sum(bool(p.strip()) for p in proc.stdout.split(b'\f'))
        else:
            try:
                views.append(raw.decode('utf-8')); counts['UTF8_files'] += 1
            except UnicodeError:
                views.append(raw.decode('latin1')); counts['ASCII_preserving_8bit_or_binary_files'] += 1
            for encoding in ('utf-16-le', 'utf-16-be'):
                try:
                    views.append(raw.decode(encoding)); counts['additional_UTF16_views'] += 1
                except UnicodeError:
                    counts['nondecodable_UTF16_views'] += 1
            if raw.startswith(b'\0\0\0\1Bud1'): counts['desktop_metadata_magic_files'] += 1
            elif b'\0' in raw: counts['other_NUL_containing_non_PDF_files'] += 1
        for text in views:
            counts['decoded_characters_examined'] += len(text)
            counts['possible_paired_hex80_occurrences'] += len(pair.findall(text))
            counts['possible_packed_hex80_occurrences'] += len(packed.findall(text))
            counts['possible_paired_decimal_field_occurrences'] += len(decimal_fields.findall(text))
            counts.update(numeric_counts(text))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--private-ledger-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); root, private, out = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    for name, expected in LOCKS.items(): assert digest(root / name) == expected, name
    controls = synthetic_controls(); counts = inspect(private)
    positive = sum(v for k, v in counts.items() if k.startswith('possible_'))
    unparsed = sum(v for k, v in counts.items() if k.startswith('numeric_tokens_unparsed'))
    out.mkdir(parents=True)
    report = dict(experiment='h1697_private_small_domain_formats',
        status='POSSIBLE_PRIVATE_COLLISION_UNRESOLVED' if positive or unparsed else 'NO_MATCH_IN_CHECKED_SMALL_DOMAIN_FORMATS',
        public_target_definition='Both signs, E=0, significands5,6,9,10,11,12,13,14; complement of H1688 reservations within1..15 only, not eligibility',
        target_encodings=16, counts=dict(counts), synthetic_controls=controls,
        possible_occurrences_nonunique=positive, unparsed_numeric_tokens=unparsed,
        unit='2^-16445; original exponent0 uses effective exponent1',
        scope='Paired/packed hex, decimal fields, exact or directed-rounded decimal/hex literals, extracted PDF text, UTF16 views and common raw80/struct bytes. Possible hits are not authenticated captures. Unknown schemas, compressed/encrypted/image-only data and dynamic generation remain outside this format audit.',
        private_identities_contents_hashes_membership_lists_published=False,
        hardware_execution='none', manifest_frozen=False, freshness_clearance=False,
        candidate_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), PUBLIC_evidence_only=LOCKS))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'counts', 'possible_occurrences_nonunique', 'unparsed_numeric_tokens')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
