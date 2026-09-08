#!/usr/bin/env python3
"""Score immutable H1662 normalization/C0 predictions using pinned raw helpers."""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import h1657_score_exception_state as raw
from h1640_remaining_scope_freshness import save

HELPER_SHA='40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mark-opened',action='store_true')
    a=p.parse_args(); kit,out=a.kit.resolve(),a.output_dir.resolve()
    assert not out.exists() and not (a.mark_opened and (kit/'OPENED.json').exists())
    digest=raw.digest
    assert digest(Path(raw.__file__))==HELPER_SHA
    freeze=json.loads((kit/'FREEZE.json').read_text())
    assert freeze['experiment']=='h1662_normalization_c0' and freeze['capture_state']=='FROZEN_UNOPENED'
    assert freeze['sha256']['scorer']==digest(Path(__file__))
    names=set()
    for line in (kit/'CHECKSUMS.sha256').read_text().splitlines():
        sha,name=line.split(None,1); path=Path(name.strip())
        assert not path.is_absolute() and '..' not in path.parts and str(path) not in names
        assert digest(kit/path)==sha; names.add(str(path))
    assert names=={'FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'}
    rows=json.loads((kit/'manifest.json').read_text())
    assert len(rows)==freeze['unique_capture_tuples']
    assert len(rows)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in rows})
    assert (kit/'inputs.txt').read_text().splitlines()==[r['capture_line'] for r in rows]
    output=kit/'hardware-output'
    assert (output/'complete-utc.txt').is_file()
    assert (output/'binary.sha256').read_text().split()[0]==freeze['hardware_target']['capture_binary_sha256']
    sha,name=(output/'outputs.sha256').read_text().strip().split(None,1)
    assert name=='hardware-output/state-output.txt' and digest(output/'state-output.txt')==sha
    cpu=(output/'cpu-summary.txt').read_text()
    assert re.search(r'vendor_id\s*:\s*GenuineIntel',cpu) and re.search(r'^model\s*:\s*85\s*$',cpu,re.M)
    lines=(output/'state-output.txt').read_text().splitlines(); assert len(lines)==len(rows)
    counts=Counter(); probes=defaultdict(Counter); shifts=defaultdict(Counter); c0=defaultdict(Counter)
    scored=[]; misses=[]; pc_groups=defaultdict(list)
    for row,line in zip(rows,lines):
        fields=raw.parse(line); r=raw.inspect(row,fields)
        assert row['expected']['output'] is not None and row['expected']['status_known_mask']==0xffff
        r.update(probe=row['probe'],normalization_shift=row['normalization_shift'],shape=row['shape'])
        scored.append(r)
        if not all(r['exact'].values()): misses.append(r)
        measures=dict(rows=1)
        for k,v in r['exact'].items(): measures[k+'_checks']=1; measures[k+'_exact']=int(v)
        counts.update(measures); probes[row['probe']].update(measures)
        selected=r['selected_snapshot']; sw=int(fields[selected+'_SW'],16)
        if row['probe']=='normalization':
            shifts[str(row['normalization_shift'])+'/'+row['instruction']].update(measures)
        else:
            initial=(row['before_SW']>>8)&1; observed=(sw>>8)&1
            group=row['kind']+'/'+row['instruction']+f'/initial{initial}'
            c0[group].update(rows=1,preserve=int(observed==initial),set=int(observed==1),clear=int(observed==0))
        pc_groups[(row['operand'],row['instruction'],row['mode'])].append(
            (fields[selected+'_R0'],fields[selected+'_SW'],fields[selected+'_FTW'],fields['FAULT_AT']))
    assert all(len(v)==3 for v in pc_groups.values())
    out.mkdir(parents=True); save(out/'score.json',scored); save(out/'misses.json',misses)
    report=dict(experiment='h1663_score_normalization_c0',capture_state='OPENED_ONCE',retries=0,
        verdict='FROZEN_COMPLETION_SURVIVES' if not misses else 'FROZEN_COMPLETION_FALSIFIED',
        counts=dict(counts),miss_rows=len(misses),probe_counts={k:dict(v) for k,v in probes.items()},
        normalization_shift_counts={k:dict(v) for k,v in shifts.items()},
        invalid_C0_discriminators={k:dict(v) for k,v in c0.items()},
        PC_groups=len(pc_groups),PC_differences=sum(len(set(v))!=1 for v in pc_groups.values()),
        claim_boundary='Finite prospective output/full-SW and fault-state checks of the unchanged frozen candidate. Rejected proposal shifts do not gain hardware credit. No all-input silicon proof or promotion.',
        sha256=dict(freeze=digest(kit/'FREEZE.json'),manifest=digest(kit/'manifest.json'),scorer=digest(Path(__file__)),
            raw_helper=HELPER_SHA,raw_output=sha,score=digest(out/'score.json'),misses=digest(out/'misses.json'),
            raw_metadata={p.name:digest(p) for p in output.iterdir() if p.is_file() and p.name!='state-output.txt'}))
    save(out/'report.json',report)
    if a.mark_opened:
        save(kit/'OPENED.json',dict(experiment=freeze['experiment'],capture_state='OPENED_ONCE',retries=0,
            verdict=report['verdict'],counts=dict(counts),miss_rows=len(misses),
            report_sha256=digest(out/'report.json'),freeze_sha256=report['sha256']['freeze'],candidate_changed=False,paper_change='none'))
    print(json.dumps({k:report[k] for k in ('verdict','counts','miss_rows','PC_differences','probe_counts')},sort_keys=True),flush=True)


if __name__=='__main__': main()
