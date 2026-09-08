#!/usr/bin/env python3
"""Exact-center model contract and instruction-specific retained provenance.

At offset zero the entire table correction vanishes by zero absorption;
the endpoint is signed RC64 of the selected native ROM word. Exhaustive
enumeration here is of H1639's finite reachable-center external preimages,
not of every external input or every historical capture archive.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from pathlib import Path
import h1636_retained_rz_pc_transfer as independent
import h1638_tiny_c_transfer as transfer
from h1640_remaining_scope_freshness import save

MODEL = 'tmp/ledger33/current/h1638_tiny_c_transfer/'
PROPOSALS = 'tmp/ledger33/current/h1639_remaining_scope_proposals/bank.json'
H245 = 'capture-kit-captures/skylake-sibling-h245/'
H257 = 'capture-kit-captures/skylake-f2xm1-h257/'
H1641 = 'transfer-tests/h1641/'
SCORE = 'tmp/ledger33/current/h1642_score_remaining_scope/report.json'
LOCKS = {
    PROPOSALS: 'c9b28e70b337b3fe3ce2fa75debc8b1c97f5d18168ebc1e1c4eb528bc8d617f1',
    MODEL + 'report.json': 'db6c8cbc1e0e2c9acdb54da5e1e381407a6b8c5f6f62cc7b1c52c4d90f8510e0',
    'src/p5_rom_constants.h': '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
    'experiments/h1633_shared_table.h': '238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1634_independent_table_certificate.py': '41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa',
    'experiments/h1636_retained_rz_pc_transfer.py': '9d44c92b5c6267752da7bab906e160ae82bb1eda338f93c86c8e7732adb45707',
    'experiments/h1638_tiny_c_transfer.py': 'db99dc020ab7372af7f8018a11c4e81a7c73afd227c4dccbbcc080d3b38a4fd1',
    'capture-kit/inputs/sibling_fptan_f2xm1_h245.txt': '4ac60935c5551165712a5bd828669e72edeadf1701784fb92339753bc55781ee',
    'capture-kit/inputs/f2xm1_validation_h257.txt': 'dd5ac3cf3ca1f07112077f496876074121545b13047574b4ad18c501b1cf0225',
    'capture-kit/run_siblings_prebuilt.sh': '99467a810b9ce1d67288cb8c7487d103a77fc54dcafd816ea206ef0eb55eb864',
    'capture-kit/run_f2xm1_validation_prebuilt.sh': '8aa40f0644df8ffe8c754cdd8ca80ce18f08a82b3319e6b3f9ab9546e3070e8b',
    H245 + 'SHA256SUMS': 'a0d45e72cd6bcc6b145029fd3f0deeac53b1701dae355b204d030db14b3f2e7a',
    H257 + 'SHA256SUMS': '54f21d30b1288f40daaa726b19939706021ae6ba94b2b19cba9c4bf8d91be74f',
    H1641 + 'FREEZE.json': '066ac4f086d9132ba157195af02a3aaffaccb4f3e05c5337a4689b634f35f833',
    H1641 + 'manifest.json': '453ecfe5ab81dc49c23cd045d85af341df3e8e6b2125cca6dd7c064568d06a84',
    SCORE: '8f19ff7e9a95df22824497abec43b765ee73d832296444bed9976b86b7092293',
}
proof = independent.proof


def zero_offset(operand, instruction, mode):
    r, _, cosine, negative, reduced = proof.external(operand, instruction)
    b = proof.table_lane(r)
    assert b in (18, 22, 26, 30, 36, 44) and r == proof.Fraction(b, 64)
    pre, _, _, precision, _, center = proof.table_graph(r, b)
    assert precision == 0 and center
    assert pre == proof.TABLE[b]
    value, c1 = proof.final(proof.TABLE[b][cosine], negative, mode)
    return dict(output=value, C1=c1, b=b, cosine=cosine, negative=negative,
                reduced=reduced, exact_ROM_prevalue=str(proof.TABLE[b][cosine]))


def input_inventory(root, targets):
    hits, files = [], {}
    # This scoped input census does NOT certify arbitrary software generators,
    # other directories, remote archives or private history absent.
    for path in sorted((root / 'capture-kit/inputs').glob('*.txt')):
        for index, line in enumerate(path.read_text().splitlines()):
            if not re.fullmatch(r'[0-9a-fA-F]{4}\s+[0-9a-fA-F]{16}', line.strip()):
                continue
            operand = ' '.join(line.lower().split())
            if operand in targets:
                name = path.relative_to(root).as_posix()
                files[name] = proof.digest(path)
                hits.append(dict(input_file=name, index_zero_based=index, operand=operand))
    return hits, files


def sibling_records(root, targets):
    records, evidence, unique = [], {}, set()
    for base, input_name, insns in (
        (H245, 'sibling_fptan_f2xm1_h245.txt', ('fptan', 'f2xm1')),
        (H257, 'f2xm1_validation_h257.txt', ('f2xm1',)),
    ):
        inputs = (root / 'capture-kit/inputs' / input_name).read_text().splitlines()
        selected = [(i, op.lower()) for i, op in enumerate(inputs) if op.lower() in targets]
        assert len(selected) == 12
        pins = dict((name, sha) for sha, name in
                    (line.split() for line in (root / base / 'SHA256SUMS').read_text().splitlines()))
        for insn in insns:
            settings = [(mode, 64, '') for mode in ('rn', 'rd', 'ru')]
            if base == H245:
                settings += [('rn', pc, '_pc' + str(pc)) for pc in (24, 53, 64)]
            for mode, pc, suffix in settings:
                stem = 'target_' + insn if base == H245 else 'f2xm1_validation_h257'
                name = f'{stem}_{mode}{suffix}_status.txt'
                path = root / base / name
                assert proof.digest(path) == pins[name]
                evidence[base + name] = pins[name]
                lines = path.read_text().splitlines()
                assert len(lines) == len(inputs)
                for i, op in selected:
                    fields = lines[i].split()
                    assert fields[0] == 'OK' and fields[-2] == 'SW'
                    assert len(fields) == (7 if insn == 'fptan' else 5)
                    int(fields[-1], 16)
                    key = (insn, mode, pc, op)
                    records.append(dict(input_file='capture-kit/inputs/' + input_name,
                        capture_file=base + name, index_zero_based=i, operand=op,
                        instruction=insn, mode=mode, precision_control=pc,
                        repeated_key_within_selected_historical_files=key in unique))
                    unique.add(key)
    assert len(records) == 180 and len(unique) == 120
    assert not {r['instruction'] for r in records} & {'fsin', 'fcos'}
    return records, evidence, len(unique)


def standalone_records(root, targets):
    manifest = json.loads((root / H1641 / 'manifest.json').read_text())
    opened = json.loads((root / H1641 / 'OPENED.json').read_text())
    assert opened['capture_state'] == 'OPENED_ONCE'
    score = json.loads((root / SCORE).read_text())
    records, evidence = [], {}
    for lane in sorted({r['lane'] for r in manifest}):
        selected = [r for r in manifest if r['lane'] == lane]
        path = root / H1641 / 'hardware-output' / (lane + '.txt')
        expected_hash = score['sha256']['raw_outputs'][path.name]
        assert proof.digest(path) == expected_hash
        evidence[path.relative_to(root).as_posix()] = expected_hash
        lines = path.read_text().splitlines()
        assert len(lines) == len(selected)
        for index, (row, line) in enumerate(zip(selected, lines)):
            if row['operand'] not in targets:
                continue
            assert row['exact_center']
            result = zero_offset(row['operand'], row['instruction'], row['mode'])
            value, sw = proof.raw(line, True)
            assert value == result['output'] == row['output']
            assert (sw >> 9) & 1 == result['C1'] == row['C1']
            assert sw & 0x3f == row['exception_flags'] == 0x20
            records.append(dict(case_id=row['case_id'], lane=lane, index_zero_based=index,
                operand=row['operand'], instruction=row['instruction'], mode=row['mode'],
                precision_control=row['precision_control'], output=value,
                SW=f'{sw:04x}', **{k: v for k, v in result.items() if k != 'output'}))
    assert len(records) == 48 and len({r['operand'] for r in records}) == 2
    assert {r['b'] for r in records} == {30}
    return records, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output_dir.resolve()
    assert not out.exists()
    for name, expected in LOCKS.items():
        assert proof.digest(root / name) == expected, name
    bank = json.loads((root / PROPOSALS).read_text())
    centers = [r for r in bank['operands'] if any('center' in k for k in r['kinds'])]
    assert len(centers) == 28
    targets = {r['operand'] for r in centers}
    independent.initialize_proof(root)
    predictions = []
    for op in sorted(targets):
        for insn in ('fsin', 'fcos'):
            for mode in ('rn', 'rd', 'ru', 'rz'):
                predictions.append(dict(operand=op, instruction=insn, mode=mode,
                                        **zero_offset(op, insn, mode)))
    assert len(predictions) == 224
    counts = Counter(model_ROM_identity_checks=len(predictions))
    prior = json.loads((root / MODEL / 'report.json').read_text())
    binary_hashes = {}
    for label in ('candidate_O0', 'candidate_O2', 'candidate_O3', 'candidate_ubsan'):
        binary = root / MODEL / label
        binary_hashes[label] = proof.digest(binary)
        assert binary_hashes[label] == prior['sha256']['binaries'][label]
        for insn in ('fsin', 'fcos'):
            for mode in ('rn', 'rd', 'ru', 'rz'):
                selected = [r for r in predictions if r['instruction'] == insn and r['mode'] == mode]
                values, metadata, _ = transfer.run(binary, insn, mode, [r['operand'] for r in selected])
                for i, (row, value) in enumerate(zip(selected, values)):
                    assert value == row['output'] and metadata[i]['C1'] == row['C1']
                    assert metadata[i]['lane'] == 'table' and metadata[i]['precision'] == 0
                    assert metadata[i]['b'] == row['b']
                    counts['four_build_output_C1_center_checks'] += 1
    inputs, input_pins = input_inventory(root, targets)
    sibling, sibling_pins, unique_sibling = sibling_records(root, targets)
    standalone, standalone_pins = standalone_records(root, targets)
    assert len(inputs) == 24 and set(input_pins) == {
        'capture-kit/inputs/sibling_fptan_f2xm1_h245.txt',
        'capture-kit/inputs/f2xm1_validation_h257.txt'}
    counts.update(retained_sibling_center_appearances=len(sibling),
                  retained_sibling_unique_instruction_mode_PC_operand_keys=unique_sibling,
                  retained_standalone_center_output_C1_flags_checks=len(standalone),
                  newly_observed_hardware_tuples=0)
    out.mkdir(parents=True)
    save(out / 'exact_center_predictions.json', predictions)
    save(out / 'capture_kit_input_hits.json', inputs)
    save(out / 'sibling_provenance.json', sibling)
    save(out / 'standalone_retained_checks.json', standalone)
    report = dict(experiment='h1689_exact_center_contract',
        status='PASS_ZERO_OFFSET_MODEL_AND_TYPED_RETAINED_PROVENANCE',
        counts=dict(counts),
        proof='For a=0, M(a,a)=0, M(0,x)=M(x,0)=0, A(0,0)=0 and T67(0)=0. The Horner coefficient values are irrelevant to every correction product. Therefore both unrounded table endpoints equal the native leading ROM words for any coefficient values for which the graph is defined. Signed final RC64 and C1 remain explicit.',
        domain='All28 signed external exact-center operands enumerated by H1639 for the fixed M66 reducer; six reachable zero-offset centers. b52 zero-offset and b60 cell remain unreachable.',
        coverage='The two capture-kit input banks contain12 signed direct centers, but their180 selected raw appearances are FPTAN/F2XM1, not FSIN/FCOS. The48 already opened H1641 standalone rows cover only the signed high-q b30 pair. No transfer or new coverage is inferred from sibling rows.',
        historical_duplicate_note='The sibling files include60 repeated instruction/mode/PC/operand-key appearances within this selected set. They are historical repetitions, not additional unique evidence; no timing file or hardware runner is executed.',
        next='Exact-center predictions are fixed and analytically justified inside the model. Remaining standalone centers need complete public/private/remote tuple provenance before any new freeze; this scoped audit does not clear them.',
        hardware_execution='none', private_ledger_access='none', freshness_clearance=False,
        paper_default_or_candidate_change=False, new_candidate_numerical_misses=0,
        sha256=dict(script=proof.digest(Path(__file__)), binaries=binary_hashes,
            evidence={**LOCKS, **input_pins, **sibling_pins, **standalone_pins},
            artifacts={p.name: proof.digest(p) for p in sorted(out.iterdir())}))
    save(out / 'report.json', report)
    print(report['status'], dict(counts), flush=True)


if __name__ == '__main__':
    main()
