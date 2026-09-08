"""Authenticate D0022 misses and audit lower/upper exact midpoint controls.

Forcing a neighboring table index is causal localization, not a selector.
Both possibilities are compared for every exact midpoint in all saved jobs.
No hardware repeats, model promotion or edits to frozen predictions occur.
"""
import collections
from dataclasses import replace
import gzip
import hashlib
import itertools
import json
from d0008_schedule_replay import BASE, digest, opened
from d0010_causal_intervals import restore
from graph_v3 import prevalue as reduced
from graph_v5 import PROGRAM
from graph_v6 import kernel, prevalue
from model import F, encode, value
from prepare import save
from protocol import validate_output


def alternatives(raw):
    ys, ym, xs, xm = raw
    if not ym or not xm or (ys & 32767) == 32767 or (xs & 32767) == 32767 or not ym >> 63 or not xm >> 63:
        return None
    if abs((ys & 32767) - (xs & 32767)) > 6:
        return None
    y, x = abs(value(ys, ym)), abs(value(xs, xm))
    ratio = min(y, x) / max(y, x)
    index = ratio * 32
    if index < F(3, 2) or index.denominator != 2:
        return None
    values = []
    for n in (int(index), int(index) + 1):
        trace = {}
        reduced(*raw, replace(PROGRAM, forced_index=n), trace=trace)
        values.append(restore(kernel(trace['z'], True), trace, raw))
    # At 3/64 the lower rounded index is 1. The public Goldmont-shaped
    # branch tests index < 2 and would use its direct polynomial instead.
    # Record this separate possibility, without silently equating table 1
    # with direct evaluation or claiming the tie rule is already recovered.
    direct = None
    if int(index) == 1:
        trace = {}
        reduced(*raw, replace(PROGRAM, forced_index=0), trace=trace)
        direct = restore(kernel(trace['z'], False), trace, raw)
    return ratio, int(index), values, direct


def agrees(v, row):
    q = encode(v, row['rc'])
    return (*q, int(abs(value(*q)) > abs(v))) == (row['se'], row['sig'], row['C1'])


def main():
    counts = collections.Counter()
    cases, witnesses, sources = [], [], []
    failures = [json.loads(line) for line in gzip.open(BASE / 'd0022/candidate-misses.jsonl.gz', 'rt')]
    failed_pairs = {tuple(int(s, 16) for s in item['input'].split()[3:]) for item in failures}
    frontier = collections.defaultdict(list)
    for job in [f'd{i:04d}' for i in range(1, 10)] + ['d0013', 'd0022']:
        root = BASE / job
        compressed = (root / 'inputs.txt.gz').exists()
        inp, hw = root / ('inputs.txt.gz' if compressed else 'inputs.txt'), root / ('hardware.txt.gz' if compressed else 'hardware.txt')
        manifest = json.loads((root / 'MANIFEST.json').read_text())
        receipt = json.loads((root / 'COMPLETE.json').read_text())
        assert digest(root / 'MANIFEST.json') == receipt['manifest_sha256']
        assert digest(inp) == manifest['files'][inp.name]
        sha, count = hashlib.sha256(), 0
        last, cached = None, None
        with opened(inp) as inputs, opened(hw) as hardware:
            for line, out in itertools.zip_longest(inputs, hardware):
                assert line is not None and out is not None
                sha.update(out.encode()); count += 1
                tokens = line.split()
                raw = tuple(int(v, 16) for v in tokens[3:])
                if raw != last:
                    last, cached = raw, alternatives(raw)
                if cached is None:
                    continue
                observed = validate_output(out, line)
                row = dict(input=line.strip(), rc=tokens[1], se=observed['se'], sig=observed['sig'], C1=observed['C1'])
                ratio, lower_index, values, direct = cached
                match = [agrees(v, row) for v in values]
                state = ('lower' if match == [True, False] else 'upper' if match == [False, True]
                         else 'both' if all(match) else 'neither')
                counts[job + ':' + state] += 1
                record = dict(job=job, row=row, ratio=str(ratio), lower_index=lower_index,
                              lower_prevalue=str(values[0]), upper_prevalue=str(values[1]),
                              outcome=state, direct_prevalue=str(direct) if direct is not None else None,
                              direct_matches=agrees(direct, row) if direct is not None else None)
                cases.append(record)
                if state != 'both':
                    witnesses.append(record)
                if job == 'd0022' and raw in failed_pairs:
                    frontier[raw].append(row)
        assert count == receipt['rows'] and sha.hexdigest() == receipt['hardware_sha256']
        sources.append(dict(job=job, rows=count, hardware_sha256=sha.hexdigest()))
    assert set(frontier) == failed_pairs
    localized = []
    for raw, rows in frontier.items():
        trace = {}
        prevalue(*raw, trace=trace)
        ratio, index, choices, direct = alternatives(raw)
        localized.append(dict(raw=raw, rows=rows, ratio=str(ratio), kind=trace['kind'], baseline_index=trace['n'],
                              lower_index=index, lower_matches_all_modes=all(agrees(choices[0], row) for row in rows)))
    save(BASE / 'd0022-midpoint-localization.json', dict(status='CAUSAL_MIDPOINT_LOCALIZATION_NOT_A_TIE_RULE_PROOF',
         sources=sources, authenticated_rows=sum(s['rows'] for s in sources),
         counts=dict(counts), midpoint_observations=cases, decisive_observations=witnesses,
         failing_observations=len(failures), failing_raw_pairs=len(failed_pairs), new_frontier=localized,
         pending='Fresh exact-midpoint discriminators must distinguish lower-cell, parity and quotient-construction hypotheses.',
         hardware_executed=False, numerical_model_promoted=False))
    print('PASS', sum(s['rows'] for s in sources), 'authenticated rows;', len(failures), 'affected observations;',
          len(failed_pairs), 'raw pairs;', len(witnesses), 'decisive midpoint observations', flush=True)
    print(dict(counts), flush=True)


if __name__ == '__main__':
    main()
