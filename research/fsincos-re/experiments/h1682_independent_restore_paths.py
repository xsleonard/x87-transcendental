#!/usr/bin/env python3
"""Independent setup algebra and raw observer checks; no primary-model imports."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from h1640_remaining_scope_freshness import save

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def expectation(row):
    cw=64+row['masks']+{'rn':0,'rd':1024,'ru':2048,'rz':3072}[row['mode']]+{24:0,53:512,64:768}[row['pc']]
    flags=row['flags']; top=(8-row['depth'])%8; requested=(top<<11)+row['cc']+flags+row['summary']
    assert (cw,requested)==(row['requested_CW'],row['requested_SW'])
    final_cw=cw-(cw%64)+63 if row['method']=='fnstenv' else cw
    pending=any((flags>>bit)&1 and not (final_cw>>bit)&1 for bit in range(6))
    before_pending=any((flags>>bit)&1 and not (cw>>bit)&1 for bit in range(6))
    final_sw=(top<<11)+row['cc']+flags+int(pending)*32896
    saved=dict(CW=cw,SW=(top<<11)+row['cc']+flags+int(before_pending)*32896,
        TW=sum(3<<(2*i) for i in range(top))) if row['method']=='fnstenv' else dict(CW=0,SW=0,TW=0)
    return dict(CW=final_cw,SW=final_sw,SW_known_mask=47359 if row['method'] in ('fldcw','fnstenv') else 65535,
        FTW=sum(1<<i for i in range(top,8)),TOP=top,output=row['operand'].replace(' ',':'),saved=saved)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--bank',type=Path); p.add_argument('--kit',type=Path)
    p.add_argument('--primary',type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); out=a.output_dir.resolve(); assert not out.exists()
    source=a.bank if a.bank else a.kit/'manifest.json'; bank=json.loads(source.read_text()); rows=bank['rows'] if a.bank else bank
    primary=lines=None; recomputed=[]; counts=Counter()
    if a.kit:
        freeze=json.loads((a.kit/'FREEZE.json').read_text()); report=json.loads((a.primary/'report.json').read_text())
        assert digest(Path(__file__))==freeze['sha256']['independent']
        assert digest(source)==freeze['sha256']['manifest'] and digest(a.kit/'FREEZE.json')==report['sha256']['freeze']
        assert digest(a.primary/'score.json')==report['sha256']['score']
        raw=a.kit/'hardware-output/state-output.txt'; assert digest(raw)==report['sha256']['raw_output']
        primary=json.loads((a.primary/'score.json').read_text()); lines=raw.read_text().splitlines()
        assert len(primary)==len(rows)==len(lines)
    for index,row in enumerate(rows):
        want=expectation(row); assert want==row['prediction']; counts['independent_predictions']+=1
        if lines is None: continue
        words=lines[index].lower().split(); assert len(words)==32 and all(w.count('=')==1 for w in words)
        f=dict(w.split('=') for w in words); assert len(f)==32
        keys=set('case method order mode pc masks depth cc flags summary req_cw req_sw scalar_cw scalar_sw saved_cw saved_sw saved_tw'.split())
        keys|={'fx_'+k for k in ('cw','sw','top','ftw',*[f'r{i}' for i in range(8)],'fop','fip','fdp')}
        assert set(f)==keys
        metadata=dict(case=row['case_id'].lower(),method=row['method'],order=row['order'],mode=row['mode'],pc='pc'+str(row['pc']),
            masks=format(row['masks'],'02x'),depth=str(row['depth']),cc=format(row['cc'],'04x'),flags=format(row['flags'],'02x'),
            summary=format(row['summary'],'04x'),req_cw=format(row['requested_CW'],'04x'),req_sw=format(row['requested_SW'],'04x'))
        fxsw,scsw,fxcw,sccw=[int(f[k],16) for k in ('fx_sw','scalar_sw','fx_cw','scalar_cw')]
        known=want['SW_known_mask']
        exact=dict(metadata=all(f[k]==v for k,v in metadata.items()),CW=fxcw==sccw==want['CW'],
            known_FX_status=(fxsw&known)==(want['SW']&known),known_scalar_status=(scsw&known)==(want['SW']&known),
            observer_known_agreement=(fxsw&known)==(scsw&known),FTW=int(f['fx_ftw'],16)==want['FTW'],
            TOP=int(f['fx_top'])==want['TOP'],operand=f['fx_r0']==want['output'],
            occupied_deeper=all(f['fx_r'+str(i)]=='3fff:'+format(2**63+8*i,'016x') for i in range(1,row['depth'])),
            saved_image=all(int(f['saved_'+k.lower()],16)==v for k,v in want['saved'].items()))
        old=primary[index]; assert old['case_id']==row['case_id'] and old['exact']==exact
        assert old['transcendental_execution_credit']==old['pending_delivery_credit']==0
        for label,cw,sw in (('FX',fxcw,fxsw),('scalar',sccw,scsw)):
            state=''.join(str(int(x)) for x in (any((sw>>i)&1 and not (cw>>i)&1 for i in range(6)),bool(sw&128),bool(sw&32768)))
            assert old['actual_U_ES_B'][label]==state
        counts['independent_raw_rows']+=1; counts['hypothesis_miss_rows']+=int(not all(exact.values()))
        recomputed.append(dict(case_id=row['case_id'],exact=exact))
    out.mkdir(parents=True); save(out/'recomputed.json',recomputed)
    result=dict(experiment='h1682_independent_restore_paths',counts=dict(counts),
        status='INDEPENDENT_RECOMPUTATION_AGREES',hardware_execution='none',new_labels_opened=bool(a.kit),
        claim_boundary='Independent verification of frozen algebra and raw scoring, not automatic validation of hypotheses or a general silicon solution.',
        sha256=dict(script=digest(Path(__file__)),source=digest(source),recomputed=digest(out/'recomputed.json')))
    save(out/'report.json',result); print(json.dumps(counts,sort_keys=True),flush=True)
if __name__=='__main__': main()
