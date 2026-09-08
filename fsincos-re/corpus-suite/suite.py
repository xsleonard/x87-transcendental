#!/usr/bin/env python3
"""Immutable x87 input suites and per-CPU observations (standard library only).

Inputs and model predictions are never treated as hardware observations.
Case IDs encode the complete numerical capture contract, independently of
the corpus version, input order, target CPU, executable or result value.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path

INSNS=('fsin','fcos','fsincos');MODES=('rn','rd','ru','rz');PCS=(24,53,64)
RAW=re.compile(r'[0-9a-f]{4}:[0-9a-f]{16}\Z')
CASE=re.compile(r'n1-(fsin|fcos|fsincos)-(rn|rd|ru|rz)-(24|53|64)-([0-9a-f]{4})([0-9a-f]{16})\Z')
FIELDS=('case_id','sin','cos','C2','C1','SW')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')


@contextmanager
def gzwrite(path):
    # mtime=0 and no embedded pathname make bytes reproducible.
    with Path(path).open('xb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding='ascii',newline='') as text:
                yield text


def case_id(insn,mode,pc,operand):
    se,sig=operand.lower().split()
    assert insn in INSNS and mode in MODES and pc in PCS and RAW.fullmatch(se+':'+sig)
    return f'n1-{insn}-{mode}-{pc}-{se}{sig}'


def decode_case(case):
    m=CASE.fullmatch(case)
    if not m:raise ValueError('invalid canonical case ID')
    insn,mode,pc,se,sig=m.groups()
    return insn,mode,int(pc),se+' '+sig


def capture_line(case):
    insn,mode,pc,op=decode_case(case)
    return f'{case} {insn} {mode} pc{pc} 3f 1 clear {op}'


def expected_cw(mode,pc):return 0x7f|{'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}[mode]|{24:0,53:0x200,64:0x300}[pc]


def parse_numeric(line):
    words=line.split();d=dict(w.split('=',1) for w in words)
    if len(words)!=len(d) or set(d)!=set('CASE INSN MODE PC IN CW B_SW A_SW SIN COS PRESERVED'.split()):
        raise ValueError('malformed numeric capture record')
    for key in ('IN','SIN','COS','PRESERVED'):
        if d[key]!='-' and not RAW.fullmatch(d[key]):raise ValueError('malformed raw80 field')
    for key in ('CW','B_SW','A_SW'):
        if not re.fullmatch('[0-9a-f]{4}',d[key]):raise ValueError('malformed control/status word')
    if d['INSN'] not in INSNS or d['MODE'] not in MODES or d['PC'] not in ('pc24','pc53','pc64'):
        raise ValueError('invalid instruction/control metadata')
    return d


def validate_numeric(fields,insn,mode,pc,op,external_id=None):
    expected=dict(INSN=insn,MODE=mode,PC=f'pc{pc}',IN=op.replace(' ',':'),CW=f'{expected_cw(mode,pc):04x}')
    if external_id is not None:expected['CASE']=external_id
    if any(fields[k]!=v for k,v in expected.items()):raise ValueError('capture input/control mapping mismatch')
    sw=int(fields['A_SW'],16);c2=bool(sw&0x400)
    if ((int(fields['B_SW'],16)>>11)&7)!=7:raise ValueError('unexpected initial TOP')
    if ((sw>>11)&7)!=(6 if insn=='fsincos' and not c2 else 7):raise ValueError('unexpected final TOP')
    if c2:
        if fields['SIN']!='-' or fields['COS']!='-' or fields['PRESERVED']!=op.replace(' ',':'):
            raise ValueError('C2 did not preserve the operand')
    else:
        if fields['PRESERVED']!='-':raise ValueError('unexpected preserved operand')
        for lane,needed in (('SIN',insn!='fcos'),('COS',insn!='fsin')):
            if (fields[lane]!='-')!=needed:raise ValueError('result lane mapping mismatch')
    return (case_id(insn,mode,pc,op),fields['SIN'],fields['COS'],int(c2),(sw>>9)&1,f'{sw:04x}')


def verify_dataset(directory):
    directory=Path(directory);manifest=json.loads((directory/'MANIFEST.json').read_text())
    for name,sha in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('unsafe manifest path')
        if digest(directory/name)!=sha:raise ValueError('dataset checksum mismatch: '+name)
    return manifest


def observations(directory):
    m=verify_dataset(directory)
    if m['kind']!='hardware_observations':raise ValueError('not hardware observations')
    previous=None;count=0
    with gzip.open(Path(directory)/'observations.tsv.gz','rt') as f:
        reader=csv.DictReader(f,delimiter='\t')
        if tuple(reader.fieldnames)!=FIELDS:raise ValueError('observation schema mismatch')
        for row in reader:
            decode_case(row['case_id'])
            if previous is not None and row['case_id']<=previous:raise ValueError('duplicate or unsorted observation IDs')
            previous=row['case_id'];count+=1;yield row
    if count!=m['rows']:raise ValueError('observation count mismatch')


def finish_observations(out,db,metadata,provenance):
    with gzwrite(out/'observations.tsv.gz') as f:
        writer=csv.writer(f,delimiter='\t',lineterminator='\n');writer.writerow(FIELDS)
        count=0
        for row in db.execute('SELECT case_id,sin,cos,c2,c1,sw FROM observations ORDER BY case_id'):
            writer.writerow(row);count+=1
    save(out/'cpu.json',metadata);save(out/'provenance.json',provenance)
    save(out/'MANIFEST.json',dict(schema='x87-suite-v1',kind='hardware_observations',rows=count,
        files={name:digest(out/name) for name in ('observations.tsv.gz','cpu.json','provenance.json')},
        limits='Numeric results and recorded status only. Undefined status bits, pointer registers and physical-CPU identity are not inferred.'))
    return count


def create_observation_db(out):
    db=sqlite3.connect(out/'index.sqlite')
    db.execute('CREATE TABLE observations(case_id TEXT PRIMARY KEY,sin TEXT,cos TEXT,c2 INTEGER,c1 INTEGER,sw TEXT) WITHOUT ROWID')
    return db


def import_state(kit,out):
    kit=Path(kit);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    freeze=json.loads((kit/'FREEZE.json').read_text());opened=json.loads((kit/'OPENED.json').read_text())
    if opened['status']!='OPENED_ONCE_DO_NOT_RERUN':raise ValueError('capture is not sealed OPENED_ONCE')
    if opened['sha256']['freeze']!=digest(kit/'FREEZE.json'):raise ValueError('freeze hash mismatch')
    rows=json.loads((kit/'manifest.json').read_text())
    if digest(kit/'manifest.json')!=freeze['sha256']['manifest']:raise ValueError('manifest hash mismatch')
    raw=kit/'hardware-output/state-output.txt'
    if digest(raw)!=opened['sha256']['raw']:raise ValueError('raw capture hash mismatch')
    db=create_observation_db(out);skip=0
    with raw.open() as stream:
        for row,line in zip(rows,stream):
            words=line.split();d=dict(w.split('=',1) for w in words)
            if len(d)!=31 or len(words)!=31:raise ValueError('state record malformed')
            # Do not silently merge arbitrary-state observations into the
            # numerical contract. Only the frozen depth1/clear/masked route.
            if (d['DEPTH'],d['PRIOR'],d['MASKS'])!=('1','clear','3f'):skip+=1;continue
            insn,mode,pc,op=row['instruction'],row['mode'],int(row['pc']),row['operand'];c2=bool(int(d['A_SW'],16)&0x400)
            numeric=dict(CASE=d['CASE'],INSN=d['INSN'],MODE=d['MODE'],PC=d['PC'],IN=d['B_R0'],CW=d['A_CW'],
                B_SW=d['B_SW'],A_SW=d['A_SW'],SIN='-' if c2 or insn=='fcos' else d['A_R1' if insn=='fsincos' else 'A_R0'],
                COS='-' if c2 or insn=='fsin' else d['A_R0'],PRESERVED=d['A_R0'] if c2 else '-')
            result=validate_numeric(numeric,insn,mode,pc,op,row['case_id'])
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)',result)
        if stream.readline():raise ValueError('excess raw records')
    if db.execute('SELECT count(*) FROM observations').fetchone()[0]+skip!=len(rows):raise ValueError('truncated capture')
    db.commit()
    text=(kit/'hardware-output/cpu-summary.txt').read_text();reported={}
    for line in text.splitlines():
        if ':' in line:k,v=line.split(':',1);reported[k.strip()]=v.strip()
    metadata=dict(identity_kind='historical_reported_FMS',reported=reported,raw_cpuid=None,
        limits='No raw CPUID dump was retained in this historical campaign; do not synthesize one from current host state.')
    count=finish_observations(out,db,metadata,dict(source='opened_architectural_capture',
        freeze_sha256=digest(kit/'FREEZE.json'),raw_sha256=digest(raw),opened_sha256=digest(kit/'OPENED.json'),
        skipped_non_numerical_contract_rows=skip,hardware_executions=0,observations_reused=True))
    db.close();return count


def import_numeric(run,out):
    run=Path(run);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    done=json.loads((run/'COMPLETE.json').read_text())
    if done['status']!='OPENED_ONCE_DO_NOT_RERUN':raise ValueError('capture is not sealed')
    if digest(run/'cpu.json')!=done['cpu_sha256']:raise ValueError('CPU metadata hash mismatch')
    if digest(run/'outputs.txt')!=done['outputs_sha256'] or digest(run/'inputs.txt')!=done['inputs_sha256']:
        raise ValueError('capture hash mismatch')
    db=create_observation_db(out);count=0
    with (run/'inputs.txt').open() as inputs,(run/'outputs.txt').open() as outputs:
        for line in inputs:
            words=line.split()
            if len(words)!=9 or words[4:7]!=['3f','1','clear']:raise ValueError('input contract mismatch')
            case,insn,mode,pc=words[:4];op=' '.join(words[7:])
            result=validate_numeric(parse_numeric(next(outputs)),insn,mode,int(pc[2:]),op,case)
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)',result);count+=1
        if outputs.readline():raise ValueError('excess output records')
    if count!=done['rows']:raise ValueError('capture row mismatch')
    db.commit();metadata=json.loads((run/'cpu.json').read_text())
    finish_observations(out,db,metadata,dict(source='numeric_capture_v1',complete_sha256=digest(run/'COMPLETE.json'),
        raw_sha256=digest(run/'outputs.txt'),input_sha256=digest(run/'inputs.txt'),hardware_executions=0,observations_reused=True))
    db.close();return count


def export(corpus,out,profile,modes,pcs,shard_size,exclude,start_operand=0,operand_count=None):
    corpus=Path(corpus);out=Path(out);manifest=verify_dataset(corpus)
    if manifest['kind']!='input_corpus':raise ValueError('not an input corpus')
    if start_operand<0 or operand_count is not None and operand_count<1:raise ValueError('invalid operand range')
    out.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(out/'exclusions.sqlite')
    db.execute('CREATE TABLE exclusions(case_id TEXT PRIMARY KEY) WITHOUT ROWID')
    for directory in exclude:
        db.executemany('INSERT OR IGNORE INTO exclusions VALUES(?)',((row['case_id'],) for row in observations(directory)))
    db.commit();jobs=[];rows=skipped=0;stream=None;job=None;jobrows=0
    def close_job():
        if stream:
            stream.close();save(job/'JOB.json',dict(schema='x87-suite-v1',corpus_id=manifest['corpus_id'],
                corpus_manifest_sha256=digest(corpus/'MANIFEST.json'),profile=profile,rows=jobrows,
                inputs_sha256=digest(job/'inputs.txt'),contract='all masked, depth1, clear, raw80',
                one_observation_maximum=True,retry_partial=False))
            jobs.append(dict(directory=job.name,rows=jobrows,job_sha256=digest(job/'JOB.json')))
    selected_index=0;selected_operands=0
    with gzip.open(corpus/'operands.tsv.gz','rt') as f:
        reader=csv.DictReader(f,delimiter='\t')
        for row in reader:
            flags=int(row['profiles'])
            if profile=='core' and not flags&1:continue
            if profile=='smoke' and not flags&2:continue
            if selected_index<start_operand:selected_index+=1;continue
            if operand_count is not None and selected_operands>=operand_count:break
            selected_index+=1;selected_operands+=1
            for insn in INSNS:
                for mode in modes:
                    for pc in pcs:
                        case=case_id(insn,mode,pc,row['se']+' '+row['sig'])
                        if db.execute('SELECT 1 FROM exclusions WHERE case_id=?',(case,)).fetchone():skipped+=1;continue
                        if stream is None or jobrows==shard_size:
                            close_job();job=out/f'job-{len(jobs):05d}';job.mkdir();stream=(job/'inputs.txt').open('x');jobrows=0
                        stream.write(capture_line(case)+'\n');jobrows+=1;rows+=1
    close_job();db.close()
    result=dict(corpus_id=manifest['corpus_id'],profile=profile,modes=modes,pcs=pcs,exported_rows=rows,
        start_operand=start_operand,selected_operands=selected_operands,next_operand=start_operand+selected_operands,
        skipped_existing_observations=skipped,jobs=jobs,
        excludes=[dict(manifest_sha256=digest(Path(x)/'MANIFEST.json'),rows=verify_dataset(x)['rows']) for x in exclude],
        warning='Exclusion is limited to the supplied observations. Import all history for an already-used CPU; a new empty ledger is not freshness clearance.')
    save(out/'EXPORT.json',result);return result


def plan(corpus,profile,modes,pcs,rate,max_hours,start_operand=0,operand_count=None):
    """Budget estimate only: no benchmark instructions or capture side effects."""
    import math
    if not math.isfinite(rate) or rate<=0 or not math.isfinite(max_hours) or max_hours<=0:
        raise ValueError('rate and budget must be positive finite numbers')
    manifest=verify_dataset(corpus);total=manifest['profiles'][profile]['operands']
    if start_operand<0 or operand_count is not None and operand_count<1:raise ValueError('invalid operand range')
    count=max(0,total-start_operand)
    if operand_count is not None:count=min(count,operand_count)
    rows=count*len(INSNS)*len(modes)*len(pcs);hours=rows/rate/3600
    return dict(corpus_id=manifest['corpus_id'],profile=profile,operands=count,executions=rows,
        modes=modes,pcs=pcs,assumed_executions_per_second=rate,estimated_hours=hours,
        budget_hours=max_hours,within_budget=hours<=max_hours,
        estimated_uncompressed_input_and_output_GB=rows*260/1e9,
        limits='Planning assumption, not a measured speed or bound. Disk excludes ledger/index growth. Use actual first-shard wall time without repeating it; retain all observations and reservations.')


def compare(left,right,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    a=iter(observations(left));b=iter(observations(right));x=next(a,None);y=next(b,None);counts=Counter()
    with gzwrite(out/'differences.tsv.gz') as f:
        w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(('case_id','kind','left_sin','right_sin','left_cos','right_cos','left_SW','right_SW'))
        while x is not None or y is not None:
            if y is None or x is not None and x['case_id']<y['case_id']:counts['left_only']+=1;x=next(a,None);continue
            if x is None or y['case_id']<x['case_id']:counts['right_only']+=1;y=next(b,None);continue
            counts['common']+=1;changes=[]
            if (x['sin'],x['cos'],x['C2'])!=(y['sin'],y['cos'],y['C2']):changes.append('numeric_or_C2');counts['numeric_or_C2_differences']+=1
            if x['C1']!=y['C1']:changes.append('C1_observed');counts['C1_observed_differences']+=1
            if x['SW']!=y['SW']:counts['full_SW_differences_observational']+=1
            if changes:w.writerow((x['case_id'],'+'.join(changes),x['sin'],y['sin'],x['cos'],y['cos'],x['SW'],y['SW']))
            x=next(a,None);y=next(b,None)
    report=dict(status='NO_COMMON_CASES' if not counts['common'] else 'DIFFERENCES' if counts['numeric_or_C2_differences'] or counts['C1_observed_differences'] else 'MATCH_ON_COMMON_CASES',
        counts=dict(counts),left_cpu=json.loads((Path(left)/'cpu.json').read_text()),right_cpu=json.loads((Path(right)/'cpu.json').read_text()),
        left_manifest_sha256=digest(Path(left)/'MANIFEST.json'),right_manifest_sha256=digest(Path(right)/'MANIFEST.json'),
        differences_sha256=digest(out/'differences.tsv.gz'),
        limits='Missing cases are missing, never passes. All recorded C1/SW differences are observational; special/undefined flags are not automatically algorithm misses. CPUID may be virtualized.')
    save(out/'report.json',report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    q=s.add_parser('verify');q.add_argument('dataset',type=Path)
    for command in ('export','plan'):
        q=s.add_parser(command);q.add_argument('corpus',type=Path)
        q.add_argument('--profile',choices=('smoke','core','full'),default='core');q.add_argument('--modes',nargs='+',choices=MODES,default=list(MODES))
        q.add_argument('--pcs',nargs='+',type=int,choices=PCS)
        q.add_argument('--start-operand',type=int,default=0);q.add_argument('--operand-count',type=int)
        if command=='export':
            q.add_argument('--output',required=True,type=Path);q.add_argument('--shard-size',type=int,default=100000)
            q.add_argument('--exclude-observations',nargs='*',type=Path,default=[])
        else:
            q.add_argument('--executions-per-second',type=float,default=1000)
            q.add_argument('--max-hours',type=float,default=168)
    for name in ('import-state','import-numeric'):
        q=s.add_parser(name);q.add_argument('capture',type=Path);q.add_argument('--output',required=True,type=Path)
    q=s.add_parser('compare');q.add_argument('left',type=Path);q.add_argument('right',type=Path);q.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.command=='verify':result=verify_dataset(a.dataset)
    elif a.command in ('export','plan'):
        # All raw operands are retained. The full profile avoids tripling the
        # large matrix by default; explicit --pcs 24 53 64 remains available.
        a.pcs=a.pcs or ([64] if a.profile=='full' else list(PCS))
        if len(set(a.modes))!=len(a.modes) or len(set(a.pcs))!=len(a.pcs):p.error('duplicate controls')
        if a.command=='export':
            if a.shard_size<1:p.error('invalid shard size')
            result=export(a.corpus,a.output,a.profile,a.modes,a.pcs,a.shard_size,a.exclude_observations,a.start_operand,a.operand_count)
        else:
            result=plan(a.corpus,a.profile,a.modes,a.pcs,a.executions_per_second,a.max_hours,a.start_operand,a.operand_count)
            if not result['within_budget']:
                print(json.dumps(result,sort_keys=True));raise SystemExit(2)
    elif a.command=='import-state':result=dict(imported_rows=import_state(a.capture,a.output))
    elif a.command=='import-numeric':result=dict(imported_rows=import_numeric(a.capture,a.output))
    else:result=compare(a.left,a.right,a.output)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
