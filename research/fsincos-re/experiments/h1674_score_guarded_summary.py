#!/usr/bin/env python3
"""62-field guarded capture scoring: BEFORE_ONLY never earns execution credit."""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
import h1669_score_summary_state as base
from h1640_remaining_scope_freshness import save

digest=base.digest
BASE_SHA='7e2bd40c5bc4277f964d332af3cddafe426951c28db08635fc84ca4713b86993'
STATE=base.STATE


def allowed(raw):
    sw,cw=int(raw['B_SW'],16),int(raw['B_CW'],16)
    return bool(sw&~cw&63) or not sw&0x8080


def parse(line):
    pairs=[word.split('=') for word in line.split()]
    assert len(pairs)==62 and all(len(p)==2 for p in pairs)
    raw={k:v.lower() for k,v in pairs}; assert len(raw)==62 and raw['ATTEMPTED'] in ('0','1')
    core={k:v for k,v in raw.items() if k!='ATTEMPTED'}
    if raw['ATTEMPTED']=='0':
        assert all(raw[k]=='0' for k in ('A_VALID','FAULT','FAULT_AT','SI_CODE','TRAP'))
        # Validate only common field formats using the older parser. This
        # temporary flag is never returned or scored as an executed snapshot.
        core['A_VALID']='1'
    base.parse(base.encode(core))
    return raw


def before_errors(row,raw):
    top=(row['requested_SW']>>11)&7
    want=dict(CASE=row['case_id'].lower(),INSN=row['instruction'],MODE=row['mode'],PC=f'pc{row["pc"]}',
        MASKS=f'{row["masks"]:02x}',DEPTH=str(row['depth']),CC=f'{row["cc"]:04x}',FLAGS=f'{row["flags"]:02x}',
        SUMMARY=f'{row["summary"]:04x}',REQ_SW=f'{row["requested_SW"]:04x}',EMPTY=str(row['empty']),
        B_CW=f'{row["before_CW"]:04x}',B_FTW=f'{row["before_FTW"]:02x}',B_TOP=str(top),B_R0=row['operand'].replace(' ',':'))
    for i in range(1,row['depth']): want[f'B_R{i}']=f'3fff:{(1<<63)+8*i:016x}'
    errors=[k for k,v in want.items() if raw[k]!=v]
    if (int(raw['B_SW'],16)^row['requested_SW'])&0x7f7f: errors.append('B_SW_non_summary')
    return errors


def inspect(row,raw):
    attempted=int(raw['ATTEMPTED']); sw=int(raw['B_SW'],16); requested=row['requested_SW']
    if attempted:
        result=base.inspect(row,{k:v for k,v in raw.items() if k!='ATTEMPTED'})
        result['exact']['guard']=allowed(raw)
        result['execution_observed']=True
    else:
        u=int(bool(sw&~int(raw['B_CW'],16)&63)); e=(sw>>7)&1; b=(sw>>15)&1
        reqe=(requested>>7)&1; reqb=(requested>>15)&1
        restore={k:(sw&0x8080)==v for k,v in dict(identity=requested&0x8080,
            B_from_ES=0x8080*reqe,both_from_U=0x8080*u,ES_from_U=(u<<7)|(reqb<<15)).items()}
        errors=before_errors(row,raw)
        empty=all(raw[p+'_'+k]==('0000:0000000000000000' if k.startswith('R') else
                  '0'*(16 if k in ('FIP','FDP') else 2 if k=='FTW' else 1 if k=='TOP' else 4))
                  for p in ('A','F') for k in STATE)
        result=dict(case_id=row['case_id'],kind=row['kind'],profile=row['profile'],
            exact=dict(before=not errors,guard=not allowed(raw),unattempted_snapshots_empty=empty),before_errors=errors,
            restoration_hypotheses=restore,pending_hypotheses={},primary_requested_fault_exact=None,
            requested_U_ES_B=f'{u}{reqe}{reqb}',actual_U_ES_B=f'{u}{e}{b}',opcode_fault=None,
            delivery_site=None,selected_snapshot='B',actual_output=None,actual_SW=None,
            actual_before_SW=sw,status_difference=None,execution_observed=False)
        assert 'output' not in result['exact'] and 'status' not in result['exact']
    result['attempted']=attempted
    result['identity_attempt_prediction_exact']=bool(attempted)==row['identity_predicted_attempted']
    return result


def synthetic(row,summary=None,at=None):
    summary=row['summary'] if summary is None else summary
    attempt=bool(row['flags']&~row['masks']&63) or not summary
    raw=base.synthetic(row,summary,at if attempt else 0); raw['ATTEMPTED']=str(int(attempt))
    if not attempt:
        for key in ('A_VALID','FAULT','FAULT_AT','SI_CODE','TRAP'): raw[key]='0'
        for p in ('A','F'):
            for k in STATE:
                width=16 if k in ('FIP','FDP') else 2 if k=='FTW' else 1 if k=='TOP' else 4
                raw[p+'_'+k]='0000:0000000000000000' if k.startswith('R') else '0'*width
    return raw


def preflight(rows):
    counts=Counter()
    for row in rows:
        raw=parse(base.encode(synthetic(row))); result=inspect(row,raw)
        assert all(result['exact'].values()) and result['restoration_hypotheses']['identity']
        assert result['identity_attempt_prediction_exact']; counts['synthetic_positive_rows']+=1
        changed=dict(raw); changed['B_R0']='ffff:ffffffffffffffff'
        assert not inspect(row,changed)['exact']['before']; counts['before_mutations_detected']+=1
        if result['attempted']:
            selected=result['selected_snapshot']; changed=dict(raw); changed[selected+'_R0']='ffff:ffffffffffffffff'
            assert not inspect(row,changed)['exact']['output']; counts['output_mutations_detected']+=1
            changed=dict(raw); changed[selected+'_SW']=f'{int(raw[selected+"_SW"],16)^0x100:04x}'
            assert not inspect(row,changed)['exact']['status']; counts['C0_mutations_detected']+=1
        else:
            assert result['pending_hypotheses']=={} and result['actual_output'] is None
            counts['skipped_execution_not_credited']+=1
            changed=dict(raw); changed['A_R0']='ffff:ffffffffffffffff'
            assert not inspect(row,changed)['exact']['unattempted_snapshots_empty']; counts['skipped_snapshot_mutations_detected']+=1
        if row['pc']==24 and row['mode']=='rn':
            for summary in (0,0x80,0x8000,0x8080):
                trial=synthetic(row,summary)
                for at in ((0,1,2) if trial['ATTEMPTED']=='1' else (None,)):
                    varied=parse(base.encode(synthetic(row,summary,at))); got=inspect(row,varied)
                    assert all(got['exact'].values()); counts['restoration_delivery_guard_combinations']+=1
                    if got['attempted'] and at!=1:
                        varied['A_SW']=f'{int(varied["A_SW"],16)^0x8080:04x}'
                        if at==2: varied['F_SW']=varied['A_SW']
                        assert all(inspect(row,varied)['exact'].values()); counts['unknown_post_summary_not_credited']+=1
    for bad in ('',base.encode(synthetic(rows[0]))+' ATTEMPTED=1',base.encode(base.synthetic(rows[0]))):
        try: parse(bad)
        except (AssertionError,KeyError): counts['malformed_rejected']+=1
        else: raise AssertionError('malformed accepted')
    return dict(counts)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--preflight-bank',type=Path)
    p.add_argument('--kit',type=Path); p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mark-opened',action='store_true'); a=p.parse_args(); out=a.output_dir.resolve()
    assert not out.exists() and digest(Path(base.__file__))==BASE_SHA
    if a.preflight_bank:
        rows=json.loads(a.preflight_bank.read_text())['predictions']; counts=preflight(rows); out.mkdir(parents=True)
        save(out/'report.json',dict(experiment='h1674_guarded_preflight',counts=counts,hardware_execution='none',
            sha256=dict(script=digest(Path(__file__)),base=BASE_SHA,bank=digest(a.preflight_bank))))
        print(json.dumps(counts,sort_keys=True),flush=True); return
    kit=a.kit.resolve(); freeze=json.loads((kit/'FREEZE.json').read_text())
    assert freeze['experiment']=='h1675_guarded_summary' and freeze['capture_state']=='FROZEN_UNOPENED'
    assert freeze['sha256']['scorer']==digest(Path(__file__)) and not (kit/'HOLD.json').exists()
    checked=set()
    for line in (kit/'CHECKSUMS.sha256').read_text().splitlines():
        sha,name=line.split(None,1); path=Path(name)
        assert not path.is_absolute() and '..' not in path.parts and name not in checked
        assert digest(kit/path)==sha; checked.add(name)
    assert checked=={'FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'}
    rows=json.loads((kit/'manifest.json').read_text()); assert len(rows)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in rows})
    output=kit/'hardware-output'; assert (output/'complete-utc.txt').is_file()
    assert (kit/'inputs.txt').read_text().splitlines()==[r['capture_line'] for r in rows]
    assert (output/'binary.sha256').read_text().split()[0]==freeze['hardware_target']['capture_binary_sha256']
    sha,name=(output/'outputs.sha256').read_text().strip().split(None,1)
    assert name=='hardware-output/state-output.txt' and digest(output/'state-output.txt')==sha
    lines=(output/'state-output.txt').read_text().splitlines(); assert len(lines)==len(rows)==freeze['unique_capture_tuples']
    counts=Counter(); restores=Counter(); pending=Counter(); categories=Counter(); truth=defaultdict(Counter)
    scored=[]; misses=[]; pc=defaultdict(list)
    for row,line in zip(rows,lines):
        raw=parse(line); result=inspect(row,raw); scored.append(result)
        if not all(result['exact'].values()): misses.append(result)
        counts['rows']+=1; counts['attempted_rows' if result['attempted'] else 'before_only_rows']+=1
        for k,v in result['exact'].items(): counts[k+'_checks']+=1; counts[k+'_exact']+=int(v)
        for k,v in result['restoration_hypotheses'].items(): restores[k]+=int(not v)
        counts['identity_attempt_prediction_misses']+=int(not result['identity_attempt_prediction_exact'])
        if result['attempted']:
            for k,v in result['pending_hypotheses'].items(): pending[k]+=int(not v)
            counts['primary_requested_fault_misses']+=int(not result['primary_requested_fault_exact'])
            truth[result['actual_U_ES_B']][str(result['opcode_fault'])]+=1
        categories[result['requested_U_ES_B']+'->'+result['actual_U_ES_B']]+=1
        pc[(row['operand'],row['instruction'],row['mode'])].append((result['actual_before_SW'],result['attempted'],result['actual_output'],result['actual_SW'],result['delivery_site']))
    assert all(len(v)==3 for v in pc.values()); out.mkdir(parents=True)
    save(out/'score.json',scored); save(out/'misses.json',misses)
    report=dict(experiment='h1674_guarded_summary_score',capture_state='OPENED_ONCE',conditional_miss_rows=len(misses),
        counts=dict(counts),restoration_hypothesis_misses=dict(restores),pending_hypothesis_misses=dict(pending),
        requested_to_actual_U_ES_B=dict(categories),actual_pending_truth={k:dict(v) for k,v in truth.items()},
        PC_groups=len(pc),PC_differences=sum(len(set(v))!=1 for v in pc.values()),
        claim_boundary='Frozen conditional checks and separate restoration/pending hypotheses. BEFORE_ONLY earns no execution, endpoint, status-transition or pending-gate credit. No all-input closure or default promotion.',
        sha256=dict(scorer=digest(Path(__file__)),base=BASE_SHA,freeze=digest(kit/'FREEZE.json'),manifest=digest(kit/'manifest.json'),
            raw_output=sha,score=digest(out/'score.json'),misses=digest(out/'misses.json')))
    save(out/'report.json',report)
    if a.mark_opened:
        save(kit/'OPENED.json',dict(experiment=freeze['experiment'],capture_state='OPENED_ONCE',retries=0,
            freeze_sha256=report['sha256']['freeze'],report_sha256=digest(out/'report.json'),conditional_miss_rows=len(misses),
            counts=dict(counts),candidate_changed=False,paper_change='none'))
    print(json.dumps({k:report[k] for k in ('conditional_miss_rows','counts','restoration_hypothesis_misses','pending_hypothesis_misses','requested_to_actual_U_ES_B','actual_pending_truth','PC_differences')},sort_keys=True),flush=True)


if __name__=='__main__': main()
