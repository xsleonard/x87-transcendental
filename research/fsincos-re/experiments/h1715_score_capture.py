#!/usr/bin/env python3
"""Score the frozen portable-harness experiment; never re-execute hardware."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite


def checks(row,fields):
    insn,mode,pc,op=row['instruction'],row['mode'],row['pc'],row['operand']
    # Protocol/control failures are not hidden among numerical passes.
    suite.validate_numeric(fields,insn,mode,pc,op,row['case_id'])
    expected=row['prediction'];c2=bool(int(fields['A_SW'],16)&0x400)
    result=dict(C2=c2==(expected['outputs'] is None))
    if expected['outputs'] is not None:
        if insn=='fsincos':
            result['sine']=fields['SIN']==expected['outputs'][0];result['cosine']=fields['COS']==expected['outputs'][1]
        else:result['sine' if insn=='fsin' else 'cosine']=fields['SIN' if insn=='fsin' else 'COS']==expected['outputs'][0]
        if expected['C1'] is not None:result['C1']=((int(fields['A_SW'],16)>>9)&1)==expected['C1']
    return result


def preflight(rows):
    counts=Counter()
    for row in rows:
        p=row['prediction'];paired=row['instruction']=='fsincos';c2=p['outputs'] is None
        sw=0x3c00 if c2 else (0x3000 if paired else 0x3800)|0x20|((p['C1'] or 0)<<9)
        f=dict(CASE=row['case_id'],INSN=row['instruction'],MODE=row['mode'],PC=f'pc{row["pc"]}',
            IN=row['operand'].replace(' ',':'),CW=f'{suite.expected_cw(row["mode"],row["pc"]):04x}',
            B_SW='3800',A_SW=f'{sw:04x}',SIN='-',COS='-',PRESERVED=row['operand'].replace(' ',':') if c2 else '-')
        if not c2:
            if row['instruction']!='fcos':f['SIN']=p['outputs'][0]
            if row['instruction']!='fsin':f['COS']=p['outputs'][-1]
        assert all(checks(row,suite.parse_numeric(' '.join(k+'='+v for k,v in f.items()))).values());counts['rows']+=1
        for key,check in (('SIN','sine'),('COS','cosine')):
            if key!='-' and check in checks(row,f):
                bad=dict(f);bad[key]='0000:0000000000000000';assert not checks(row,bad)[check];counts['mutations']+=1
        if 'C1' in checks(row,f):
            bad=dict(f);bad['A_SW']=f'{sw^0x200:04x}';assert not checks(row,bad)['C1'];counts['mutations']+=1
        for key,val in (('CASE','wrong'),('CW','0000'),('B_SW','0000')):
            bad=dict(f);bad[key]=val
            try:checks(row,bad)
            except ValueError:counts['mutations']+=1
            else:raise AssertionError('missed control mutation')
    return dict(counts)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();kit=a.kit.resolve();out=a.output_dir.resolve();assert not out.exists()
    freeze=json.loads((kit/'FREEZE.json').read_text());assert suite.digest(Path(__file__))==freeze['sha256']['scorer']
    assert suite.digest(Path(suite.__file__))==freeze['sha256']['suite']
    assert suite.digest(kit/'manifest.json')==freeze['sha256']['manifest']
    rows=json.loads((kit/'manifest.json').read_text());assert len(rows)==freeze['unique_capture_tuples']
    assert preflight(rows)==freeze['scorer_preflight']
    byjob={job:[r for r in rows if r['job']==job] for job in freeze['jobs']};counts=Counter();misses=[];paths=Counter();hashes={}
    for job,selected in byjob.items():
        run=kit/('run-'+job);done=json.loads((run/'COMPLETE.json').read_text())
        assert done['status']=='OPENED_ONCE_DO_NOT_RERUN' and done['rows']==len(selected)
        assert suite.digest(run/'outputs.txt')==done['outputs_sha256'];assert suite.digest(run/'inputs.txt')==freeze['jobs'][job]['inputs_sha256']
        assert suite.digest(run/'cpu.json')==done['cpu_sha256'];assert done['binary_sha256']==freeze['jobs'][job]['binary_sha256']
        with (run/'outputs.txt').open() as f:
            for row in selected:
                line=next(f);fields=suite.parse_numeric(line)
                try:result=checks(row,fields)
                except ValueError as error:result=dict(capture_contract=False);row=dict(row,contract_error=str(error))
                counts['instruction_rows']+=1;paths[row['instruction']+'.'+row['prediction']['path']]+=1
                for name,passed in result.items():counts[name+'_checks']+=1;counts[name+'_misses']+=not passed
                if not all(result.values()):misses.append(dict(row,checks=result,raw=line.strip()))
            assert not f.readline()
        hashes[job]=dict(complete=suite.digest(run/'COMPLETE.json'),raw=done['outputs_sha256'],cpu=done['cpu_sha256'])
    out.mkdir(parents=True);report=dict(experiment='h1715_compound_adversarial',status='PASS_FROZEN_ADVERSARIAL' if not misses else 'FROZEN_MODEL_FALSIFIED',
        counts=dict(counts),paths=dict(paths),miss_count=len(misses),unique_operands=freeze['unique_operands'],
        instruction_retries=0,hardware_execution='ONCE_PER_TUPLE',candidate_changed=False,paper_changed=False,
        capture_builds='x86_64 and i386 on disjoint fresh tuples, same reported Xeon CPUID; not an old-Pentium hardware validation',
        sha256=dict(freeze=suite.digest(kit/'FREEZE.json'),jobs=hashes,scorer=suite.digest(Path(__file__))))
    suite.save(out/'misses.json',misses);suite.save(out/'report.json',report)
    suite.save(kit/'OPENED.json',dict(status='OPENED_ONCE_DO_NOT_RERUN',instruction_retries=0,
        sha256=dict(freeze=suite.digest(kit/'FREEZE.json'),score=suite.digest(out/'report.json'),misses=suite.digest(out/'misses.json'))))
    print(json.dumps(report,sort_keys=True),flush=True)


if __name__=='__main__':main()
