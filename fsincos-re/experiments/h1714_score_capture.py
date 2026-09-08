#!/usr/bin/env python3
"""Score frozen H1714 three-instruction numerical predictions, not new fits."""
import argparse
import json
from collections import Counter
from pathlib import Path
from h1709_paired_retained_census import digest, save
from h1712_score_paired_capture import parse


def cw(row):
    return 0x7f | {24:0,53:0x200,64:0x300}[row['pc']] | {'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}[row['mode']]


def inspect(row, fields):
    expected=row['prediction'];paired=row['instruction']=='fsincos';c2=expected['outputs'] is None
    before=dict(CASE=row['case_id'],INSN=row['instruction'],MODE=row['mode'],PC=f'pc{row["pc"]}',
        MASKS='3f',DEPTH='1',PRIOR='clear',B_CW=f'{cw(row):04x}',B_SW='3800',B_TOP='7',B_FTW='80',
        B_R0=row['operand'].replace(' ',':'))
    checks=dict(before=all(fields.get(k)==v for k,v in before.items()),CW=fields['A_CW']==f'{cw(row):04x}',
        C2=bool(int(fields['A_SW'],16)&0x400)==c2,
        stack_mapping=(fields['A_TOP'],fields['A_FTW'])==(('6','c0') if paired and not c2 else ('7','80')))
    if c2:checks['C2_operand_preserved']=fields['A_R0']==before['B_R0']
    else:
        if paired:
            checks['sine']=fields['A_R1']==expected['outputs'][0]
            checks['cosine']=fields['A_R0']==expected['outputs'][1]
        else:checks['sine' if row['instruction']=='fsin' else 'cosine']=fields['A_R0']==expected['outputs'][0]
        if expected['C1'] is not None:checks['C1']=((int(fields['A_SW'],16)>>9)&1)==expected['C1']
    return checks


def synthetic(row):
    pred=row['prediction'];paired=row['instruction']=='fsincos';c2=pred['outputs'] is None
    fields=dict(CASE=row['case_id'],INSN=row['instruction'],MODE=row['mode'],PC=f'pc{row["pc"]}',
        MASKS='3f',DEPTH='1',PRIOR='clear')
    for phase in ('B','A'):
        before=phase=='B';top=6 if not before and paired and not c2 else 7
        sw=0x3800 if before else (top<<11)|(0x400 if c2 else 0x20|((pred['C1'] or 0)<<9))
        fields.update({phase+'_CW':f'{cw(row):04x}',phase+'_SW':f'{sw:04x}',phase+'_TOP':str(top),
            phase+'_FTW':'c0' if top==6 else '80'})
        for i in range(8):fields[phase+f'_R{i}']='0000:0000000000000000'
    fields['B_R0']=row['operand'].replace(' ',':')
    fields['A_R0']=fields['B_R0'] if c2 else pred['outputs'][-1]
    if paired and not c2:fields['A_R1']=pred['outputs'][0]
    return fields


def preflight(rows):
    counts=Counter()
    for row in rows:
        fields=synthetic(row);assert all(inspect(row,parse(' '.join(k+'='+v for k,v in fields.items()))).values())
        counts['synthetic_rows']+=1
        mutations=[('CASE','wrong','before'),('A_CW','0000','CW'),('A_SW',f'{int(fields["A_SW"],16)^0x400:04x}','C2'),
            ('A_TOP','0','stack_mapping')]
        if row['prediction']['outputs'] is None:mutations.append(('A_R0','0000:0000000000000000','C2_operand_preserved'))
        else:
            if row['instruction']=='fsincos':mutations.extend([('A_R1','0000:0000000000000000','sine'),('A_R0','0000:0000000000000000','cosine')])
            else:mutations.append(('A_R0','0000:0000000000000000','sine' if row['instruction']=='fsin' else 'cosine'))
            if row['prediction']['C1'] is not None:mutations.append(('A_SW',f'{int(fields["A_SW"],16)^0x200:04x}','C1'))
        for key,value,check in mutations:
            altered=dict(fields);altered[key]=value;assert not inspect(row,altered)[check];counts['mutation_detections']+=1
    return dict(counts)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mark-opened',action='store_true')
    a=p.parse_args();kit=a.kit.resolve();out=a.output_dir.resolve();assert not out.exists()
    assert not a.mark_opened or not (kit/'OPENED.json').exists()
    freeze=json.loads((kit/'FREEZE.json').read_text());assert digest(Path(__file__))==freeze['sha256']['scorer']
    assert digest(Path(parse.__code__.co_filename))==freeze['sha256']['parser']
    for line in (kit/'CHECKSUMS.sha256').read_text().splitlines():
        sha,name=line.split();assert Path(name).name==name and digest(kit/name)==sha
    rows=json.loads((kit/'manifest.json').read_text());assert len(rows)==freeze['unique_capture_tuples']
    assert (kit/'inputs.txt').read_text().splitlines()==[r['capture_line'] for r in rows]
    assert preflight(rows)==freeze['scorer_preflight']
    hardware=kit/'hardware-output';assert (hardware/'complete-utc.txt').is_file()
    assert (hardware/'binary.sha256').read_text().split()[0]==freeze['capture_binary_sha256']
    sha,name=(hardware/'outputs.sha256').read_text().split();assert name=='hardware-output/state-output.txt' and digest(kit/name)==sha
    lines=(kit/name).read_text().splitlines();assert len(lines)==len(rows)
    counts={insn:Counter() for insn in ('fsin','fcos','fsincos')};misses=[];paths=Counter();kinds=Counter()
    for row,line in zip(rows,lines):
        checks=inspect(row,parse(line));local=counts[row['instruction']];local['rows']+=1
        paths[row['instruction']+'.'+row['prediction']['path']]+=1
        for k in row['kinds']:kinds[k]+=1
        for key,good in checks.items():local[key+'_checks']+=1;local[key+'_misses']+=not good
        if not all(checks.values()):misses.append(dict(row,checks=checks,raw=line))
    out.mkdir(parents=True);report=dict(experiment='h1714_score_capture',
        status='PASS_FROZEN_ADVERSARIAL' if not misses else 'FROZEN_MODEL_FALSIFIED',
        counts={k:dict(v) for k,v in counts.items()},miss_count=len(misses),paths=dict(paths),kinds=dict(kinds),
        unique_operands=freeze['unique_operands'],unique_capture_tuples=len(rows),hardware_execution='ONCE',instruction_retries=0,
        candidate_changed=False,paper_changed=False,
        claim_boundary='Fresh directed rounding-boundary and exact-reduction-lattice numerical/C1 tests, not exhaustive input or hidden-circuit proof.',
        sha256=dict(freeze=digest(kit/'FREEZE.json'),manifest=digest(kit/'manifest.json'),raw=sha,script=digest(Path(__file__))))
    save(out/'misses.json',misses);save(out/'report.json',report)
    if a.mark_opened:save(kit/'OPENED.json',dict(status='OPENED_ONCE_DO_NOT_RERUN',instruction_retries=0,
        frozen_predictions_unchanged=True,sha256=dict(freeze=digest(kit/'FREEZE.json'),raw=sha,
        score=digest(out/'report.json'),misses=digest(out/'misses.json'))))
    print(json.dumps(report,sort_keys=True),flush=True)


if __name__=='__main__':main()
