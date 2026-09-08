#!/usr/bin/env python3
"""Pinned 61-field ES/B parser, conditional scorer and synthetic preflight."""
import argparse
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
import h1657_score_exception_state as legacy
from h1666_summary_observability import gates
from h1640_remaining_scope_freshness import save

digest=legacy.digest
STATE=legacy.STATE_FIELDS
HELPER_SHA='40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808'


def parse(line):
    words=line.split(); pairs=[w.split('=') for w in words]
    assert len(pairs)==61 and all(len(p)==2 for p in pairs)
    fields={k:v.lower() for k,v in pairs}; assert len(fields)==61
    assert 'PENDING' not in fields
    for key in ('SUMMARY','REQ_SW'): assert re.fullmatch('[0-9a-f]{4}',fields[key])
    assert not int(fields['SUMMARY'],16)&~0x8080
    adapted={k:v for k,v in fields.items() if k not in ('SUMMARY','REQ_SW')}
    adapted['PENDING']='0'
    old=legacy.parse(' '.join(f'{k}={v}' for k,v in adapted.items()))
    assert all(fields[k]==v for k,v in old.items() if k!='PENDING')
    return fields


def inspect(row,raw):
    sw=int(raw['B_SW'],16); requested=row['requested_SW']; top=(requested>>11)&7
    metadata=dict(CASE=row['case_id'].lower(),INSN=row['instruction'],MODE=row['mode'],PC=f'pc{row["pc"]}',
        MASKS=f'{row["masks"]:02x}',DEPTH=str(row['depth']),CC=f'{row["cc"]:04x}',FLAGS=f'{row["flags"]:02x}',
        SUMMARY=f'{row["summary"]:04x}',REQ_SW=f'{requested:04x}',EMPTY=str(row['empty']),
        B_CW=f'{row["before_CW"]:04x}',B_FTW=f'{row["before_FTW"]:02x}',B_TOP=str(top),B_R0=row['operand'].replace(' ',':'))
    for i in range(1,row['depth']): metadata[f'B_R{i}']=f'3fff:{(1<<63)+8*i:016x}'
    before_errors=[k for k,v in metadata.items() if raw[k]!=v]
    if (sw^requested)&0x7f7f: before_errors.append('B_SW_non_summary')
    valid,fault,at,trap=(int(raw[k]) for k in ('A_VALID','FAULT','FAULT_AT','TRAP'))
    selected='A' if valid else 'F'; observed_sw=int(raw[selected+'_SW'],16)
    expected=row['conditional_executed']
    exact=dict(before=not before_errors,trap=trap==(16 if fault else 0),
        CW=raw[selected+'_CW']==raw['B_CW'],TOP=int(raw[selected+'_TOP'])==top,
        deeper=all(raw[selected+f'_R{i}']==raw[f'B_R{i}'] for i in range(1,8)))
    if at==1:
        exact['skipped_state']=all(raw['F_'+k]==raw['B_'+k] for k in STATE)
        exact['output']=raw['F_R0']==raw['B_R0']
        exact['status']=observed_sw==sw
        exact['FTW']=raw['F_FTW']==raw['B_FTW']
    else:
        exact['output']=raw['A_R0']==expected['output']
        exact['status']=not ((observed_sw^expected['status_bits'])&expected['status_known_mask'])
        exact['FTW']=int(raw['A_FTW'],16)==expected['physical_abridged_tag']
    if fault:
        ref='B' if at==1 else 'A'
        exact['fault_snapshot_relation']=all(raw['F_'+k]==raw[ref+'_'+k] for k in STATE)
    u=int(bool(sw&~int(raw['B_CW'],16)&63)); e=(sw>>7)&1; b=(sw>>15)&1
    requested_e=(requested>>7)&1; requested_b=(requested>>15)&1
    restore_predictions=dict(identity=requested&0x8080,B_from_ES=0x8080*requested_e,
        both_from_U=0x8080*u,ES_from_U=(u<<7)|(requested_b<<15))
    restore={k:v==sw&0x8080 for k,v in restore_predictions.items()}
    pending={k:v==int(at==1) for k,v in gates(u,e,b).items()}
    return dict(case_id=row['case_id'],kind=row['kind'],profile=row['profile'],exact=exact,
        before_errors=before_errors,restoration_hypotheses=restore,pending_hypotheses=pending,
        primary_requested_fault_exact=bool(row['predicted_opcode_fault'])==(at==1),
        requested_U_ES_B=f'{u}{requested_e}{requested_b}',actual_U_ES_B=f'{u}{e}{b}',
        opcode_fault=int(at==1),delivery_site=at,selected_snapshot=selected,
        actual_output=raw[selected+'_R0'],actual_SW=observed_sw,actual_before_SW=sw,
        status_difference=(observed_sw^(sw if at==1 else expected['status_bits']))&(0xffff if at==1 else 0x7f7f))


def synthetic(row,summary=None,at=None):
    summary=row['summary'] if summary is None else summary
    sw=(row['requested_SW']&0x7f7f)|summary
    if at is None: at=int(bool(summary&0x80))
    valid=int(at!=1); fault=int(at!=0)
    fields=dict(CASE=row['case_id'].lower(),INSN=row['instruction'],MODE=row['mode'],PC=f'pc{row["pc"]}',
        MASKS=f'{row["masks"]:02x}',DEPTH=str(row['depth']),CC=f'{row["cc"]:04x}',FLAGS=f'{row["flags"]:02x}',
        SUMMARY=f'{row["summary"]:04x}',REQ_SW=f'{row["requested_SW"]:04x}',EMPTY=str(row['empty']),
        A_VALID=str(valid),FAULT=str(fault),FAULT_AT=str(at),SI_CODE='0',TRAP=str(16 if fault else 0))
    for prefix in ('B','A','F'):
        for name in STATE:
            width=16 if name in ('FIP','FDP') else 2 if name=='FTW' else 1 if name=='TOP' else 4
            fields[prefix+'_'+name]='0000:0000000000000000' if name.startswith('R') else '0'*width
    fields.update(B_CW=f'{row["before_CW"]:04x}',B_SW=f'{sw:04x}',B_TOP=str((sw>>11)&7),
        B_FTW=f'{row["before_FTW"]:02x}',B_R0=row['operand'].replace(' ',':'),B_FOP='0123',B_FIP='0000000000004567',B_FDP='00000000000089ab')
    for i in range(1,row['depth']): fields[f'B_R{i}']=f'3fff:{(1<<63)+8*i:016x}'
    if valid:
        for name in STATE: fields['A_'+name]=fields['B_'+name]
        x=row['conditional_executed']
        fields.update(A_SW=f'{x["status_bits"]|(0x8080 if fault else 0):04x}',A_R0=x['output'],A_FTW=f'{x["physical_abridged_tag"]:02x}')
    if fault:
        ref='B' if at==1 else 'A'
        for name in STATE: fields['F_'+name]=fields[ref+'_'+name]
    return fields


def encode(fields): return ' '.join(f'{k}={v}' for k,v in fields.items())


def preflight(rows):
    counts=Counter()
    for row in rows:
        fields=parse(encode(synthetic(row))); result=inspect(row,fields)
        assert all(result['exact'].values()) and result['restoration_hypotheses']['identity'] and result['pending_hypotheses']['ES']
        counts['synthetic_positive_rows']+=1
        selected=result['selected_snapshot']
        changed=dict(fields); changed[selected+'_R0']='ffff:ffffffffffffffff'
        assert not inspect(row,changed)['exact']['output']; counts['output_mutations_detected']+=1
        changed=dict(fields); changed[selected+'_SW']=f'{int(fields[selected+"_SW"],16)^0x100:04x}'
        assert not inspect(row,changed)['exact']['status']; counts['C0_mutations_detected']+=1
        if row['pc']==24 and row['mode']=='rn':
            for summary in (0,0x80,0x8000,0x8080):
                for at in (0,1,2):
                    varied=parse(encode(synthetic(row,summary,at))); result=inspect(row,varied)
                    assert all(result['exact'].values()); counts['independent_restore_delivery_combinations']+=1
                    if at!=1:
                        varied['A_SW']=f'{int(varied["A_SW"],16)^0x8080:04x}'
                        if at==2: varied['F_SW']=varied['A_SW']
                        assert all(inspect(row,varied)['exact'].values()); counts['unknown_summary_not_credited']+=1
    for bad in ('', 'CASE=x', encode(synthetic(rows[0]))+' REQ_SW=0000'):
        try: parse(bad)
        except (AssertionError,KeyError): counts['malformed_rejected']+=1
        else: raise AssertionError('malformed row accepted')
    return dict(counts)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--preflight-bank',type=Path)
    p.add_argument('--kit',type=Path); p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mark-opened',action='store_true'); a=p.parse_args(); out=a.output_dir.resolve()
    assert not out.exists() and digest(Path(legacy.__file__))==HELPER_SHA
    if a.preflight_bank:
        rows=json.loads(a.preflight_bank.read_text())['predictions']; counts=preflight(rows)
        out.mkdir(parents=True); report=dict(experiment='h1669_synthetic_preflight',counts=counts,hardware_execution='none',
            sha256=dict(script=digest(Path(__file__)),bank=digest(a.preflight_bank),legacy_parser=HELPER_SHA))
        save(out/'report.json',report); print(json.dumps(counts,sort_keys=True),flush=True); return
    kit=a.kit.resolve(); freeze=json.loads((kit/'FREEZE.json').read_text())
    assert freeze['capture_state']=='FROZEN_UNOPENED' and freeze['sha256']['scorer']==digest(Path(__file__))
    for line in (kit/'CHECKSUMS.sha256').read_text().splitlines():
        sha,name=line.split(None,1); path=Path(name)
        assert not path.is_absolute() and '..' not in path.parts and digest(kit/path)==sha
    rows=json.loads((kit/'manifest.json').read_text()); output=kit/'hardware-output'
    assert (output/'complete-utc.txt').is_file()
    assert (output/'binary.sha256').read_text().split()[0]==freeze['hardware_target']['capture_binary_sha256']
    sha,name=(output/'outputs.sha256').read_text().strip().split(None,1)
    assert name=='hardware-output/state-output.txt' and digest(output/'state-output.txt')==sha
    assert (kit/'inputs.txt').read_text().splitlines()==[r['capture_line'] for r in rows]
    lines=(output/'state-output.txt').read_text().splitlines(); assert len(rows)==len(lines)==freeze['unique_capture_tuples']
    counts=Counter(); restored=Counter(); pending=Counter(); categories=Counter(); pc=defaultdict(list)
    actual=defaultdict(Counter); scored=[]; misses=[]
    for row,line in zip(rows,lines):
        fields=parse(line); result=inspect(row,fields); scored.append(result)
        if not all(result['exact'].values()): misses.append(result)
        counts['rows']+=1
        for k,v in result['exact'].items(): counts[k+'_checks']+=1; counts[k+'_exact']+=int(v)
        for k,v in result['restoration_hypotheses'].items(): restored[k]+=int(not v)
        for k,v in result['pending_hypotheses'].items(): pending[k]+=int(not v)
        counts['primary_requested_fault_misses']+=int(not result['primary_requested_fault_exact'])
        categories[result['requested_U_ES_B']+'->'+result['actual_U_ES_B']]+=1
        actual[result['actual_U_ES_B']][str(result['opcode_fault'])]+=1
        pc[(row['operand'],row['instruction'],row['mode'])].append((result['actual_before_SW'],result['actual_output'],result['actual_SW'],result['delivery_site']))
    assert all(len(v)==3 for v in pc.values())
    out.mkdir(parents=True); save(out/'score.json',scored); save(out/'misses.json',misses)
    report=dict(experiment='h1669_summary_state_score',capture_state='OPENED_ONCE',conditional_miss_rows=len(misses),
        counts=dict(counts),restoration_hypothesis_misses=dict(restored),pending_hypothesis_misses=dict(pending),
        requested_to_actual_U_ES_B=dict(categories),actual_pending_truth={k:dict(v) for k,v in actual.items()},
        PC_groups=len(pc),PC_differences=sum(len(set(v))!=1 for v in pc.values()),
        primary_hypotheses_survive=not restored['identity'] and not counts['primary_requested_fault_misses'],
        claim_boundary='Immutable prospective hypotheses, not fitted closure. Conditional checks are distinct from restoration/delivery predictions; unknown post-execution summary and delivery are not predicted successes.',
        sha256=dict(scorer=digest(Path(__file__)),freeze=digest(kit/'FREEZE.json'),manifest=digest(kit/'manifest.json'),raw_output=sha,
            score=digest(out/'score.json'),misses=digest(out/'misses.json')))
    save(out/'report.json',report)
    if a.mark_opened:
        save(kit/'OPENED.json',dict(capture_state='OPENED_ONCE',experiment=freeze['experiment'],retries=0,
            freeze_sha256=report['sha256']['freeze'],report_sha256=digest(out/'report.json'),conditional_miss_rows=len(misses),
            primary_hypotheses_survive=report['primary_hypotheses_survive'],candidate_changed=False,paper_change='none'))
    print(json.dumps({k:report[k] for k in ('conditional_miss_rows','counts','restoration_hypothesis_misses','pending_hypothesis_misses','requested_to_actual_U_ES_B','actual_pending_truth','PC_differences')},sort_keys=True),flush=True)


if __name__=='__main__': main()
