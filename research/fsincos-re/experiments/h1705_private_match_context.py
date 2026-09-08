#!/usr/bin/env python3
"""Aggregate-only structural localization of H1697's possible matches.

No private names, contents, hashes, identifiers or per-operand membership are
returned or written. Context categories are NOT semantic capture-role proofs.
No hardware, freshness clearance, PDF authoring or emulator change.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
import h1697_private_small_domain_formats as base
from h1640_remaining_scope_freshness import save
from h1650_score_masked_state import digest

LOCKS = {
    'experiments/h1697_private_small_domain_formats.py': '63e221edbfe1821099282685875967463e906c595bef8e1576d26b5eac8d8b47',
    'tmp/ledger33/current/h1697_private_small_domain_formats/report.json': '9b00b1208edd277ac92781b6793c360d365a65faf444283d7d55767621f82f38',
}


def file_kind(raw):
    if raw.startswith(b'%PDF'): return 'PDF'
    if raw.startswith(b'\0\0\0\1Bud1'): return 'desktop_metadata_magic'
    if b'\0' in raw: return 'unparsed_NUL_binary'
    return 'text'


def context(text, match):
    start = text.rfind('\n', 0, match.start()) + 1
    end = text.find('\n', match.end())
    if end < 0: end = len(text)
    line = text[start:end]
    return dict(same_line='\n' not in match.group() and '\r' not in match.group(),
        comma=',' in match.group(), sole_record=line.strip() == match.group().strip(),
        adjacent_numeric_dot=(match.start() > 0 and text[match.start()-1] == '.')
            or (match.end() < len(text) and text[match.end()] == '.'),
        following_comma_numeric=bool(re.match(r'\s*,\s*(?:0[xX])?[0-9a-fA-F]', text[match.end():])))


def inspect(private):
    pair, packed, decimal, binary = base.patterns()
    counts, contexts, csv_counts = Counter(), Counter(), Counter()
    for path in sorted(private.rglob('*')):
        if not path.is_file(): continue
        raw = path.read_bytes(); kind = file_kind(raw)
        counts['files'] += 1; counts['bytes'] += len(raw)
        counts[kind+'_files'] += 1
        counts[kind+'_byte_occurrences'] += sum(raw.count(b) for b in binary)
        views = []
        if kind == 'PDF':
            proc = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True)
            if proc.returncode or proc.stderr: raise ValueError('extraction incomplete')
            views.append(('extracted', proc.stdout.decode('utf-8')))
            counts['nonempty_PDF_page_texts'] += sum(bool(p.strip()) for p in proc.stdout.split(b'\f'))
        else:
            try: views.append(('UTF8', raw.decode('utf-8')))
            except UnicodeError: views.append(('Latin1', raw.decode('latin1')))
            for encoding in ('utf-16-le', 'utf-16-be'):
                try: views.append((encoding, raw.decode(encoding)))
                except UnicodeError: pass
        file_matches = 0
        for view, text in views:
            local_matches = 0
            for family, pattern in (('hex_pair', pair), ('decimal_pair', decimal), ('packed', packed)):
                for match in pattern.finditer(text):
                    file_matches += 1; local_matches += 1
                    key = kind+'_'+view+'_'+family
                    contexts[key+'_occurrences'] += 1
                    for name, present in context(text, match).items():
                        contexts[key+'_'+name] += int(present)
            if local_matches and view == 'UTF8':
                # Parsing comma syntax locates field boundaries only. There is
                # no guessed header/schema and no declaration of operand roles.
                rows = list(csv.reader(io.StringIO(text), strict=True))
                csv_counts['parsed_files_with_matches'] += 1
                csv_counts['rows'] += len(rows)
                widths = {len(row) for row in rows if row}
                csv_counts['uniform_width_files'] += len(widths) == 1
                for row in rows:
                    for field in row:
                        csv_counts['fields_containing_whole_possible_pair'] += bool(pair.search(field) or decimal.search(field))
        counts['files_with_text_matches'] += bool(file_matches)
    return dict(counts=dict(counts), contexts=dict(contexts), comma_syntax=dict(csv_counts))


def synthetic_controls():
    pair, _, decimal, _ = base.patterns()
    tests = (
        ('0, 5', pair, dict(same_line=True, comma=True, sole_record=True)),
        ('record, 0, 5, 12', pair, dict(same_line=True, comma=True, sole_record=False, following_comma_numeric=True)),
        ('0\n5', pair, dict(same_line=False, comma=False, sole_record=True)),
        ('record: 0 5.0', pair, dict(same_line=True, comma=False, sole_record=False, adjacent_numeric_dot=True)),
        ('32768, 14', decimal, dict(same_line=True, comma=True, sole_record=True)),
    )
    for text, pattern, expected in tests:
        match = pattern.search(text); assert match is not None
        got = context(text, match)
        assert all(got[k] == v for k, v in expected.items())
    assert file_kind(b'%PDF synthetic') == 'PDF'
    assert file_kind(b'\0\0\0\1Bud1 synthetic') == 'desktop_metadata_magic'
    assert file_kind(b'unknown\0bytes') == 'unparsed_NUL_binary'
    assert file_kind(b'0, 5') == 'text'
    return dict(context_cases=len(tests), magic_cases=4,
        policy='Embedded/comma/numeric-dot matches remain unresolved without a semantic schema.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--private-ledger-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); root, private, out = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    for name, sha in LOCKS.items(): assert digest(root/name) == sha, name
    controls = synthetic_controls()
    try:
        old_counts = base.inspect(private)
        localized = inspect(private)
    except Exception:
        # Library and OS diagnostics can contain private filenames or contents.
        raise SystemExit('H1705 private audit incomplete; diagnostics withheld') from None
    baseline = json.loads((root/'tmp/ledger33/current/h1697_private_small_domain_formats/report.json').read_text())
    assert dict(old_counts) == baseline['counts'], 'Private aggregate baseline changed; no clearance'
    total = sum(v for k, v in old_counts.items() if k.startswith('possible_'))
    localized_total = sum(v for k, v in localized['counts'].items() if k.endswith('_byte_occurrences'))
    localized_total += sum(v for k, v in localized['contexts'].items() if k.endswith('_occurrences'))
    assert total == localized_total == 188
    out.mkdir(parents=True)
    report = dict(experiment='h1705_private_match_context', status='STRUCTURALLY_LOCALIZED_SEMANTICALLY_UNRESOLVED',
        possible_occurrences_nonunique=total, prior_aggregate_reproduced=True,
        private_aggregate=localized, synthetic_controls=controls,
        boundary='The same188 nonunique syntax/layout occurrences are localized by public context categories only. No schema authenticates or rejects a capture role; embedded fields and desktop metadata magic are not dismissed. No image-content, arbitrary binary, dynamic-generator or complete-ledger absence claim.',
        private_identities_contents_hashes_membership_lists_published=False,
        hardware_execution='none', manifest_frozen=False, freshness_clearance=False,
        candidate_default_or_paper_change=False, sha256=dict(script=digest(Path(__file__)), public_evidence=LOCKS))
    save(out/'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'possible_occurrences_nonunique', 'private_aggregate')}, sort_keys=True), flush=True)


if __name__ == '__main__': main()
