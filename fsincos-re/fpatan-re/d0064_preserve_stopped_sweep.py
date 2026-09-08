"""Inventory the deliberately interrupted construction sweep without closure.

The three both-parity endpoint witnesses already passed native capture.
The remaining optional construction work was interrupted normally. Preserve
all existing streams, authenticate their contents, and replay the last
recorded block to ensure its target records are complete. This is not a
full-binade completion receipt and must not be presented as one.
"""
from collections import Counter
import json
from pathlib import Path

from compressed_guard import digest
from d0049_algebraic_tie_preimages import domains, invert_target, graph, target_event
from d0056_outer_boundary_lattice import parameters, filtered_indices
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def main():
    scan = BASE / 'd0060-long-complete-binade-validated'
    output = scan / 'STOPPED.json'
    assert not output.exists() and not (scan / 'REPORT.json').exists()
    started = json.loads((scan / 'STARTED.json').read_text())
    for name, sha in started['source_sha256'].items():
        assert digest(HERE / name) == sha
    assert digest(Path(started['library_path'])) == started['library_sha256']
    domain = domains(0, -9)[0]
    width = 1 << 20
    first, expected_start = started['first_block'] * width, started['first_block'] * width
    counts = Counter()
    last = None
    with (scan / 'blocks.tsv').open() as stream:
        for line in stream:
            which, start, length, candidates = map(int, line.split())
            assert which == 0 and start == expected_start and length == min(width, domain['count'] - start)
            expected_start += length
            counts['recorded_blocks'] += 1
            counts['distinct_target_indices_in_recorded_blocks'] += length
            counts['recorded_boundary_candidates'] += candidates
            last = start, length, candidates
    assert last is not None and counts['recorded_blocks'] < started['blocks']
    last_block = last[0] // width
    last_rows, nonzero_rows, previous_word = [], [], None
    with (scan / 'targets.tsv').open() as stream:
        for line in stream:
            fields = line.split()
            assert int(fields[1]) == 0 and int(fields[3]) == -9
            assert started['first_block'] <= int(fields[2]) <= last_block
            counts[fields[0] + '_rows'] += 1
            if fields[0] == 'T':
                word = int(fields[4], 16)
                assert previous_word is None or word > previous_word
                previous_word = word
                counts[f'parity{fields[5]}'] += 1
                counts['H_changes'] += int(fields[6])
                counts['outer_changes'] += int(fields[7])
                if int(fields[2]) == last_block:
                    last_rows.append(fields)
            elif fields[0] == 'Z':
                counts['kernel_cut_changes'] += int(fields[8])
            else:
                assert fields[0] == 'W'
                if int(fields[10], 16):
                    nonzero_rows.append(fields)
                    counts['endpoint_separators'] += 1
    params = parameters(0, domain)
    candidates = list(filtered_indices(params, last[0], last[1]))
    assert len(candidates) == last[2]
    replayed_last = []
    for index in candidates:
        for word in invert_target(domain, domain['first'] + index * domain['modulus']):
            target, h, outer = graph(0, (word, -72))
            other_target, other_h, other_outer = graph(0, (word, -72), True)
            assert target == other_target
            replayed_last.append(['T', '0', str(last_block), '-9', f'{word:016x}',
                str(target_event(target)), str(int(h != other_h)), str(int(outer != other_outer))])
    assert replayed_last == last_rows
    prefix = BASE / 'd0062-long-prefix2/REPORT.json'
    witnesses = json.loads(prefix.read_text())
    assert nonzero_rows == witnesses['selected_records']
    native = json.loads((BASE / 'd0063/TIE-RULE-SCORE.json').read_text())
    assert native['counts']['baseline_union_misses'] == 0
    assert all(native['counts'][f'node0:{rule}:union_misses'] > 0
               for rule in ('nearest-odd', 'ties-away', 'ties-zero'))
    save(output, dict(status='STOPPED_OPTIONAL_CONSTRUCTION_SWEEP_PARTIAL_ONLY',
        reason='Both-parity external witnesses were found, frozen, captured once and distinguish the final fixed tie rule. The remaining optional mining was stopped with a normal SIGINT; no files were removed.',
        observed_tool_session=77084, observed_terminal_exit_code=130,
        counts=counts, first_recorded_target_index=first, exclusive_recorded_end=expected_start,
        last_recorded_block=last_block, last_block_candidate_and_target_replay_passed=True,
        all_recorded_endpoint_witnesses_in_D0063=True,
        planned_full_domain_complete=False, report_json_intentionally_absent=True,
        files_sha256={name: digest(scan / name) for name in ('STARTED.json', 'blocks.tsv', 'targets.tsv')},
        authenticated_witness_prefix_sha256=digest(prefix),
        source_sha256=digest(Path(__file__)), hardware_executed=False,
        limits='Preserved partial software evidence only. No completion of the planned highest-binade sweep or any all-input hardware theorem is claimed.'))
    print('PASS preserved stopped partial sweep', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
