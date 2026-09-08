#!/usr/bin/env python3
"""Independent exact-rational endpoint and raw-state verification of H1662.

Does not import H1660/H1659 completion or H1663/H1657 parsers. Unknown physical
semantics are not closed by agreement; all frozen failures remain failures.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from h1640_remaining_scope_freshness import save

KIT='transfer-tests/h1662/'
SCORE='tmp/ledger33/current/h1663_score_normalization_c0/'
LOCKS={KIT+'FREEZE.json':'544ab1fb1a62b4d0a9d496077dd829f18ee8cfdff69f7b1bb51fc93828c94a53',
       KIT+'manifest.json':'90ddbdf8ec19f3be57307d061a5812e57734f25b22dc08d66303427a90264e45',
       'experiments/h1663_score_normalization_c0.py':'8effa5634c585bb6b3f73493da9ede511fed9b44e669da61c8148bd14f095441'}


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def scaled_raw80(se,sig):
    # Decode the original raw subnormal into an exact rational, multiply by
    # the documented bias factor, and independently encode the exact normal.
    value=Fraction(sig,1<<16445)*(1<<24576)
    assert value.denominator==1 and value>0
    n=value.numerator; exponent=n.bit_length()-1
    q,remainder=divmod(n,1<<(exponent-63))
    assert remainder==0 and 1<<63<=q<1<<64
    return f'{(se&0x8000)|(exponent+16383):04x}:{q:016x}'


def predict(row,scaled):
    se,sig=(int(w,16) for w in row['operand'].split())
    top=(8-row['depth'])%8; tag=((1<<row['depth'])-1)<<(8-row['depth'])
    sf=0
    if row['empty']:
        tag &= ~(1<<top); sf=0x40
    assert row['flags']==row['pending']==0
    if row['probe']=='invalid_C0':
        assert not row['masks']&1
        if row['empty']:
            cls='empty_stack'
        elif (se&0x7fff) and not sig>>63:
            cls='unsupported'
        else:
            assert se&0x7fff==0x7fff and sig>>63 and not sig&(1<<62)
            cls='signaling_nan'
        output=row['operand'].replace(' ',':'); flags=1
    else:
        assert row['probe']=='normalization' and se&0x7fff==0 and 0<sig<1<<63 and not row['empty']
        assert row['masks']&2 and not row['masks']&16
        cls='denormal'
        if row['instruction']=='fsin':
            output=scaled[(se,sig)]; flags=0x32
        else:
            assert row['instruction']=='fcos'
            output='3fff:8000000000000000'; flags=0x22
    pending=bool(flags & ~row['masks'] & 63)
    sw=(top<<11)|(row['cc']&0x4100)|sf|flags|(0x8080 if pending else 0)
    return dict(encoding_class=cls,output=output,response='MF_AFTER' if pending else 'OK',
        delivery='at_next_wait' if pending else 'none',new_exception_flags=flags,C1=0,C2=0,
        status_bits=sw,status_known_mask=65535,physical_abridged_tag=tag,top=top)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    freeze=json.loads((root/KIT/'FREEZE.json').read_text())
    for name,sha in freeze['sha256']['evidence'].items(): assert digest(root/name)==sha,name
    opened=json.loads((root/KIT/'OPENED.json').read_text())
    assert opened['capture_state']=='OPENED_ONCE' and opened['freeze_sha256']==LOCKS[KIT+'FREEZE.json']
    assert digest(root/SCORE/'report.json')==opened['report_sha256']
    report=json.loads((root/SCORE/'report.json').read_text())
    assert digest(root/SCORE/'score.json')==report['sha256']['score']
    raw_path=root/KIT/'hardware-output/state-output.txt'
    assert digest(raw_path)==report['sha256']['raw_output']
    previous={r['case_id']:r for r in json.loads((root/SCORE/'score.json').read_text())}
    rows=json.loads((root/KIT/'manifest.json').read_text()); lines=raw_path.read_text().splitlines()
    assert len(rows)==len(lines)==freeze['unique_capture_tuples']==53664
    scaled={}
    for row in rows:
        if row['probe']=='normalization':
            se,sig=(int(w,16) for w in row['operand'].split())
            if (se,sig) not in scaled: scaled[(se,sig)]=scaled_raw80(se,sig)
    counts=Counter(); failures=Counter(); misses=[]; recomputed=[]
    state_fields=('cw','sw','top','ftw',*(f'r{i}' for i in range(8)),'fop','fip','fdp')
    for row,line in zip(rows,lines):
        words=line.lower().split(); assert len(words)==60 and all(w.count('=')==1 for w in words)
        fields=dict(w.split('=') for w in words); assert len(fields)==60
        assert fields['case']==row['case_id'].lower()
        expected=predict(row,scaled); assert expected==row['expected'],row['case_id']
        top=(8-row['depth'])%8; tag=((1<<row['depth'])-1)<<(8-row['depth'])
        if row['empty']: tag &= ~(1<<top)
        cw=0x40|row['masks']|{24:0,53:0x200,64:0x300}[row['pc']]|{'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}[row['mode']]
        before=dict(insn=row['instruction'],mode=row['mode'],pc=f'pc{row["pc"]}',masks=f'{row["masks"]:02x}',
            depth=str(row['depth']),cc=f'{row["cc"]:04x}',flags='00',pending='0',empty=str(row['empty']),
            b_cw=f'{cw:04x}',b_sw=f'{(top<<11)|row["cc"]:04x}',b_ftw=f'{tag:02x}',
            b_top=str(top),b_r0=row['operand'].replace(' ',':'))
        for i in range(1,row['depth']): before[f'b_r{i}']=f'3fff:{(1<<63)+8*i:016x}'
        valid,fault,site,trap=(int(fields[k]) for k in ('a_valid','fault','fault_at','trap'))
        assert (valid,fault,site) in ((1,0,0),(1,1,2),(0,1,1))
        selected='a' if valid else 'f'
        want=(1,1,2,16) if expected['delivery']=='at_next_wait' else (1,0,0,0)
        exact=dict(before=all(fields[k]==v for k,v in before.items()),delivery=(valid,fault,site,trap)==want,
            output=fields[selected+'_r0']==expected['output'],status=int(fields[selected+'_sw'],16)==expected['status_bits'],
            CW=int(fields[selected+'_cw'],16)==cw,TOP=int(fields[selected+'_top'])==top,
            FTW=int(fields[selected+'_ftw'],16)==expected['physical_abridged_tag'],
            deeper=all(fields[selected+f'_r{i}']==fields[f'b_r{i}'] for i in range(1,8)))
        if fault:
            reference='b' if site==1 else 'a'
            exact['fault_snapshot_relation']=all(fields['f_'+k]==fields[reference+'_'+k] for k in state_fields)
        assert exact==previous[row['case_id']]['exact'],row['case_id']
        bad=[k for k,v in exact.items() if not v]
        if bad: misses.append(row['case_id']); failures.update(bad)
        counts['independent_raw_output_full_SW_rows']+=1
        if row['probe']=='normalization' and row['instruction']=='fsin': counts['exact_rational_underflow_rows']+=1
        if row['probe']=='invalid_C0' and not row['cc']&0x100: counts['invalid_initial_C0_zero_rows']+=1
        recomputed.append(dict(case_id=row['case_id'],expected=expected,exact=exact,
            actual_output=fields[selected+'_r0'],actual_SW=int(fields[selected+'_sw'],16),actual_delivery_site=site))
    assert len(misses)==report['miss_rows']
    out.mkdir(parents=True); save(out/'recomputed.json',recomputed)
    result=dict(experiment='h1664_independent_normalization_c0',
        status='INDEPENDENT_FALSIFICATION_CONFIRMED' if misses else 'PASS_INDEPENDENT_FROZEN_COMPLETION',
        counts=dict(counts),unique_rational_scaled_operands=len(scaled),miss_rows=len(misses),failures=dict(failures),
        hardware_execution='none',private_ledger_access='none',production_or_paper_change='none',
        claim_boundary='Independent raw parser, exact Fraction scaling/encoding and stage algebra. Finite accepted-input validation, not evidence for rejected shifts or all-input silicon equality.',
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS,score_report=digest(root/SCORE/'report.json'),
            raw_output=digest(raw_path),recomputed=digest(out/'recomputed.json')))
    save(out/'report.json',result)
    print(json.dumps({k:result[k] for k in ('status','counts','miss_rows','failures')},sort_keys=True),flush=True)


if __name__=='__main__': main()
