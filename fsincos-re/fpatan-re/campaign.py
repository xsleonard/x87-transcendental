"""Explicit bounded campaign steps; no capture retries or inferred completion.

Only generic capture/guard/protocol and public cleared inputs are uploaded.
All hardware observations are preserved remotely and locally. Model code
and private records never leave this machine.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
from protocol import validate_inputs,validate_output
from prepare import save,digest

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'tmp/fpatan-re'
HOST='root@45.32.204.118'
REMOTE='/root/fpatan-re'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',HOST]


def history(job):
    with (job/'HISTORY.json').open('xb') as out:
        subprocess.run(SSH+['python3 -'],input=(HERE/'audit_history.py').read_bytes(),stdout=out,check=True)
    report=json.loads((job/'HISTORY.json').read_text())
    print(json.dumps(report),flush=True)
    assert report['status']=='NO_PRIOR_FPATAN_FOUND'


def stage(job):
    assert json.loads((job/'HISTORY.json').read_text())['status']=='NO_PRIOR_FPATAN_FOUND'
    remote=REMOTE+'/'+job.name
    subprocess.run(SSH+['mkdir -p '+REMOTE+' && mkdir '+remote],check=True)
    compressed=json.loads((job/'MANIFEST.json').read_text()).get('format')=='fpatan-gzip-v2'
    files=[job/('inputs.txt.gz' if compressed else 'inputs.txt'),job/'MANIFEST.json',job/'HISTORY.json']
    files += [HERE/name for name in ('capture.c','protocol.py','compressed_guard.py' if compressed else 'remote_guard.py')]
    subprocess.run(['scp',*[str(p) for p in files],HOST+':'+remote+'/'],check=True)
    # Building/identity/protocol tests execute NO FPATAN. There is no warmup.
    command='cd '+remote+' && gcc -O2 -std=c11 -Wall -Wextra -Werror capture.c -o capture && python3 protocol.py && ./capture --identity && objdump -d capture | grep fpatan'
    result=subprocess.run(SSH+[command],capture_output=True,text=True,check=True)
    save(job/'STAGED.json',dict(stdout=result.stdout,stderr=result.stderr,
        files={p.name:digest(p) for p in files},hardware_executed=False))
    print(result.stdout,flush=True)


def capture(job):
    assert (job/'STAGED.json').exists()
    # A durable local dispatch record also prevents uncertain SSH completion
    # from being mistaken for permission to run the capture again.
    dispatch=dict(status='DISPATCHED_DO_NOT_RETRY',host=HOST,job=job.name)
    # A structural discriminator has an additional local-only prediction
    # artifact. Pin it before dispatch; it is never sent to the capture host.
    hypothesis=job/'STRUCTURAL-HYPOTHESIS.json'
    if hypothesis.exists():dispatch['structural_hypothesis_sha256']=digest(hypothesis)
    save(job/'DISPATCHED.json',dispatch)
    compressed=json.loads((job/'MANIFEST.json').read_text()).get('format')=='fpatan-gzip-v2'
    guard='compressed_guard.py' if compressed else 'remote_guard.py'
    result=subprocess.run(SSH+['python3 '+REMOTE+'/'+job.name+'/'+guard+' --base '+REMOTE+' --job '+job.name],capture_output=True,text=True)
    save(job/'SSH_CAPTURE_RETURN.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    print(result.stdout,result.stderr,flush=True)
    if result.returncode:raise RuntimeError('Inspect reservations and partial outputs; do not retry')


def fetch(job):
    remote=REMOTE+'/'+job.name
    compressed=json.loads((job/'MANIFEST.json').read_text()).get('format')=='fpatan-gzip-v2'
    for name in ('STARTED.json','COMPLETE.json','hardware.txt.gz' if compressed else 'hardware.txt','hardware.stderr'):
        with (job/name).open('xb') as f:subprocess.run(SSH+['cat '+remote+'/'+name],stdout=f,check=True)
    complete=json.loads((job/'COMPLETE.json').read_text())
    if compressed:assert complete['hardware_gzip_sha256']==digest(job/'hardware.txt.gz')
    else:assert complete['hardware_sha256']==digest(job/'hardware.txt')
    assert complete['manifest_sha256']==digest(job/'MANIFEST.json')
    print('Fetched and authenticated',complete['rows'],'one-shot rows')


def ledger(job):
    # Aggregate-only, read-only audit. It never executes the capture binary.
    code="""import json,sqlite3
db=sqlite3.connect('file:/root/fpatan-re/ledger.sqlite?mode=ro',uri=True)
batch=[]
if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_reservations'").fetchone():
 batch=db.execute('SELECT context,job,state,rows FROM batch_reservations ORDER BY job').fetchall()
print(json.dumps({'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],
 'counts':db.execute('SELECT context,job,state,count(*) FROM reservations GROUP BY context,job,state ORDER BY job').fetchall(),
 'compressed_batches':batch}))
db.close()
"""
    result=subprocess.run(SSH+['python3 -'],input=code,text=True,capture_output=True,check=True)
    report=json.loads(result.stdout);assert report['integrity']=='ok'
    save(job/'LEDGER-AUDIT.json',report);print(json.dumps(report),flush=True)


def score(job):
    manifest=json.loads((job/'MANIFEST.json').read_text())
    if manifest.get('format')=='fpatan-gzip-v2':
        from score_stream import score as stream_score
        return stream_score(job)
    for name,sha in manifest['files'].items():assert digest(job/name)==sha
    complete=json.loads((job/'COMPLETE.json').read_text())
    assert digest(job/'hardware.txt')==complete['hardware_sha256']
    inputs,keys=validate_inputs((job/'inputs.txt').read_text())
    raw=(job/'hardware.txt').read_text().splitlines()
    assert len(raw)==len(inputs)==manifest['rows']
    prediction_rows=list(map(str.split,(job/'predictions.txt').read_text().splitlines()))
    predicted={t[0]:(int(t[1],16),int(t[2],16)) for t in prediction_rows}
    predicted_c1={t[0]:int(t[3]) for t in prediction_rows if len(t)==4}
    math={t[0]:(int(t[1],16),int(t[2],16),t[3]) for t in map(str.split,(job/'math-oracle.txt').read_text().splitlines())}
    categories=json.loads((job/'categories.json').read_text())
    status_predictions=json.loads((job/'status-predictions.json').read_text()) if (job/'status-predictions.json').exists() else {}
    counts=collections.Counter();groups=collections.defaultdict(collections.Counter);misses=[]
    pcgroups=collections.defaultdict(dict)
    for actual,expected in zip(raw,inputs):
        observed=validate_output(actual,expected);parts=expected.split();ident=parts[0]
        hardware=(observed['se'],observed['sig']);reference=math[ident]
        cm=hardware!=predicted[ident];mm=reference[2]=='CERTIFIED' and hardware!=reference[:2]
        assert reference[2] in ('CERTIFIED','NOT_APPLICABLE')
        if reference[2]=='NOT_APPLICABLE':assert manifest.get('mathematical_oracle') is False
        for c in (counts,groups[categories[ident]],groups['rc-'+parts[1]],groups['pc-'+parts[2]]):
            c['rows']+=1;c['candidate_misses']+=cm;c['mathematical_rounding_differences']+=mm
            c['mathematical_rounding_checks']+=reference[2]=='CERTIFIED'
        counts['C1_set']+=observed['C1'];counts['IE_set']+=bool(observed['sw']&1)
        counts['UE_set']+=bool(observed['sw']&16)
        if ident in predicted_c1:
            counts['candidate_C1_checks']+=1;counts['candidate_C1_misses']+=predicted_c1[ident]!=observed['C1']
        if ident in status_predictions:
            status=status_predictions[ident];counts['exception_checks']+=1
            counts['exception_misses']+=(observed['sw']&63)!=status['after_exceptions']
            counts['before_exception_misses']+=(observed['before']&63)!=status['before_exceptions']
        pcgroups[tuple([parts[1]]+parts[3:])][parts[2]]=(*hardware,observed['sw'])
        if cm:misses.append(dict(id=ident,kind=categories[ident],input=expected,hardware=hardware,
            prediction=predicted[ident],mathematical=reference[:2],sw=observed['sw']))
    for values in pcgroups.values():
        if len(values)==3:
            counts['all_PC_groups']+=1;counts['PC_value_or_status_differences']+=len(set(values.values()))!=1
    save(job/'SCORE.json',dict(status='DISCOVERY_SCORED_NOT_VALIDATED_SOLUTION',counts=dict(counts),
        groups={k:dict(v) for k,v in groups.items()},hardware_sha256=complete['hardware_sha256'],
        candidate_frozen_before_capture=True,C1_candidate='present' if predicted_c1 else 'not implemented',paper_changed=False))
    save(job/'candidate-misses.json',misses)
    print(json.dumps(dict(counts),indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('step',choices=('history','stage','capture','fetch','score','ledger'))
    p.add_argument('--job',default='d0001');a=p.parse_args()
    assert Path(a.job).name==a.job and a.job not in ('.','..')
    globals()[a.step](BASE/a.job)
