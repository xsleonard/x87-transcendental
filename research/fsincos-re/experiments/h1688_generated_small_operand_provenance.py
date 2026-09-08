#!/usr/bin/env python3
"""Reconcile generated historical operands; inspect private formats locally.

No hardware, freshness clearance, capture labels, private identifiers/hashes/
contents/membership lists, or emulator edits. A historical execution report
reserves tuples against recapture but does not substitute for the missing raw
archive when validating an output or an exact prestate.
"""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
import gen_specials
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

LOCKS = {
    'experiments/gen_specials.py': '643b3b7dfda6a3c87b1bc749fa48409dda9c59429ae440b8dbe1dcd05a8f7656',
    'experiments/run_specials.sh': '498a4e56984847b23aadac5c28c67c89f98635cbea9cf9d9eead767ed28a2c50',
    'tmp/ledger33/current/h1665_small_denormal_provenance_v2/report.json': 'e1313f2af7a5a8cb4154b3ac4f304d894a5db89aabdb380357795552874fe110',
    'tmp/ledger33/current/h1665_refine_public_operands/report.json': '0fc3ae7f08878ec27038f1ce7df3dbfe0ed648dad41249c63e673b371da870a2',
}
NOTE_START = '## ROUNDS 62/63 — TASK-3 INSURANCE SWEEPS FIND AND CLOSE TWO MODEL'
NOTE_END = '## h665-h669 — TASK 1/2 OF THE CLOSURE GUIDE:'
# Deliberately broad POSSIBLE operand syntax, not verified tuple records.
# Include packed80, hex or decimal small fields, and cross-line separators.
SMALL = r'(?:0x)?0*(?:[1-9a-f]|1[0-5])'
PAIR = re.compile(r'(?<![0-9a-z_])(?:0x)?(?:0000|8000|32768|0)'
                  r'[\s:,"\[\]]+' + SMALL + r'(?![0-9a-z_])', re.I)
PACKED = re.compile(r'(?<![0-9a-f])(?:0000|8000)000000000000000[1-9a-f](?![0-9a-f])', re.I)
SIG = re.compile(r'(?<![0-9a-f])000000000000000[1-9a-f](?![0-9a-f])', re.I)


def public_history(root):
    out, classes = io.StringIO(), io.StringIO()
    # The pinned generator only writes to stdout/stderr, not a file or device.
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(classes):
        gen_specials.main()
    rows, annotations = out.getvalue().splitlines(), classes.getvalue().splitlines()
    assert len(rows) == len(annotations) == 3318 and len(set(rows)) == 3318
    matches, keys = [], set()
    for index, (operand, annotation) in enumerate(zip(rows, annotations)):
        assert annotation.startswith(operand + ' ')
        se, sig = (int(word, 16) for word in operand.split())
        kind = ('small_denormal' if se in (0, 0x8000) and 1 <= sig <= 15 else
                'zero' if se in (0, 0x8000) and sig == 0 else
                'infinity' if se in (0x7fff, 0xffff) and sig == 1 << 63 else None)
        if kind is None:
            continue
        matches.append(dict(input_index_zero_based=index, operand=operand,
                            kind=kind, generator_class=annotation.split()[-1]))
        for instruction in ('fsin', 'fcos'):
            for mode in ('rn', 'rd', 'ru', 'rz'):
                keys.add((instruction, mode, operand))
    # Independent construction of the small field-pattern subset: powers of
    # two and low-one runs. Neither the large complements nor the alternating
    # 63-bit constants can fall in1..15.
    small_sigs = ({1 << k for k in range(4)} | {(1 << k) - 1 for k in range(1, 5)})
    assert small_sigs == {1, 2, 3, 4, 7, 8, 15}
    actual = {(int(r['operand'].split()[0], 16), int(r['operand'].split()[1], 16))
              for r in matches if r['kind'] == 'small_denormal'}
    assert actual == {(sign, sig) for sign in (0, 0x8000) for sig in small_sigs}
    assert len(matches) == 18 and len(keys) == 144
    historical = (root / 'tmp/retired-notes/notes/HANDOFF-collision-gate.md').read_text()
    start, end = historical.index(NOTE_START), historical.index(NOTE_END)
    excerpt = historical[start:end]
    assert '3,318 operands' in excerpt and 'FSIN+FCOS x rn/rd/ru/rz' in excerpt
    assert 'Data: /root/h491/specials/ on the i7' in excerpt
    runner = (root / 'experiments/run_specials.sh').read_text()
    assert 'for insn in sin cos;' in runner and 'for mode in rn rd ru rz;' in runner
    assert '/root/x87_capture_x86_64 $insn $mode --status' in runner
    return rows, matches, sorted(keys), excerpt


def private_aggregate(root):
    """Only aggregate counters cross this boundary; never return file data."""
    counts = Counter()
    # This is not a structured tuple ledger parser. Non-text formats and
    # dynamically generated operands retain explicit unresolved provenance.
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        counts['files_examined'] += 1
        raw = path.read_bytes()
        counts['raw_bytes_examined'] += len(raw)
        raw_hits = 0
        for sig in range(1, 16):
            for se in (0, 0x8000):
                raw_hits += raw.count(sig.to_bytes(8, 'little') + se.to_bytes(2, 'little'))
                raw_hits += raw.count(se.to_bytes(2, 'big') + sig.to_bytes(8, 'big'))
        counts['possible_packed_binary80_occurrences'] += raw_hits
        if raw.startswith(b'%PDF'):
            proc = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode:
                # Never expose external diagnostics, which can name a source.
                raise RuntimeError('Private PDF extraction failed; audit incomplete')
            counts['pdf_files_extracted'] += 1
            counts['pdf_nonempty_page_texts'] += sum(bool(p.strip()) for p in proc.stdout.split(b'\f'))
            counts['pdf_diagnostic_bytes'] += len(proc.stderr)
            text = proc.stdout.decode('utf-8')
        else:
            try:
                text = raw.decode('utf-8')
                counts['utf8_text_files'] += 1
            except UnicodeDecodeError:
                # ASCII field syntax survives Latin1 decoding, but this does
                # not prove arbitrary 8-bit or binary records fully parsed.
                text = raw.decode('latin1')
                if b'\x00' in raw:
                    counts['unresolved_binary_files'] += 1
                else:
                    counts['ascii_preserving_8bit_files'] += 1
        counts['decoded_characters'] += len(text)
        counts['possible_small_pair_occurrences'] += len(PAIR.findall(text))
        counts['possible_packed_hex80_occurrences'] += len(PACKED.findall(text))
        counts['small_padded_signature_occurrences'] += len(SIG.findall(text))
    return dict(counts=dict(counts),
        private_identities_contents_hashes_membership_lists_published=False,
        extraction_role='Text/byte representation audit only; not a complete structured capture parser or absence proof over dynamic generators, binary records, or image-only PDF content.',
        freshness_clearance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--private-ledger-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, private, out = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not out.exists() and out.is_relative_to(root)
    for name, expected in LOCKS.items():
        assert digest(root / name) == expected, name
    rows, matches, keys, excerpt = public_history(root)
    private_report = private_aggregate(private)
    out.mkdir(parents=True)
    save(out / 'historically_reported_reservations.json', dict(
        status='REPORTED_CAPTURE_RESERVATIONS_NOT_RAW_VERIFIED_RESULTS',
        source='R62/R63 historical handoff + pinned generator/runner',
        raw_archive_location='i7 /root/h491/specials',
        do_not_rerun=True, operands=matches,
        conservative_instruction_mode_operand_keys=[list(k) for k in keys],
        PC_masks_prestates='Runner source suggests default controls, but original binary/raw prestates are not authenticated here. Do not infer an available PC/mask/state tuple from that suggestion.',
        numerical_status_credit=0, hardware_rows_opened=0))
    save(out / 'generator_replay.json', dict(count=len(rows), inputs=rows))
    # Only the PUBLIC historical paragraph is retained verbatim.
    save(out / 'historical_public_statement.json', dict(text=excerpt))
    report = dict(experiment='h1688_generated_small_operand_provenance',
        status='HISTORICAL_RESERVATIONS_AND_FORMAT_AUDIT_NOT_CLEARANCE',
        public_counts=dict(generator_operands=len(rows), small_signed_operands=14,
            zero_signed_operands=2, infinity_signed_operands=2,
            historically_reported_instruction_mode_operand_keys=len(keys),
            raw_verified_output_or_status_rows=0),
        private_aggregate=private_report,
        conclusion='The literal H1665 scan could not exclude generated prior operands. The known specials generator reconstructs seven small significands with both signs, plus zeros/infinities, in a historically reported hardware campaign. Reserve them against recapture; missing raw evidence cannot verify their outputs or prestates. Other small significands are not cleared by complement.',
        hardware_execution='none', capture_labels_opened=False, manifest_frozen=False,
        freshness_policy_changed=False, candidate_default_or_paper_changed=False,
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS,
            public_artifacts={p.name: digest(p) for p in sorted(out.iterdir())}))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'public_counts', 'private_aggregate')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
