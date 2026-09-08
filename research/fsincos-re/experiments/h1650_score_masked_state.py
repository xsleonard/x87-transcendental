#!/usr/bin/env python3
"""Score immutable H1649 state predictions and unknown-bit discriminators.

No hardware or adjustment of predictions. Unknown bits are descriptive
discriminators, not predicted passes. Every raw word and prestate is preserved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
from h1640_remaining_scope_freshness import save


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(line):
    fields={}
    for token in line.split():
        key,sep,value=token.partition('=')
        assert sep and key not in fields
        fields[key]=value.lower()
    required={'CASE','INSN','MODE','PC','MASKS','DEPTH','CC','FLAGS','EMPTY'}
    required|={prefix+'_'+name for prefix in ('A','B') for name in ('CW','SW','TOP','FTW',*(f'R{i}' for i in range(8)))}
    assert set(fields)==required
    for prefix in ('A','B'):
        for name in ('CW','SW'): assert re.fullmatch('[0-9a-f]{4}',fields[prefix+'_'+name])
        assert re.fullmatch('[0-9a-f]{2}',fields[prefix+'_FTW'])
        assert int(fields[prefix+'_TOP'])==((int(fields[prefix+'_SW'],16)>>11)&7)
        for i in range(8): assert re.fullmatch('[0-9a-f]{4}:[0-9a-f]{16}',fields[f'{prefix}_R{i}'])
    return fields


def before_errors(row,raw):
    expected={'CASE':row['case_id'].lower(),'INSN':row['instruction'],'MODE':row['mode'],'PC':f'pc{row["pc"]}',
        'MASKS':'3f','DEPTH':str(row['depth']),'CC':f'{row["cc"]:04x}','FLAGS':f'{row["flags"]:02x}',
        'EMPTY':str(row['empty']),'B_CW':f'{row["before_CW"]:04x}','B_SW':f'{row["before_SW"]:04x}',
        'B_FTW':f'{row["before_FTW"]:02x}','B_R0':row['operand'].replace(' ',':')}
    for i in range(1,row['depth']): expected[f'B_R{i}']=f'3fff:{(1<<63)+8*i:016x}'
    return [k for k,v in expected.items() if raw[k]!=v]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mark-opened',action='store_true')
    a=p.parse_args(); kit,out=a.kit.resolve(),a.output_dir.resolve()
    assert not out.exists() and not (a.mark_opened and (kit/'OPENED.json').exists())
    freeze=json.loads((kit/'FREEZE.json').read_text())
    assert freeze['experiment']=='h1649_masked_state' and freeze['capture_state']=='FROZEN_UNOPENED'
    assert freeze['sha256']['scorer']==digest(Path(__file__))
    checked=set()
    for line in (kit/'CHECKSUMS.sha256').read_text().splitlines():
        sha,name=line.split(None,1); path=Path(name.strip())
        assert not path.is_absolute() and '..' not in path.parts and str(path) not in checked
        assert digest(kit/path)==sha; checked.add(str(path))
    assert checked=={'FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'}
    rows=json.loads((kit/'manifest.json').read_text())
    assert len(rows)==freeze['unique_capture_tuples']==16128
    assert len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in rows})==len(rows)
    assert (kit/'inputs.txt').read_text().splitlines()==[r['capture_line'] for r in rows]
    path=kit/'hardware-output/state-output.txt'
    assert (kit/'hardware-output/complete-utc.txt').is_file()
    assert (kit/'hardware-output/binary.sha256').read_text().split()[0]==freeze['hardware_target']['capture_binary_sha256']
    output_hash,name=(kit/'hardware-output/outputs.sha256').read_text().strip().split(None,1)
    assert name.strip()=='hardware-output/state-output.txt' and digest(path)==output_hash
    cpu=(kit/'hardware-output/cpu-summary.txt').read_text()
    assert re.search(r'vendor_id\s*:\s*GenuineIntel',cpu) and re.search(r'^model\s*:\s*85\s*$',cpu,re.M)
    assert re.search(r'cpu family\s*:\s*6\s*$',cpu,re.M)
    lines=path.read_text().splitlines(); assert len(lines)==len(rows)
    counts=Counter(); cells=defaultdict(Counter); survivors={}; trials=Counter(); initial_values=defaultdict(set)
    scored=[]; misses=[]; paired={}; pc_groups=defaultdict(list)
    for row,line in zip(rows,lines):
        raw=parse(line); errors=before_errors(row,raw)
        expected=row['expected']; after=int(raw['A_SW'],16)
        exact=dict(before=not errors,output=raw['A_R0']==expected['output'],
            status=((after^expected['status_bits'])&expected['status_known_mask'])==0,
            CW=raw['A_CW']==raw['B_CW'],TOP=int(raw['A_TOP'])==expected['top'],
            FTW=int(raw['A_FTW'],16)==expected['physical_abridged_tag'],
            deeper=all(raw[f'A_R{i}']==raw[f'B_R{i}'] for i in range(1,8)))
        record=dict(case_id=row['case_id'],kind=row['kind'],operand=row['operand'],instruction=row['instruction'],
            mode=row['mode'],pc=row['pc'],profile=row['profile'],expected=expected,actual=raw,exact=exact,before_errors=errors,
            status_difference=(after^expected['status_bits'])&expected['status_known_mask'])
        scored.append(record)
        if not all(exact.values()): misses.append(record)
        counts['rows']+=1; cells[row['kind']]['rows']+=1
        for key,truth in exact.items(): counts[key+'_exact']+=truth; cells[row['kind']][key+'_exact']+=truth
        for bit,options in row['unmodeled_bit_alternatives'].items():
            key=row['kind']+'/'+row['instruction']+'/'+bit
            valid={k for k,v in options.items() if v==(after>>int(bit))&1}
            survivors[key]=survivors.get(key,set(options))&valid
            trials[key]+=1; initial_values[key].add((row['before_SW']>>int(bit))&1)
        if row['equivalence_pair']:
            key=(row['equivalence_pair'],row['instruction'],row['mode'],row['pc'])
            paired.setdefault(key,{})[row['kind']]=(row,raw)
        pc_groups[(row['operand'],row['instruction'],row['mode'])].append((raw['A_R0'],raw['A_SW'],raw['A_FTW']))
    pair_results=[]
    for key,pair in sorted(paired.items()):
        p,pr=pair['pseudo_denormal']; n,nr=pair['equivalent_normal']
        assert p['cc']==n['cc'] and p['flags']==n['flags'] and p['depth']==n['depth']
        flags_xor=(int(pr['A_SW'],16)^int(nr['A_SW'],16))&0x3f
        expected_xor=0 if p['flags']&2 else 2
        pair_results.append(dict(pair=list(key),equal_output=pr['A_R0']==nr['A_R0'],
            flags_xor=flags_xor,expected_flags_xor=expected_xor,flags_exact=flags_xor==expected_xor))
    assert len(pair_results)==1152 and all(len(v)==3 for v in pc_groups.values())
    output=kit/'hardware-output'
    out.mkdir(parents=True); save(out/'score.json',scored); save(out/'pairs.json',pair_results)
    result=dict(experiment='h1650_score_masked_state',capture_state='OPENED_ONCE',repeats=0,counts=dict(counts),
        cells={k:dict(v) for k,v in cells.items()},misses=misses,
        equal_value_pairs=dict(total=len(pair_results),outputs_equal=sum(p['equal_output'] for p in pair_results),
            flags_exact=sum(p['flags_exact'] for p in pair_results)),
        PC_groups=len(pc_groups),PC_differences=sum(len(set(v))!=1 for v in pc_groups.values()),
        unmodeled_bit_discriminators={k:dict(survivors=sorted(v),trials=trials[k],initial_values=sorted(initial_values[k])) for k,v in sorted(survivors.items())},
        verdict='FROZEN_STATE_MODEL_SURVIVES' if not misses else 'FROZEN_STATE_MODEL_FALSIFIED',
        claim_boundary='Finite prospective output/known-state test. Unknown-bit survivors are new observations, not previously validated laws; no full-state closure, unmasked claim, model adjustment or promotion.',
        sha256=dict(freeze=digest(kit/'FREEZE.json'),manifest=digest(kit/'manifest.json'),scorer=digest(Path(__file__)),
            raw_output=output_hash,score=digest(out/'score.json'),pairs=digest(out/'pairs.json'),
            raw_metadata={p.name:digest(p) for p in output.iterdir() if p.is_file() and p.name!='state-output.txt'}))
    save(out/'report.json',result)
    if a.mark_opened:
        save(kit/'OPENED.json',dict(experiment=freeze['experiment'],capture_state='OPENED_ONCE',repeats=0,
            verdict=result['verdict'],counts=dict(counts),report_sha256=digest(out/'report.json'),
            freeze_sha256=result['sha256']['freeze'],candidate_changed=False,paper_change='none'))
    print(json.dumps({k:result[k] for k in ('counts','verdict','equal_value_pairs','PC_differences')},sort_keys=True),flush=True)


if __name__=='__main__': main()
