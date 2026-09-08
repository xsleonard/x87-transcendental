#!/usr/bin/env python3
"""Freeze the same new challenge matrix for two independently observed CPUs.

All predictions, scorer checks and freshness evidence precede any hardware
labels. This creates an input-only export; model and private sources stay
local. Every instruction/RC/PC tuple is executed once per CPU, never retried.
"""
import argparse
import json
import subprocess
from datetime import datetime,timezone
from pathlib import Path
import h1715_score_capture as scorer
import suite
from h1719_run_saved_suite import PINS,digest,save

BANK='tmp/ledger33/current/h1721_challenge_bank/bank.json'
AUDIT='tmp/ledger33/current/h1721_freshness'
BINARY='tmp/ledger33/current/h1715_capture_build/capture_numeric'
BINARY_SHA='fd96d6ce1270cb37e327a1a28f4494753e529732b91638fa5741e63b0682fdfd'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    bank=json.loads((root/BANK).read_text());audit=json.loads((root/AUDIT/'report.json').read_text())
    assert audit['status']=='LOCAL_AUDIT_CLEAR_NOT_FROZEN' and audit['sha256']['bank']==digest(root/BANK)
    assert bank['sha256']['script']==digest(root/'experiments/h1721_policy2_challenge.py')
    assert audit['sha256']['script']==digest(root/'experiments/h1721_freshness.py')
    assert not audit['private_matching_significands'] and not audit['private_possible_occurrences']
    for name,sha in bank['sha256']['evidence'].items():assert digest(root/name)==sha,name
    for name,sha in PINS.items():assert digest(root/name)==sha,name
    assert digest(root/BINARY)==BINARY_SHA
    assert digest(root/'corpus-suite/capture_numeric.c')=='c02d30fa4204bfb952302e9cc309132b5e21bfc32035b94feb3d2c24e81f7e3b'
    remote={};reject=set()
    for host in ('i7','skylake'):
        path=root/AUDIT/(host+'-native-remote.json');r=json.loads(path.read_text())
        assert r['status']=='PUBLIC_REMOTE_HISTORY_AUDITED'
        assert r['patterns_sha256']==digest(root/AUDIT/'candidate_signatures.txt')
        reject.update(r['matching_candidate_significands']);remote[host]=digest(path)
    eligible=[r for r in audit['eligible'] if r['operand'].split()[1] not in reject]
    # Separately audited schedule discriminators extend, never overwrite, the
    # broad fixed panel. The two source banks and audits remain immutable.
    extra_path=root/'tmp/ledger33/current/h1724_challenge_bank/bank.json'
    extra=json.loads(extra_path.read_text());extra_audit_dir=root/'tmp/ledger33/current/h1724_freshness'
    extra_audit=json.loads((extra_audit_dir/'report.json').read_text())
    assert extra_audit['status']=='LOCAL_AUDIT_CLEAR_NOT_FROZEN'
    assert extra_audit['sha256']['bank']==digest(extra_path)
    assert extra['sha256']['script']==digest(root/'experiments/h1724_separator_bank.py')
    for name,sha in extra['sha256']['evidence'].items():assert digest(root/name)==sha,name
    extra_reject=set();extra_remote={}
    for host in ('i7','skylake'):
        path=extra_audit_dir/(host+'-native-remote.json');r=json.loads(path.read_text())
        assert r['status']=='PUBLIC_REMOTE_HISTORY_AUDITED'
        assert r['patterns_sha256']==digest(extra_audit_dir/'candidate_signatures.txt')
        extra_reject.update(r['matching_candidate_significands']);extra_remote[host]=digest(path)
    eligible += [r for r in extra_audit['eligible'] if r['operand'].split()[1] not in extra_reject]
    assert eligible and len({r['operand'] for r in eligible})==len(eligible)
    out.mkdir(parents=True,exist_ok=False)
    # The current UBSan embedded verifier must reproduce every independently
    # predicted output and known C1 before any target-host labels are opened.
    with (out/'software-inputs.txt').open('x') as f:f.write(''.join(r['operand']+'\n' for r in eligible))
    checks=0
    for insn in suite.INSNS:
        for mode in suite.MODES:
            proc=subprocess.run([str(root/'tmp/ledger33/current/h1719_local_checks/ubsan'),
                '--predict',insn,mode,str(out/'software-inputs.txt')],capture_output=True,text=True,check=True)
            assert not proc.stderr
            lines=proc.stdout.splitlines();assert len(lines)==len(eligible)
            for row,line in zip(eligible,lines):
                p=row['predictions'][insn][mode];value,flags=line.split(' META ')
                expected='C2' if p['outputs'] is None else 'OK '+' '.join(x.replace(':',' ') for x in p['outputs'])
                assert value==expected and flags==f'{int(p["C1"] is not None)} {p["C1"] or 0}',(row['operand'],insn,mode)
                checks+=1
    rows=[]
    for row in eligible:
        for insn in suite.INSNS:
            for mode in suite.MODES:
                for pc in suite.PCS:
                    case=suite.case_id(insn,mode,pc,row['operand'])
                    rows.append(dict(case_id=case,instruction=insn,mode=mode,pc=pc,operand=row['operand'],
                        kinds=row['kinds'],prediction=row['predictions'][insn][mode],
                        policy1_prediction=row.get('policy1_predictions',{}).get(mode) if insn=='fsincos' else None))
    assert len(rows)==len({r['case_id'] for r in rows})==36*len(eligible)
    preflight=scorer.preflight(rows);save(out/'manifest.json',rows)
    job=out/'job';job.mkdir()
    with (job/'inputs.txt').open('x') as f:f.write(''.join(suite.capture_line(r['case_id'])+'\n' for r in rows))
    spec=dict(schema='x87-suite-v1',corpus_id='h1722-policy2-frozen-confidence',rows=len(rows),
        inputs_sha256=digest(job/'inputs.txt'),binary_sha256=BINARY_SHA,one_observation_maximum=True,
        retry_partial=False,freshness_audit_sha256=digest(root/AUDIT/'report.json'))
    save(job/'JOB.json',spec)
    for name in ('suite.py','run_capture.py','capture_numeric.c'):
        with (out/name).open('x') as f:f.write((root/'corpus-suite'/name).read_text())
    save(out/'operands.json',eligible)
    freeze=dict(experiment='h1722_policy2_confidence',capture_state='FROZEN_UNOPENED',
        frozen_utc=datetime.now(timezone.utc).isoformat(),unique_operands=len(eligible),tuples_per_CPU=len(rows),
        target_hosts={'i7':'142.132.217.243','skylake':'45.32.204.118'},job=spec,
        scorer_preflight=preflight,UBSan_prediction_checks=checks,remote_rejected_significands=len(reject),
        candidate_changed=False,paper_changed=False,instruction_retries=0,
        freshness_scope='Local public/compressed and aggregate private checks, explicit remote campaign trees, binary64 domain exclusion and all-counter default-seed raw80 generator exclusion. Unavailable/unknown-seed history is not claimed audited.',
        sha256=dict(manifest=digest(out/'manifest.json'),operands=digest(out/'operands.json'),bank=digest(root/BANK),
            extra_bank=digest(extra_path),extra_audit=digest(extra_audit_dir/'report.json'),extra_remote_audits=extra_remote,
            audit=digest(root/AUDIT/'report.json'),remote_audits=remote,freezer=digest(Path(__file__)),
            scorer=digest(root/'experiments/h1722_score_confidence.py'),base_scorer=digest(scorer.__file__),
            suite=digest(out/'suite.py'),runner=digest(out/'run_capture.py'),capture_source=digest(out/'capture_numeric.c'),
            candidate=PINS,paper_tex=digest(root/'paper/skylake-x87.tex'),paper_pdf=digest(root/'paper/skylake-x87.pdf')))
    save(out/'FREEZE.json',freeze)
    print(json.dumps(dict(status='FROZEN_UNOPENED',operands=len(eligible),tuples_per_CPU=len(rows),
        UBSan_checks=checks,scorer_preflight=preflight)),flush=True)


if __name__=='__main__':main()
