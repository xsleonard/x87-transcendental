#!/usr/bin/env python3
"""Freeze H1715 before any new hardware labels, split into disjoint builds."""
import argparse
import json
import re
import sys
from datetime import datetime,timezone
from pathlib import Path
import h1714_rounding_challenge as check
import h1715_freshness as audit
import h1715_score_capture as scorer
from h1709_paired_retained_census import digest,save
import suite

AUDIT='tmp/ledger33/current/h1715_freshness'
BUILD='tmp/ledger33/current/h1715_capture_build'
BINS={'x86_64':('capture_numeric','fd96d6ce1270cb37e327a1a28f4494753e529732b91638fa5741e63b0682fdfd'),
    'i386':('capture_numeric_i586','7bf061b8f9fe82ebe020ea0613842114de7b840913c473cd68e6adf7b595f263')}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--private-ledger-dir',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();private=a.private_ledger_dir.resolve();out=a.output_dir.resolve();assert not out.exists()
    report=json.loads((root/AUDIT/'report.json').read_text());bank=json.loads((root/audit.BANK).read_text())
    assert report['status']=='AUDITED_NOT_FROZEN' and digest(root/audit.BANK)==report['sha256']['bank']
    for name,sha in bank['sha256']['evidence'].items():assert digest(root/name)==sha,name
    assert digest(Path(audit.__file__))==report['sha256']['script']
    for key,path in [('base',Path(audit.base.__file__)),('scanner',Path(audit.base.matches.__code__.co_filename)),('private_scanner',Path(audit.base.private_audit.__file__))]:
        assert digest(path)==report['sha256'][key]
    assert digest(root/'corpus-suite/capture_numeric.c')=='c02d30fa4204bfb952302e9cc309132b5e21bfc32035b94feb3d2c24e81f7e3b'
    for binary,sha in BINS.values():assert digest(root/BUILD/binary)==sha,binary
    for name in ('capture.disassembly.txt','capture_i586.disassembly.txt'):
        assembly=(root/BUILD/name).read_text();instructions=[]
        for line in assembly.splitlines():
            w=line.split('\t')
            if len(w)>=3 and re.fullmatch(r'\s*[0-9a-f]+:',w[0]):instructions.append(w[2].strip())
        for insn in check.INSTRUCTIONS:
            sites=[i for i,x in enumerate(instructions) if x==insn];assert len(sites)==1
            assert instructions[sites[0]+1].startswith('fstsw ') and instructions[sites[0]+2].startswith('fnstcw ')
        assert not re.search(r'\b(fxsave|rdtsc|xmm[0-9]+)\b',assembly)
    check.independent.constants(root);eligible=report['eligible'];ops=[r['operand'] for r in eligible];assert len(ops)==len(set(ops))==2784
    cache={};checks=0
    for insn in check.INSTRUCTIONS:
        for mode in check.MODES:
            expected=[check.prediction(op,insn,mode,cache) for op in ops]
            assert expected==[r['predictions'][insn][mode] for r in eligible]
            for binary in (root/'src/fsincos_skylake',root/'tmp/ledger33/current/h1713_promotion_checks_v2/ubsan'):
                assert check.c_predictions(binary,insn,mode,ops)==expected;checks+=len(ops)
    rows=[]
    for index,row in enumerate(eligible):
        job=('x86_64','i386')[index%2]
        for insn in check.INSTRUCTIONS:
            for mode in check.MODES:
                for pc in (24,53,64):
                    case=suite.case_id(insn,mode,pc,row['operand'])
                    rows.append(dict(case_id=case,instruction=insn,mode=mode,pc=pc,operand=row['operand'],kinds=row['kinds'],
                        prediction=row['predictions'][insn][mode],job=job,capture_line=suite.capture_line(case)))
    assert len(rows)==len({r['case_id'] for r in rows})==100224
    preflight=scorer.preflight(rows);print('Default/UBSan/independent predictions and scorer mutation checks pass; refreshing freshness.',flush=True)
    public,again,hidden,positive,private_sigs,clean=audit.refresh(root,private,root/AUDIT,bank['operands'],root/AUDIT/'candidate_signatures.txt')
    assert clean and again==eligible and not public
    out.mkdir(parents=True);save(out/'manifest.json',rows);jobs={}
    for job,(binary,sha) in BINS.items():
        target=out/('job-'+job);target.mkdir();selected=[r for r in rows if r['job']==job]
        with (target/'inputs.txt').open('x') as f:f.write(''.join(r['capture_line']+'\n' for r in selected))
        spec=dict(schema='x87-suite-v1',corpus_id='h1715-frozen-compound-boundaries',rows=len(selected),
            inputs_sha256=digest(target/'inputs.txt'),one_observation_maximum=True,retry_partial=False,
            freshness_audit_sha256=digest(root/AUDIT/'report.json'),binary_sha256=sha)
        save(target/'JOB.json',spec);jobs[job]=spec
    for name in ('suite.py','run_capture.py','capture_numeric.c'):
        with (out/name).open('x') as f:f.write((root/'corpus-suite'/name).read_text())
    save(out/'provenance.json',dict(audit_sha256=digest(root/AUDIT/'report.json'),selected_public_collisions=0,
        selected_private_possible_collisions=0,private_counts=dict(hidden),private_identities_contents_hashes_membership_lists_published=False))
    freeze=dict(experiment='h1715_compound_boundaries',capture_state='FROZEN_UNOPENED',frozen_utc=datetime.now(timezone.utc).isoformat(),
        unique_operands=len(ops),unique_capture_tuples=len(rows),jobs=jobs,scorer_preflight=preflight,independent_compiler_checks=checks,
        target_host='45.32.204.118',candidate_changed=False,paper_changed=False,instruction_retries=0,
        sha256=dict(manifest=digest(out/'manifest.json'),scorer=digest(Path(scorer.__file__)),suite=digest(Path(suite.__file__)),
            runner=digest(out/'run_capture.py'),freezer=digest(Path(__file__)),bank=digest(root/audit.BANK),
            evidence={**bank['sha256']['evidence'],AUDIT+'/report.json':digest(root/AUDIT/'report.json'),
                **{BUILD+'/'+name:digest(root/BUILD/name) for name in ('capture_numeric','capture_numeric_i586','capture.disassembly.txt','capture_i586.disassembly.txt')}}))
    save(out/'FREEZE.json',freeze)
    with (out/'CHECKSUMS.sha256').open('x') as f:
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name!='CHECKSUMS.sha256':f.write(f'{digest(path)}  {path.relative_to(out)}\n')
    print(json.dumps(dict(status='FROZEN_UNOPENED',operands=len(ops),tuples=len(rows),jobs={k:v['rows'] for k,v in jobs.items()},preflight=preflight)),flush=True)


if __name__=='__main__':main()
