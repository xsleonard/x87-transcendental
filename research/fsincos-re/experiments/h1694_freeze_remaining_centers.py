#!/usr/bin/env python3
"""Deliberate tuple-provenance refinement and freeze for remaining centers.

Unlike a literal significand filter, actual instruction/RC/PC/operand history
distinguishes software and sibling instruction records. The old standalone
pair remains excluded, with no masks/prestates used to claim novelty.
Any unknown public positive or private possible collision stops the freeze.
"""
from __future__ import annotations
import argparse
import json
import marshal
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import h1690_exact_center_public_inventory as public
import h1691_private_center_representation_audit as private_audit
import h1692_remaining_center_state_bank as bank_module
import h1693_center_state_verifier as verifier
from h1640_remaining_scope_freshness import save

BANK = 'tmp/ledger33/current/h1692_remaining_center_state_bank/bank.json'
INVENTORY = 'tmp/ledger33/current/h1690_exact_center_public_inventory/public_inventory.json'
LOCKS = {
    BANK: '4a2730f5bb792b90da2ea7319be6231c69337cd54cca81c8d276392e57022f7d',
    INVENTORY: 'a28dacc932c9a817d6b8ac367eeb1f4dd8b3e9a34629af3fa4e97fb474049a07',
    'experiments/h1690_exact_center_public_inventory.py': '4a47b748768ffaa9f8b194f659cb309644f0a1d562b8416301cc70fe2e9edc16',
    'experiments/h1691_private_center_representation_audit.py': '7e39e927b0504298cd9088b80b18fe198455818206e02cf6d28aa8250ef8b480',
    'experiments/h1692_remaining_center_state_bank.py': 'f490049f3d83767f376c95895e05d69106deb6fa9e40f7088b24f003a986eedf',
    'experiments/h1693_center_state_verifier.py': '33862a62e095d18b008e04ef795c10d9c7956c2d21864e10bb40d5d7b71ae26f',
    'tmp/ledger33/current/h1693_center_state_preflight/report.json': '22c53316d6eafc63b870a693ca2ed0b7e84abfa5860ef5d13f3cbccb10d49ebb',
    'tmp/ledger33/current/h1654_capture_static_audit/report.json': '7a5b0198db87093a708e7c8c513eea63c5cce82e6ddcc0dbf5296c4302689cc7',
}
digest = verifier.primary.digest


def artifact_path(root, name):
    path = root / name
    return path if path.exists() else root / 'tmp/retired-notes' / name


def reconcile(root, inventory, targets, old):
    classes, reviewed = Counter(), {}
    for name, entry in inventory.items():
        assert digest(artifact_path(root, name)) == entry['sha256'], name
        seen = set(entry['operands'])
        if name.startswith('transfer-tests/h1641/'):
            assert seen <= old
            role = 'opened_standalone_pair_reserved'
        elif name in ('capture-kit/inputs/f2xm1_validation_h257.txt',
                      'capture-kit/inputs/sibling_fptan_f2xm1_h245.txt'):
            # H1689 authenticated the runners, input rows and sibling-only
            # raw mappings; no inference from filename alone is needed.
            role = 'verified_sibling_instruction_input'
        elif name in ('notes/HANDOFF-collision-gate.md', 'notes/h1638-h1643-tiny-and-remaining-scope.md'):
            assert seen <= old
            role = 'documentation_of_reserved_pair'
        elif name == 'tmp/ledger33/current/h1633_shared_table_audit/preflight.json':
            assert json.loads((root / name).read_text())['hardware_observations'] == 0
            role = 'software_preflight'
        elif name == public.BANK:
            data = json.loads((root / name).read_text())
            assert data['hardware_execution'] == 'none' and not data['manifest_frozen']
            role = 'software_proposal'
        elif name == 'tmp/ledger33/current/h1640_remaining_scope_freshness/report.json':
            assert seen <= old
            data = json.loads((root / name).read_text())
            assert data['hardware_execution'] == 'none' and not data['manifest_frozen']
            role = 'old_freshness_metadata'
        elif name in ('tmp/ledger33/current/h1642_score_remaining_scope/score.json',
                      'tmp/ledger33/current/h1645_masked_status_audit/h1641_score.json'):
            assert seen <= old
            role = 'reanalysis_of_reserved_pair'
        elif name.startswith(('tmp/ledger33/current/h1689_exact_center_contract/',
              'tmp/ledger33/current/h1688-h1689-replay.vbEwt5/h1689_exact_center_contract/')):
            # Require exact immutable artifact identity, including the replay.
            report = json.loads((root / 'tmp/ledger33/current/h1689_exact_center_contract/report.json').read_text())
            assert entry['sha256'] == report['sha256']['artifacts'][Path(name).name]
            role = 'H1689_typed_reanalysis_or_software_prediction'
        else:
            raise AssertionError('Unreviewed public positive: ' + name)
        classes[role] += 1
        reviewed[name] = dict(role=role, sha256=entry['sha256'])
    assert len(reviewed) == 42 and len(targets - old) == 26
    # The known generated R62/R63 reservation has no center operand at all.
    generated = json.loads((root / 'tmp/ledger33/current/h1688_generated_small_operand_provenance/generator_replay.json').read_text())
    assert not targets & set(generated['inputs'])
    return reviewed, classes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path); p.add_argument('--private-ledger-dir', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, private, out = a.root.resolve(), a.private_ledger_dir.resolve(), a.output_dir.resolve()
    assert private.is_dir() and not out.exists() and out.is_relative_to(root)
    evidence = dict(LOCKS)
    for name, sha in evidence.items():
        assert digest(artifact_path(root, name)) == sha, name
    bank = json.loads((root / BANK).read_text())
    for name, sha in bank['sha256']['evidence'].items():
        assert digest(artifact_path(root, name)) == sha, name
        evidence[name] = sha
    assert bank_module.operands(root) == bank['operands']
    repeated = bank_module.predictions(root, bank['operands'])
    assert repeated == [{k: v for k, v in row.items() if k != 'center_formula'} for row in bank['predictions']]
    _, failures, preflight, _ = verifier.verify(root, bank['predictions'])
    assert not failures
    inventory = json.loads((root / INVENTORY).read_text())
    targets = {op for entry in inventory.values() for op in entry['operands']}
    old = {'403d fb53d14aa9c2f2c1', 'c03d fb53d14aa9c2f2c1'}
    reviewed, classes = reconcile(root, inventory, targets, old)
    excluded = [private, out, (root / BANK).parent,
        root / 'tmp/ledger33/current/h1690_exact_center_public_inventory',
        root / 'tmp/ledger33/current/h1691_private_center_representation_audit',
        root / 'tmp/ledger33/current/h1693_center_state_preflight']
    command = ['rg', '--files-with-matches', '--pcre2', '--hidden', '--no-ignore',
               '--search-zip', '--text', '--ignore-case', '--glob', '!**/.git/**']
    for path in excluded:
        command += ['--glob', '!**/' + path.relative_to(root).as_posix() + '/**']
    command += [public.patterns(targets), str(root)]
    print('Replaying predictions and refreshing paired-operand public/private checks.', flush=True)
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.returncode in (0, 1) and not process.stderr
    found = {Path(line).resolve().relative_to(root).as_posix().removeprefix('tmp/retired-notes/')
             for line in process.stdout.decode().splitlines()}
    # The preparation just added source literals for the EXCLUDED old pair.
    # Reconcile those explicit new software sources, not an arbitrary glob
    # exemption that could conceal other historical operands or captures.
    allowed_sources = {'experiments/h1692_remaining_center_state_bank.py',
                       'experiments/h1694_freeze_remaining_centers.py'}
    for name in sorted(found - set(reviewed)):
        path = root / name
        if name in allowed_sources:
            source_name = name
        elif name.startswith('experiments/__pycache__/') and name.endswith('.pyc'):
            source_name = 'experiments/' + path.name.split('.')[0] + '.py'
            assert source_name in allowed_sources, name
            cached = marshal.loads(path.read_bytes()[16:])
            assert cached == compile((root / source_name).read_text(), str(root / source_name), 'exec')
        else:
            raise AssertionError('Unreviewed new public positive: ' + name)
        if source_name != 'experiments/h1694_freeze_remaining_centers.py':
            assert digest(root / source_name) == evidence[source_name]
        reviewed[name] = dict(role='new_software_source_for_reserved_pair', sha256=digest(path))
        classes['new_software_source_for_reserved_pair'] += 1
    assert found == set(reviewed), ('missing previous public positives', sorted(set(reviewed) - found))
    hidden, positive = private_audit.inspect(private, targets)
    assert positive == 0 and not hidden['numeric_parse_failures'] and not hidden['long_numeric_tokens_unparsed']
    selected = [dict(row, capture_state='FROZEN_UNOPENED') for row in bank['predictions']]
    assert len(selected) == 624 and {r['operand'] for r in selected} == targets - old
    assert len({(r['instruction'], r['mode'], r['pc'], r['operand']) for r in selected}) == 624
    out.mkdir(parents=True)
    provenance = dict(status='REVIEWED_LOCALLY_VISIBLE_STANDALONE_TUPLES',
        public_reviewed_files=reviewed, public_role_counts=dict(classes), private_counts=dict(hidden),
        selected_known_public_standalone_collisions=0, selected_checked_private_collisions=0,
        old_standalone_center_operands_reserved=2,
        explicit_policy_refinement='Use instruction/RC/PC/raw80 operand provenance for these26 centers, distinguishing software-only and verified sibling instruction records. Previously opened standalone operands remain excluded regardless of new masks/state fields. Unknown PC reserves all PC.',
        limits='Locally visible known formats and documented generated history, not proof every prior capture anywhere is recoverable. Private structured/image/dynamic representations remain a general limitation; no checked possible target collision is unresolved here.',
        private_identities_contents_hashes_membership_lists_published=False)
    save(out / 'provenance.json', provenance)
    save(out / 'manifest.json', selected)
    with (out / 'inputs.txt').open('x') as stream:
        stream.write(''.join(row['capture_line'] + '\n' for row in selected))
    with (out / 'run_capture.sh').open('x') as stream:
        stream.write((root / 'experiments/h1694_run_capture.sh').read_text())
    freeze = dict(experiment='h1694_remaining_exact_centers', capture_state='FROZEN_UNOPENED',
        frozen_utc=datetime.now(timezone.utc).isoformat(), unique_operands=26, unique_capture_tuples=624,
        one_observation_maximum_per_tuple=True, instruction_retries=0, candidate_changed=False,
        selected_kinds=bank['counts']['kinds'], preflight=dict(preflight),
        hardware_target=dict(host='45.32.204.118', family=6, model=85,
            capture_binary_sha256='1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e'),
        claim_boundary='Prospective remaining exact-center output/full-SW challenge. With the old48 rows this covers the finite28-operand model center domain at both instructions/allRC/PC24,53,64, if predictions survive. Not all-input silicon or arbitrary-control-state closure.',
        sha256=dict(evidence=evidence, manifest=digest(out / 'manifest.json'), inputs=digest(out / 'inputs.txt'),
            provenance=digest(out / 'provenance.json'), runner=digest(out / 'run_capture.sh'),
            scorer=digest(root / 'experiments/h1693_center_state_verifier.py'), freezer=digest(Path(__file__))))
    save(out / 'FREEZE.json', freeze)
    with (out / 'CHECKSUMS.sha256').open('x') as stream:
        for name in ('FREEZE.json', 'manifest.json', 'inputs.txt', 'provenance.json', 'run_capture.sh'):
            stream.write(f'{digest(out / name)}  {name}\n')
    print(json.dumps(dict(state=freeze['capture_state'], operands=26, tuples=624,
                         public_role_counts=dict(classes), private_possible_collisions=positive), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
