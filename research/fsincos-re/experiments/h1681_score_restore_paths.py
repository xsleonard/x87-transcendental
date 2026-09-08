#!/usr/bin/env python3
"""Score frozen restoration hypotheses; never award transcendental/delivery credit."""
import argparse
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
from h1678_restore_paths_static import digest
from h1640_remaining_scope_freshness import save

HEAD='CASE METHOD ORDER MODE PC MASKS DEPTH CC FLAGS SUMMARY REQ_CW REQ_SW SCALAR_CW SCALAR_SW SAVED_CW SAVED_SW SAVED_TW'.split()
STATE=['CW','SW','TOP','FTW',*[f'R{i}' for i in range(8)],'FOP','FIP','FDP']
KEYS=set(HEAD)|{'FX_'+k for k in STATE}

def encode(raw): return ' '.join(k+'='+v for k,v in raw.items())
def parse(line):
    pairs=[word.split('=') for word in line.split()]
    assert len(pairs)==32 and all(len(p)==2 for p in pairs)
    raw={k:v.lower() for k,v in pairs}; assert set(raw)==KEYS and len(raw)==32
    for key in KEYS-{'CASE','METHOD','ORDER','MODE','PC','DEPTH','FX_TOP'}:
        pattern=r'[0-9a-f]{4}:[0-9a-f]{16}' if key.startswith('FX_R') else r'[0-9a-f]{16}' if key in ('FX_FIP','FX_FDP') else r'[0-9a-f]{2}' if key in ('MASKS','FLAGS','FX_FTW') else r'[0-9a-f]{4}'
        assert re.fullmatch(pattern,raw[key]),key
    assert raw['DEPTH'] in tuple(str(i) for i in range(1,9)) and raw['FX_TOP'] in tuple(str(i) for i in range(8))
    assert int(raw['FX_TOP'])==(int(raw['FX_SW'],16)>>11)&7
    return raw

def metadata(row):
    return dict(CASE=row['case_id'].lower(),METHOD=row['method'],ORDER=row['order'],MODE=row['mode'],PC=f'pc{row["pc"]}',
        MASKS=f'{row["masks"]:02x}',DEPTH=str(row['depth']),CC=f'{row["cc"]:04x}',FLAGS=f'{row["flags"]:02x}',
        SUMMARY=f'{row["summary"]:04x}',REQ_CW=f'{row["requested_CW"]:04x}',REQ_SW=f'{row["requested_SW"]:04x}')

def inspect(row,raw):
    want=row['prediction']; known=want['SW_known_mask']; fxsw=int(raw['FX_SW'],16); scsw=int(raw['SCALAR_SW'],16)
    fxcw=int(raw['FX_CW'],16); sccw=int(raw['SCALAR_CW'],16)
    exact=dict(metadata=all(raw[k]==v for k,v in metadata(row).items()),
        CW=fxcw==sccw==want['CW'],known_FX_status=not((fxsw^want['SW'])&known),
        known_scalar_status=not((scsw^want['SW'])&known),observer_known_agreement=not((fxsw^scsw)&known),
        FTW=int(raw['FX_FTW'],16)==want['FTW'],TOP=int(raw['FX_TOP'])==want['TOP'],operand=raw['FX_R0']==want['output'],
        occupied_deeper=all(raw[f'FX_R{i}']==f'3fff:{(1<<63)+8*i:016x}' for i in range(1,row['depth'])),
        saved_image=all(int(raw['SAVED_'+k],16)==v for k,v in want['saved'].items()))
    actual={}
    for name,sw,cw in (('FX',fxsw,fxcw),('scalar',scsw,sccw)):
        actual[name]=f'{int(bool(sw&~cw&63))}{int(bool(sw&128))}{int(bool(sw&32768))}'
    return dict(case_id=row['case_id'],method=row['method'],order=row['order'],exact=exact,
        actual_U_ES_B=actual,observer_full_SW_agreement=fxsw==scsw,actual_FX_CW=fxcw,actual_FX_SW=fxsw,
        actual_scalar_CW=sccw,actual_scalar_SW=scsw,transcendental_execution_credit=0,pending_delivery_credit=0)

def synthetic(row):
    want=row['prediction']; raw=metadata(row)
    raw.update(SCALAR_CW=f'{want["CW"]:04x}',SCALAR_SW=f'{want["SW"]:04x}')
    for k,v in want['saved'].items(): raw['SAVED_'+k]=f'{v:04x}'
    raw.update(FX_CW=f'{want["CW"]:04x}',FX_SW=f'{want["SW"]:04x}',FX_TOP=str(want['TOP']),FX_FTW=f'{want["FTW"]:02x}')
    for i in range(8):
        raw[f'FX_R{i}']=want['output'] if not i else f'3fff:{(1<<63)+8*i:016x}' if i<row['depth'] else '0000:0000000000000000'
    raw.update(FX_FOP='0000',FX_FIP='0000000000000000',FX_FDP='0000000000000000')
    return raw

def preflight(rows):
    counts=Counter()
    for row in rows:
        raw=parse(encode(synthetic(row))); assert all(inspect(row,raw)['exact'].values()); counts['positive']+=1
        for field,bit,check in (('FX_SW',128,'known_FX_status'),('SCALAR_SW',32768,'known_scalar_status'),('SAVED_SW',128,'saved_image')):
            changed=dict(raw); changed[field]=f'{int(raw[field],16)^bit:04x}'
            assert not inspect(row,changed)['exact'][check]; counts[field+'_mutations']+=1
        changed=dict(raw); changed['FX_R0']='ffff:ffffffffffffffff'
        assert not inspect(row,changed)['exact']['operand']; counts['operand_mutations']+=1
        if row['prediction']['SW_known_mask']!=65535:
            changed=dict(raw)
            for key in ('FX_SW','SCALAR_SW'): changed[key]=f'{int(raw[key],16)^0x4700:04x}'
            assert all(inspect(row,changed)['exact'].values()); counts['undefined_CC_not_credited']+=1
    for bad in ('',encode(synthetic(rows[0]))+' FX_SW=0000',encode(synthetic(rows[0])).replace('SCALAR_CW=','ABSENT=')):
        try: parse(bad)
        except (AssertionError,KeyError): counts['malformed_rejected']+=1
        else: raise AssertionError('malformed accepted')
    return dict(counts)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--preflight-bank',type=Path)
    p.add_argument('--kit',type=Path); p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mark-opened',action='store_true'); a=p.parse_args(); out=a.output_dir.resolve(); assert not out.exists()
    if a.preflight_bank:
        rows=json.loads(a.preflight_bank.read_text())['rows']; counts=preflight(rows); out.mkdir(parents=True)
        save(out/'report.json',dict(experiment='h1681_restore_preflight',counts=counts,hardware_execution='none',
            sha256=dict(script=digest(Path(__file__)),bank=digest(a.preflight_bank))))
        print(json.dumps(counts,sort_keys=True),flush=True); return
    kit=a.kit.resolve(); freeze=json.loads((kit/'FREEZE.json').read_text())
    assert freeze['experiment']=='h1680_restore_paths' and freeze['sha256']['scorer']==digest(Path(__file__))
    assert not (kit/'HOLD.json').exists(); checked=set()
    for line in (kit/'CHECKSUMS.sha256').read_text().splitlines():
        sha,name=line.split(None,1); path=Path(name)
        assert not path.is_absolute() and '..' not in path.parts and name not in checked
        assert digest(kit/path)==sha; checked.add(name)
    assert checked=={'FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'}
    rows=json.loads((kit/'manifest.json').read_text()); output=kit/'hardware-output'
    assert (output/'complete-utc.txt').is_file()
    assert (kit/'inputs.txt').read_text().splitlines()==[r['capture_line'] for r in rows]
    assert (output/'binary.sha256').read_text().split()[0]==freeze['hardware_target']['capture_binary_sha256']
    sha,name=(output/'outputs.sha256').read_text().strip().split(None,1)
    assert name=='hardware-output/state-output.txt' and digest(output/'state-output.txt')==sha
    lines=(output/'state-output.txt').read_text().splitlines(); assert len(lines)==len(rows)==freeze['unique_capture_tuples']
    counts=Counter(); methods=defaultdict(Counter); states=defaultdict(Counter); scored=[]; misses=[]
    for row,line in zip(rows,lines):
        result=inspect(row,parse(line)); scored.append(result); counts['rows']+=1
        if not all(result['exact'].values()): misses.append(result)
        for key,value in result['exact'].items():
            counts[key+'_checks']+=1; counts[key+'_misses']+=int(not value); methods[row['method']][key+'_misses']+=int(not value)
        for observer,state in result['actual_U_ES_B'].items(): states[row['method']+'/'+row['order']+'/'+observer][state]+=1
        counts['observer_full_SW_differences']+=int(not result['observer_full_SW_agreement'])
    out.mkdir(parents=True); save(out/'score.json',scored); save(out/'misses.json',misses)
    report=dict(experiment='h1681_restore_paths_score',capture_state='OPENED_ONCE',hypothesis_miss_rows=len(misses),
        counts=dict(counts),method_misses={k:dict(v) for k,v in methods.items()},actual_states={k:dict(v) for k,v in states.items()},
        transcendental_execution_credit=0,pending_delivery_credit=0,
        claim_boundary='Frozen restoration hypotheses only. Actual off-diagonal state, if any, is not a consumed FSIN/FCOS state or evidence for a pending-delivery selector. No all-input proof/default/paper promotion.',
        sha256=dict(scorer=digest(Path(__file__)),freeze=digest(kit/'FREEZE.json'),manifest=digest(kit/'manifest.json'),
            raw_output=sha,score=digest(out/'score.json'),misses=digest(out/'misses.json')))
    save(out/'report.json',report)
    if a.mark_opened: save(kit/'OPENED.json',dict(experiment=freeze['experiment'],capture_state='OPENED_ONCE',retries=0,
        report_sha256=digest(out/'report.json'),freeze_sha256=report['sha256']['freeze'],hypothesis_miss_rows=len(misses),
        transcendental_execution_credit=0,pending_delivery_credit=0))
    print(json.dumps({k:report[k] for k in ('hypothesis_miss_rows','counts','actual_states')},sort_keys=True),flush=True)
if __name__=='__main__': main()
