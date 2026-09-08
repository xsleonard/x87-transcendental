#!/usr/bin/env python3
"""Independent conditional arithmetic/state algebra and 62-field raw checks.

No H1673/H1674/H1660/H1652 imports. Inconsistent-state conditional hypotheses
may fail; retain all failures without changing the frozen bank or arithmetic.
"""
import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
import h1637_tiny_closed_form_audit as tiny
import h1636_retained_rz_pc_transfer as rational
from h1640_remaining_scope_freshness import save


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def executed(row):
    se,sig=(int(w,16) for w in row['operand'].split()); ef=se&32767
    raw=row['operand'].replace(' ',':'); top=(-row['depth'])%8; tag=row['before_FTW']; c1=c2=0
    if row['empty']: cls='empty_stack'
    elif ef and not sig&(1<<63): cls='unsupported'
    elif ef==32767: cls='quiet_nan' if sig&(1<<62) else 'signaling_nan'
    elif ef==0: cls='pseudo_denormal' if sig&(1<<63) else 'denormal'
    else: cls='normal_out_of_range' if ef>=0x403e else 'normal_in_range'
    sf=0x40 if cls=='empty_stack' else 0
    if cls in ('empty_stack','unsupported','signaling_nan') and not row['masks']&1:
        output,flags=raw,1
    elif cls in ('denormal','pseudo_denormal') and not row['masks']&2:
        output,flags=raw,2
    elif cls in ('empty_stack','unsupported'):
        output,flags='ffff:c000000000000000',1; tag |= 1<<top
    elif cls in ('quiet_nan','signaling_nan'):
        output=f'{se:04x}:{sig|(1<<62):016x}'; flags=int(cls=='signaling_nan')
    elif cls in ('denormal','pseudo_denormal'):
        flags=0x22|(0x10 if cls=='denormal' and row['instruction']=='fsin' else 0)
        if row['instruction']=='fcos': output='3fff:8000000000000000'
        elif cls=='pseudo_denormal': output=f'{(se&32768)|1:04x}:{sig:016x}'
        elif row['masks']&16: output=raw
        else:
            value=Fraction(sig,1<<16445)*(1<<24576); assert value.denominator==1
            exponent=value.numerator.bit_length()-1; word,rem=divmod(value.numerator,1<<(exponent-63))
            assert rem==0 and 1<<63<=word<1<<64
            output=f'{(se&32768)|(exponent+16383):04x}:{word:016x}'
    elif cls=='normal_out_of_range': output,flags,c2=raw,0,1
    else:
        flags=0x20; small=tiny.evaluate(row['operand'],row['instruction'],row['mode'])
        if small['output'] is not None: output,c1=small['output'],small['C1']
        else:
            output,c1,_,_=rational.verify_hit(row['operand'],row['instruction'],row['mode'],row['numerical']['metadata'])
    status=(top<<11)|(row['cc']&0x4100)|(c1<<9)|(c2<<10)|row['flags']|sf|flags
    return dict(encoding_class=cls,output=output,new_exception_flags=flags,C1=c1,C2=c2,
        status_bits=status,status_known_mask=0x7f7f,physical_abridged_tag=tag,top=top)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--bank',type=Path); p.add_argument('--kit',type=Path); p.add_argument('--primary',type=Path)
    p.add_argument('--output-dir',required=True,type=Path); a=p.parse_args()
    root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists(); rational.initialize_proof(root)
    source=a.bank if a.bank else a.kit/'manifest.json'; value=json.loads(source.read_text())
    rows=value['predictions'] if a.bank else value
    if a.bank:
        for name,sha in value['sha256']['evidence'].items(): assert digest(root/name)==sha,name
    else:
        freeze=json.loads((a.kit/'FREEZE.json').read_text())
        for name,sha in freeze['sha256']['evidence'].items(): assert digest(root/name)==sha,name
        assert digest(source)==freeze['sha256']['manifest']
    counts=Counter(); predictions={}; primary=None; lines=None; failures=[]; recomputed=[]
    if a.kit:
        report=json.loads((a.primary/'report.json').read_text())
        assert digest(a.primary/'score.json')==report['sha256']['score']
        raw_path=a.kit/'hardware-output/state-output.txt'; assert digest(raw_path)==report['sha256']['raw_output']
        primary=json.loads((a.primary/'score.json').read_text()); lines=raw_path.read_text().splitlines()
        assert len(rows)==len(primary)==len(lines)
    for index,row in enumerate(rows):
        key=(row['operand'],row['instruction'],row['mode'])
        if key not in predictions: predictions[key]=executed(row)
        expected=predictions[key]
        for k,v in expected.items(): assert row['conditional_executed'][k]==v,(row['case_id'],k)
        counts['independent_frozen_conditional_checks']+=1
        if lines is None: continue
        words=lines[index].lower().split(); assert len(words)==62 and all(w.count('=')==1 for w in words)
        f=dict(w.split('=') for w in words); assert len(f)==62
        state=('cw','sw','top','ftw',*(f'r{i}' for i in range(8)),'fop','fip','fdp')
        required={'case','insn','mode','pc','masks','depth','cc','flags','summary','empty','req_sw',
                  'attempted','a_valid','fault','fault_at','si_code','trap'}|{p+'_'+k for p in ('a','b','f') for k in state}
        assert set(f)==required
        attempted=int(f['attempted']); assert attempted in (0,1)
        valid,fault,at,trap=(int(f[k]) for k in ('a_valid','fault','fault_at','trap'))
        assert (valid,fault,at) in (((1,0,0),(0,1,1),(1,1,2)) if attempted else ((0,0,0),))
        for prefix in ('a','b','f'): assert int(f[prefix+'_top'])==(int(f[prefix+'_sw'],16)>>11)&7
        top=(-row['depth'])%8; cw=0x40|row['masks']|{24:0,53:0x200,64:0x300}[row['pc']]|{'rn':0,'rd':1024,'ru':2048,'rz':3072}[row['mode']]
        requested=(top<<11)|row['cc']|row['flags']|row['summary']
        before=dict(case=row['case_id'].lower(),insn=row['instruction'],mode=row['mode'],pc=f'pc{row["pc"]}',
            masks=f'{row["masks"]:02x}',depth=str(row['depth']),cc=f'{row["cc"]:04x}',flags=f'{row["flags"]:02x}',
            summary=f'{row["summary"]:04x}',empty=str(row['empty']),req_sw=f'{requested:04x}',b_cw=f'{cw:04x}',
            b_top=str(top),b_ftw=f'{row["before_FTW"]:02x}',b_r0=row['operand'].replace(' ',':'))
        for i in range(1,row['depth']): before[f'b_r{i}']=f'3fff:{(1<<63)+8*i:016x}'
        selected='b' if not attempted else 'a' if valid else 'f'; sw=int(f['b_sw'],16); actual_sw=int(f[selected+'_sw'],16)
        exact=dict(before=all(f[k]==v for k,v in before.items()) and not ((sw^requested)&0x7f7f),
            trap=trap==(16 if fault else 0),CW=f[selected+'_cw']==f['b_cw'],TOP=int(f[selected+'_top'])==top,
            deeper=all(f[selected+f'_r{i}']==f[f'b_r{i}'] for i in range(1,8)))
        guard=bool(sw&~cw&63) or not sw&0x8080
        if not attempted:
            empty=all(f[p+'_'+k]==('0000:0000000000000000' if k.startswith('r') else
                '0'*(16 if k in ('fip','fdp') else 2 if k=='ftw' else 1 if k=='top' else 4))
                for p in ('a','f') for k in state)
            exact=dict(before=exact['before'],guard=not guard,unattempted_snapshots_empty=empty)
        elif at==1:
            exact.update(skipped_state=all(f['f_'+k]==f['b_'+k] for k in state),output=f['f_r0']==f['b_r0'],
                         status=actual_sw==sw,FTW=f['f_ftw']==f['b_ftw'])
        else:
            exact.update(output=f['a_r0']==expected['output'],status=not ((actual_sw^expected['status_bits'])&0x7f7f),
                         FTW=int(f['a_ftw'],16)==expected['physical_abridged_tag'])
        if attempted: exact['guard']=guard
        if fault:
            ref='b' if at==1 else 'a'; exact['fault_snapshot_relation']=all(f['f_'+k]==f[ref+'_'+k] for k in state)
        u=int(bool(sw&~cw&63)); e=(sw>>7)&1; b=(sw>>15)&1
        reqe=(requested>>7)&1; reqb=(requested>>15)&1
        restores=dict(identity=(sw&0x8080)==row['summary'],B_from_ES=(sw&0x8080)==reqe*0x8080,
                      both_from_U=(sw&0x8080)==u*0x8080,ES_from_U=(sw&0x8080)==((u<<7)|(reqb<<15)))
        pending={k:int(v)==int(at==1) for k,v in dict(ES=e,B=b,flags_and_masks=u,ES_or_B=e|b,ES_and_flags=e&u,ES_or_flags=e|u).items()}
        if not attempted: pending={}
        old=primary[index]; assert old['case_id']==row['case_id'] and exact==old['exact']
        assert restores==old['restoration_hypotheses'] and pending==old['pending_hypotheses']
        assert bool(row['summary']&128)==row['predicted_opcode_fault']
        assert old['primary_requested_fault_exact']==((bool(row['summary']&128)==(at==1)) if attempted else None)
        assert old['attempted']==attempted and old['execution_observed']==bool(attempted)
        assert old['identity_attempt_prediction_exact']==(bool(attempted)==row['identity_predicted_attempted'])
        if not attempted: assert old['actual_output'] is None and old['actual_SW'] is None and old['opcode_fault'] is None
        if not all(exact.values()): failures.append(dict(case_id=row['case_id'],exact=exact))
        recomputed.append(dict(case_id=row['case_id'],exact=exact,restoration=restores,pending=pending))
        counts['independent_raw_rows']+=1
        counts['independent_attempted_rows' if attempted else 'independent_before_only_rows']+=1
    out.mkdir(parents=True); save(out/'recomputed.json',recomputed)
    result=dict(experiment='h1677_independent_summary_state',status='INDEPENDENT_CONDITIONAL_MISSES' if failures else 'PASS_INDEPENDENT_CONDITIONAL_CHECKS',
        counts=dict(counts),distinct_arithmetic_points=len(predictions),conditional_miss_rows=len(failures),
        hardware_execution='none',private_ledger_access='none',default_or_paper_change='none',
        claim_boundary='Independent verification of frozen conditional algebra and raw scoring, not a claim that primary restoration/delivery hypotheses survive or that all-input silicon equality is proved.',
        sha256=dict(script=digest(Path(__file__)),source=digest(source),recomputed=digest(out/'recomputed.json')))
    save(out/'report.json',result); print(json.dumps({k:result[k] for k in ('status','counts','distinct_arithmetic_points','conditional_miss_rows')},sort_keys=True),flush=True)


if __name__=='__main__': main()
