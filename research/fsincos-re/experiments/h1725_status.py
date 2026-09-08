#!/usr/bin/env python3
"""Report durable full-corpus progress; never start or retry a capture."""
import argparse
import json
import os
import shlex
import subprocess
import tempfile
import time
from h1725_full_campaign import BASE,HOSTS


def autonomous_snapshot(host, marker):
    """Read-only observer: a sleeping/offline Mac cannot pause remote work."""
    package = marker['remote_package']
    script = '''import json,pathlib,shutil
p=pathlib.Path(PACKAGE)
result={n:json.loads((p/n).read_text()) for n in ('STATUS.json','RUN_COMPLETE.json','STOPPED.json','CUTOVER.json') if (p/n).exists()}
done=sorted((p/'observed').glob('job-*.DONE.json'))
if done: result['last_done']=dict(name=done[-1].name,receipt=json.loads(done[-1].read_text()))
s=result.get('STATUS.json',{}); pid=s.get('pid',0); cmd=pathlib.Path('/proc')/str(pid)/'cmdline'
result['remote_process_present']=cmd.exists() and b'h1725_autonomous.py' in cmd.read_bytes()
result['free_disk_bytes']=shutil.disk_usage(p).free
print(json.dumps(result))'''.replace('PACKAGE', repr(package))
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
        'root@' + HOSTS[host], shlex.join(['python3', '-c', script])], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError('read-only remote status unavailable: ' + result.stderr.strip())
    data = json.loads(result.stdout); state = data.get('STATUS.json', {})
    cfg = data['CUTOVER.json']; last = data.get('last_done')
    counts = last['receipt']['totals'] if last else cfg['prior_totals']
    completed = int(last['name'].split('-')[1].split('.')[0]) + 1 if last else cfg['start_job']
    row = dict(stage=state.get('stage', 'REMOTE_SERVICE_STARTING'), execution_location='remote_server',
        mac_required_for_execution=False, controller_process_present=data['remote_process_present'],
        remote_pid=state.get('pid'), controller_update_age_seconds=round(time.time()-state.get('updated_unix',time.time()),1),
        completed_shards=completed, verified_fresh_cases=counts['rows'], selected_fresh_cases=cfg['selected_cases'],
        numerical_or_C1_C2_misses=sum(v for k,v in counts.items() if k.endswith('_misses')),
        last_completed_shard=f'job-{completed-1:06d}', current_job=state.get('job'), free_disk_bytes=data['free_disk_bytes'])
    if 'STOPPED.json' in data:
        row.update(stage='REMOTE_STOPPED_INSPECT_RECEIPTS', error=data['STOPPED.json']['error'])
    elif 'RUN_COMPLETE.json' in data:
        row.update(stage='SELECTED_RUN_COMPLETE_HOLDS_REMAIN', completion=data['RUN_COMPLETE.json'])
    elif not data['remote_process_present']:
        row['stage']='REMOTE_PROCESS_MISSING_INSPECT_RECEIPTS'
    if last:
        seconds=last['receipt']['seconds']; new_cases=counts['rows']-cfg['prior_totals']['rows']
        if seconds>0 and new_cases>0:
            rate=new_cases/seconds
            row.update(measured_cases_per_second=round(rate,1),
                estimated_remaining_hours_at_observed_rate=round((cfg['selected_cases']-counts['rows'])/rate/3600,2))
    return row


def snapshot():
    processes=subprocess.check_output(['ps','-eo','pid,args'],text=True)
    result={}
    for host in HOSTS:
        out=BASE/host;selection=out/'SELECTION.json';done=sorted((out/'jobs').glob('job-*/DONE.json'))
        if (out/'AUTONOMOUS_CUTOVER.json').exists():
            try:
                result[host]=autonomous_snapshot(host,json.loads((out/'AUTONOMOUS_CUTOVER.json').read_text()))
            except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
                result[host]=dict(stage='REMOTE_STATUS_UNAVAILABLE',execution_location='remote_server',
                    mac_required_for_execution=False,error=str(exc),
                    note='Observer cannot reach the server. This is not evidence that native execution stopped.')
            continue
        active=any('h1725_' in line and '--host '+host in line for line in processes.splitlines())
        row=dict(controller_process_present=active,completed_shards=len(done),verified_fresh_cases=0,
            numerical_or_C1_C2_misses=0)
        if selection.exists():row['selected_fresh_cases']=json.loads(selection.read_text())['counts']['selected_cases']
        if done:
            last=json.loads(done[-1].read_text());counts=last['totals'];row['verified_fresh_cases']=counts['rows']
            row['numerical_or_C1_C2_misses']=sum(v for k,v in counts.items() if k.endswith('_misses'))
            row['last_completed_shard']=done[-1].parent.name
            row['elapsed_seconds']=last['seconds']
            row['measured_cases_per_second']=round(counts['rows']/last['seconds'],1)
            if 'selected_fresh_cases' in row:
                row['estimated_remaining_hours_at_observed_rate']=round((row['selected_fresh_cases']-counts['rows'])/(counts['rows']/last['seconds'])/3600,2)
        pending=sorted(p for p in (out/'jobs').glob('job-*/score.json') if not (p.parent/'DONE.json').exists())
        for path in pending:
            score=json.loads(path.read_text())
            row['verified_fresh_cases']+=score['counts']['rows']
            row['numerical_or_C1_C2_misses']+=sum(v for k,v in score['counts'].items() if k.endswith('_misses'))
            row['scored_but_housekeeping_pending']=path.parent.name
        controller=json.loads((out/'CONTROLLER.json').read_text()) if (out/'CONTROLLER.json').exists() else None
        if controller:
            pid=str(controller['pid'])
            active=any(line.split(None,1)[0]==pid and 'h1725_resume_full.py' in line for line in processes.splitlines() if line.strip())
            row['controller_process_present']=active
            row['controller_stage']=controller['stage']
            row['controller_update_age_seconds']=round(time.time()-controller['updated_unix'],1)
            if 'job' in controller:row['current_job']=controller['job']
            if controller.get('cases_per_second',0)>0:
                rate=controller['cases_per_second'];row['measured_cases_per_second']=round(rate,1)
                row['estimated_remaining_hours_at_observed_rate']=round((row['selected_fresh_cases']-row['verified_fresh_cases'])/rate/3600,2)
        if (out/'RUN_COMPLETE.json').exists():row['stage']='SELECTED_RUN_COMPLETE_HOLDS_REMAIN'
        elif row['numerical_or_C1_C2_misses']:row['stage']='MODEL_MISS_STOPPED'
        elif (out/'RESUME_STOPPED.json').exists():row['stage']='CONTROLLER_STOPPED_INSPECT_RECEIPTS'
        elif controller and active:row['stage']=controller['stage']
        elif (out/'RUN_STARTED.json').exists():row['stage']='RUNNING' if active else 'CONTROLLER_STOPPED_INSPECT_LAST_JOB'
        elif selection.exists():row['stage']='SELECTION_FROZEN'
        else:
            log=(out/'public-history.log').read_text().splitlines()
            try:audit=json.loads(log[-1]) if log else {}
            except json.JSONDecodeError:audit={}
            row['stage']='SELECTING' if audit.get('status')=='PUBLIC_HISTORY_EXPORT_COMPLETE' else 'AUDITING_HISTORY'
            if not active:row['stage']='CONTROLLER_STOPPED_BEFORE_CAPTURE'
        result[host]=row
    return dict(updated_unix=time.time(),campaign='H1725',hosts=result,algorithm_changed=False,paper_changed=False,
        limits='Progress counters count completed, scored new observations only. Held and legacy-PC-unknown cases are not counted as fresh passes.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--watch',action='store_true');a=p.parse_args()
    while True:
        value=snapshot();path=BASE/'LIVE_STATUS.json'
        with tempfile.NamedTemporaryFile(mode='w',prefix='LIVE_STATUS-',suffix='.next.json',dir=BASE,delete=False) as f:
            json.dump(value,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno());temp=f.name
        os.replace(temp,path);print(json.dumps(value),flush=True)
        if not a.watch or all(x['stage']=='SELECTED_RUN_COMPLETE_HOLDS_REMAIN' for x in value['hosts'].values()):break
        time.sleep(30)
