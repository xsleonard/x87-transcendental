#!/usr/bin/env python3
"""Independently refine the broad inventory to padded raw operand syntax.

No private reads, clearance, hardware, model edits or inferred capture labels.
Short-hex/decimal/binary/generated representations remain separate obligations.
"""
import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from h1665_small_denormal_provenance import digest
from h1640_remaining_scope_freshness import save

PARENT = 'tmp/ledger33/current/h1665_small_denormal_provenance_v2/'
LOCKS = {
    PARENT+'public_inventory.json': 'a02695d489680b8418cb1a03154d64c7c17c7cb7d5844308a85c15c2613ea051',
    PARENT+'report.json': 'e1313f2af7a5a8cb4154b3ac4f304d894a5db89aabdb380357795552874fe110',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert digest(root/name) == sha
    inventory = json.loads((root/PARENT/'public_inventory.json').read_text())['inventory']
    paths = [root/name for name, row in inventory.items() if row['operand_lexical_lines']]
    assert all(p.is_relative_to(root) and 'supplemental' not in p.relative_to(root).parts for p in paths)
    pattern = r'(?<![0-9a-z_])(?:0000|8000)(?:[ :\t]+)?000000000000000[1-9a-f](?![0-9a-z_])'
    process = subprocess.run(['rg', '--json', '--pcre2', '--ignore-case', '--search-zip', '--text',
                              pattern, *(str(p) for p in paths)], capture_output=True, check=False)
    assert process.returncode in (0, 1) and not process.stderr
    hits, counts = {}, Counter()
    for line in process.stdout.splitlines():
        event = json.loads(line)
        if event['type'] != 'match':
            continue
        data = event['data']; name = Path(data['path']['text']).relative_to(root).as_posix()
        row = hits.setdefault(name, dict(matching_lines=0, first_line=data['line_number'],
                                         operand_spellings=set(), sha256=digest(root/name)))
        row['matching_lines'] += 1
        row['operand_spellings'].update(m['match']['text'].lower() for m in data['submatches'])
    for name, row in hits.items():
        row['operand_spellings'] = sorted(row['operand_spellings'])
        if name.startswith(('tmp/ledger33/current/h1597_broad_encoding_ub_audit/',
                            'tmp/ledger33/current/h1598_signed_payload_ub_audit/',
                            'tmp/ledger33/current/h1638_tiny_c_transfer/',
                            'tmp/ledger33/current/h1661_normalization_and_c0_proposals/')):
            row['provenance_class'] = 'previously_declared_software_only'
        elif name == 'experiments/h1618_isolated_cosine_transfer.py' or name.startswith('experiments/__pycache__/'):
            row['provenance_class'] = 'software_source_or_bytecode'
        else:
            row['provenance_class'] = 'requires_manual_provenance'
        counts[row['provenance_class']] += 1
    out.mkdir(parents=True)
    save(out/'padded_operand_inventory.json', hits)
    report = dict(experiment='h1665_refine_public_operands',
        status='PADDED_SYNTAX_REFINEMENT_NOT_CLEARANCE', broad_candidate_files=len(paths),
        refined_files=len(hits), provenance_file_counts=dict(counts),
        hardware_execution='none', private_ledger_access='none', freshness_policy_changed=False,
        claim_boundary='Padded raw operand syntax only, with identifier boundaries. Source/software appearances do not establish capture. Other representations and dynamic generators are not excluded.',
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS,
                    padded_inventory=digest(out/'padded_operand_inventory.json')))
    save(out/'report.json', report)
    print(json.dumps({k:report[k] for k in ('status', 'broad_candidate_files', 'refined_files', 'provenance_file_counts')}, sort_keys=True))


if __name__ == '__main__':
    main()
