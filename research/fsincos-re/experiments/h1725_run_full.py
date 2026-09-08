#!/usr/bin/env python3
"""Execute the frozen full-corpus selection in bounded, one-shot shards.

Predictions precede capture. All outputs, misses and input/control identities
are retained locally. Remote scratch is released only after verified local
offload; permanent remote reservation bits and receipts are never cleared.
This script does not alter the numerical algorithm or the academic paper.
"""
import argparse
import collections
import gzip
import json
import os
import struct
import subprocess
import time
from pathlib import Path
from h1725_full_campaign import ROOT,BASE,HOSTS,CORPUS,INSNS,MODES,PINS,save,suite

REMOTE='/root/h1725-full-corpus'
CAPTURE={'i7':'/root/h1721-freshness/capture_numeric','skylake':'/root/fsincos-h1715-suite/capture_numeric'}
LEDGER={'i7':'/root/h1722-policy2-confidence/ledger.sqlite','skylake':'/root/fsincos-h1715-suite/ledger.sqlite'}
BINARY_SHA='fd96d6ce1270cb37e327a1a28f4494753e529732b91638fa5741e63b0682fdfd'


def ssh(host,command,**kwargs):
    return subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','root@'+HOSTS[host],command],check=True,**kwargs)


def scp(host,paths,dest):
    subprocess.run(['scp',*[str(p) for p in paths],'root@'+HOSTS[host]+':'+dest],check=True)


def setup(host):
    ssh(host,'mkdir -p '+REMOTE)
    scp(host,[ROOT/'experiments/h1725_remote_capture.py',ROOT/'corpus-suite/suite.py',ROOT/'corpus-suite/run_capture.py'],REMOTE+'/')
    actual=ssh(host,'sha256sum '+CAPTURE[host],capture_output=True,text=True).stdout.split()[0]
    assert actual==BINARY_SHA
    ssh(host,'python3 -m py_compile '+REMOTE+'/h1725_remote_capture.py '+REMOTE+'/run_capture.py '+REMOTE+'/suite.py')


def predict(job,records,predictor):
    predictions={};groups=collections.defaultdict(list)
    for ordinal,se,sig,mask in records:
        op=f'{se:04x} {sig:016x}'
        for i in range(12):
            if mask&(1<<i):groups[i].append(op)
    for i,ops in sorted(groups.items()):
        insn,mode=INSNS[i//4],MODES[i%4]
        path=job/f'predict-input-{insn}-{mode}.txt'
        with path.open('x') as f:f.write(''.join(op+'\n' for op in ops))
        result=subprocess.run([str(predictor),'--predict',insn,mode,str(path)],text=True,capture_output=True,check=True)
        if result.stderr:raise ValueError('predictor diagnostic')
        lines=result.stdout.splitlines();assert len(lines)==len(ops)
        for op,line in zip(ops,lines):
            values,meta=line.split(' META ');known,c1=map(int,meta.split())
            predictions[suite.case_id(insn,mode,64,op)]=dict(value=values,known=known,c1=c1)
    with gzip.open(job/'predictions.json.gz','xt',compresslevel=1) as f:json.dump(predictions,f,sort_keys=True)
    return predictions


def score(job,predictions):
    counts=collections.Counter();misses=[];observations=[]
    with gzip.open(job/'inputs.txt.gz','rt') as inputs,gzip.open(job/'outputs.txt.gz','rt') as outputs:
        for line in inputs:
            case=line.split()[0];insn,mode,pc,op=suite.decode_case(case)
            raw=next(outputs);fields=suite.parse_numeric(raw)
            obs=suite.validate_numeric(fields,insn,mode,pc,op,case);observations.append(obs)
            expected=predictions[case];value=expected['value'].split();c2=bool(int(fields['A_SW'],16)&0x400)
            tests={'C2':c2==(value[0]=='C2')}
            if not c2 and value[0]=='OK':
                if insn=='fsincos':
                    tests['sine']=fields['SIN']==value[1]+':'+value[2]
                    tests['cosine']=fields['COS']==value[3]+':'+value[4]
                else:tests['output']=fields['SIN' if insn=='fsin' else 'COS']==value[1]+':'+value[2]
                if expected['known']:tests['C1']=((int(fields['A_SW'],16)>>9)&1)==expected['c1']
            for k,ok in tests.items():counts[k+'_checks']+=1;counts[k+'_misses']+=not ok
            counts['rows']+=1
            if not all(tests.values()):misses.append(dict(case_id=case,expected=expected,actual=fields,checks=tests))
        assert not outputs.readline() and counts['rows']==len(predictions)
    save(job/'score.json',dict(status='PASS' if not misses else 'MODEL_MISMATCH',counts=dict(counts),misses=misses,
        prediction_sha256=suite.digest(job/'predictions.json.gz'),raw_sha256=suite.digest(job/'outputs.txt.gz')))
    portable=job/'observations';portable.mkdir()
    with suite.gzwrite(portable/'observations.tsv.gz') as f:
        f.write('\t'.join(suite.FIELDS)+'\n')
        for row in sorted(observations):f.write('\t'.join(map(str,row))+'\n')
    save(portable/'cpu.json',json.loads((job/'cpu.json').read_text()))
    save(portable/'provenance.json',dict(source='H1725 one-shot full corpus numerical capture',
        complete_sha256=suite.digest(job/'COMPLETE.json'),raw_sha256=suite.digest(job/'outputs.txt.gz'),
        prediction_sha256=suite.digest(job/'predictions.json.gz'),hardware_retries=0))
    save(portable/'MANIFEST.json',dict(schema='x87-suite-v1',kind='hardware_observations',rows=counts['rows'],
        files={n:suite.digest(portable/n) for n in ('observations.tsv.gz','cpu.json','provenance.json')}))
    assert sum(1 for _ in suite.observations(portable))==counts['rows']
    return counts,len(misses)


def run(host,operands_per_job=5000):
    out=BASE/host;selection=json.loads((out/'SELECTION.json').read_text())
    assert selection['corpus_id']==CORPUS and suite.digest(out/'selected.bin')==selection['selected_sha256']
    preflight=json.loads((BASE/'PREFLIGHT.json').read_text());assert preflight['status']=='PASS'
    for name,sha in PINS.items():assert suite.digest(ROOT/name)==sha
    predictor=BASE/'predictor';assert suite.digest(predictor)==preflight['predictor_sha256']
    setup(host)
    prior=json.loads((out/'prior-ledger-0.json').read_text());contexts={r[0] for r in prior['counts']};assert len(contexts)==1
    context=next(iter(contexts));jobs=out/'jobs';jobs.mkdir(exist_ok=True)
    save(out/'RUN_STARTED.json',dict(status='RUNNING',started_unix=time.time(),
        selection_sha256=suite.digest(out/'SELECTION.json'),source_sha256=suite.digest(Path(__file__)),
        remote_runner_sha256=suite.digest(ROOT/'experiments/h1725_remote_capture.py'),predictor_sha256=suite.digest(predictor)))
    totals=collections.Counter();started=time.time()
    with (out/'selected.bin').open('rb') as stream:
        number=0
        while True:
            raw=stream.read(20*operands_per_job)
            if not raw:break
            assert len(raw)%20==0
            records=list(struct.iter_unpack('<QHQH',raw));name=f'job-{number:06d}';number+=1
            job=jobs/name;job.mkdir(exist_ok=False)
            for path,sha in PINS.items():assert suite.digest(ROOT/path)==sha
            predictions=predict(job,records,predictor)
            with gzip.open(job/'inputs.txt.gz','xt',compresslevel=1) as f,(job/'indices.bin').open('xb') as idx:
                for ordinal,se,sig,mask in records:
                    op=f'{se:04x} {sig:016x}'
                    for i in range(12):
                        if mask&(1<<i):
                            case=suite.case_id(INSNS[i//4],MODES[i%4],64,op)
                            f.write(suite.capture_line(case)+'\n');idx.write(struct.pack('<Q',ordinal*12+i))
            save(job/'JOB.json',dict(corpus_id=CORPUS,host=host,pc=64,rows=len(predictions),cpu_context_id=context,
                binary_sha256=BINARY_SHA,files={n:suite.digest(job/n) for n in ('inputs.txt.gz','indices.bin')},
                predictions_sha256=suite.digest(job/'predictions.json.gz'),selection_sha256=selection['selected_sha256'],
                first_ordinal=records[0][0],last_ordinal=records[-1][0],frozen_before_capture=True,algorithm_pins=PINS))
            ssh(host,'mkdir '+REMOTE+'/'+name)
            scp(host,[job/n for n in ('JOB.json','inputs.txt.gz','indices.bin')],REMOTE+'/'+name+'/')
            with (job/'remote-run.log').open('x') as log:
                ssh(host,'python3 '+REMOTE+'/h1725_remote_capture.py capture --base '+REMOTE+' --job '+name+
                    ' --binary '+CAPTURE[host]+' --ledger '+LEDGER[host],stdout=log,stderr=subprocess.STDOUT)
            downloads=('outputs.txt.gz','COMPLETE.json','STARTED.json','cpu.json','cpu-after.json','stderr.txt')
            subprocess.run(['scp',*['root@'+HOSTS[host]+':'+REMOTE+'/'+name+'/'+n for n in downloads],str(job)+'/'],check=True)
            done=json.loads((job/'COMPLETE.json').read_text());assert done['status']=='OPENED_ONCE_DO_NOT_RERUN'
            assert done['rows']==len(predictions) and done['outputs_sha256']==suite.digest(job/'outputs.txt.gz')
            assert done['inputs_sha256']==suite.digest(job/'inputs.txt.gz') and done['cpu_context_id']==context
            counts,misses=score(job,predictions);totals.update(counts)
            # Hash the decompressed local input without creating another copy.
            import hashlib
            h=hashlib.sha256()
            with gzip.open(job/'inputs.txt.gz','rb') as f:
                for b in iter(lambda:f.read(1<<20),b''):h.update(b)
            hashes={n:suite.digest(job/n) for n in ('inputs.txt.gz','indices.bin','outputs.txt.gz','stderr.txt')};hashes['inputs.txt']=h.hexdigest()
            save(job/'OFFLOAD.json',dict(files=hashes,local_archive_verified=True))
            scp(host,[job/'OFFLOAD.json'],REMOTE+'/'+name+'/')
            ssh(host,'python3 '+REMOTE+'/h1725_remote_capture.py ack --base '+REMOTE+' --job '+name,stdout=subprocess.DEVNULL)
            save(job/'DONE.json',dict(status='PASS' if not misses else 'MODEL_MISMATCH',totals=dict(totals),seconds=time.time()-started))
            print(json.dumps(dict(host=host,job=name,totals=dict(totals),seconds=time.time()-started)),flush=True)
            if misses:raise RuntimeError('New model miss retained; further capture paused for analysis')
    assert totals['rows']==selection['counts']['selected_cases']
    save(out/'RUN_COMPLETE.json',dict(status='PASS_SELECTED_REMAINING_CASES',totals=dict(totals),seconds=time.time()-started,
        full_matrix_complete=False,remaining_holds=selection['counts'],paper_changed=False,algorithm_changed=False))
    print(host,'COMPLETE',dict(totals),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',choices=HOSTS,required=True)
    p.add_argument('--operands-per-job',type=int,default=5000);a=p.parse_args()
    assert 1<=a.operands_per_job<=10000
    run(a.host,a.operands_per_job)
