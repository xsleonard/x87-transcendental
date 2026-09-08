#!/usr/bin/env python3
"""Recheck fixed predictions and freshness, then freeze one-shot H1714 tuples."""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import h1714_rounding_challenge as challenge
import h1714_freshness as audit
import h1714_score_capture as scorer
from h1709_paired_retained_census import digest, save

AUDIT='tmp/ledger33/current/h1714_freshness'
CAPTURE='tmp/ledger33/current/h1712_capture_build/'
LOCKS={
    'capture-kit/x87_state_capture.c':'1b2df713deeb44576169c7f75e86a1365f92b6315da284280e8c76437588980b',
    CAPTURE+'x87_state_capture':'2a2adae7cf86348e78c6c5a3cd35c18762971b19542fdafcee52d9fabf369a82',
    CAPTURE+'capture.disassembly.txt':'f1e993faa6902739c73a4f595a8e870e49232a94cfb23a347daf353db9ce1eab',
    'paper/skylake-x87.tex':'f3b3371287510c834aa02c4f79e25990d2c4fb714c0b112d97bb21786ba5dec6',
    'paper/skylake-x87.pdf':'09c3192104cd0a2451d6c77388f3abb21129b39392756c1cacd6af1945b1f790',
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--private-ledger-dir',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();private=a.private_ledger_dir.resolve();out=a.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    for name,sha in LOCKS.items():assert digest(root/name)==sha,name
    bank=json.loads((root/audit.BANK).read_text());report=json.loads((root/AUDIT/'report.json').read_text())
    assert report['status']=='AUDITED_NOT_FROZEN' and digest(root/audit.BANK)==report['sha256']['bank']
    assert digest(Path(audit.__file__))==report['sha256']['script']
    assert digest(Path(audit.private_audit.__file__))==report['sha256']['private_scanner']
    assert digest(Path(audit.matches.__code__.co_filename))==report['sha256']['scanner']
    assert digest(Path(challenge.__file__))==bank['sha256']['script']
    for name,sha in bank['sha256']['evidence'].items():assert digest(root/name)==sha,name
    assert digest(root/'tmp/ledger33/current/h1714_rounding_challenge/boundary_certificate.json')==bank['sha256']['certificate']
    # Existing pinned disassembly has one opcode site per instruction. Each
    # is followed immediately by FWAIT and the common FXSAVE block. No target
    # opcode executes during this read-only preflight.
    instructions=[]
    for line in (root/CAPTURE/'capture.disassembly.txt').read_text().splitlines():
        fields=line.split('\t')
        if len(fields)>=3 and re.fullmatch(r'\s*[0-9a-f]+:',fields[0]):instructions.append(fields[2].strip())
    for insn in challenge.INSTRUCTIONS:
        sites=[i for i,s in enumerate(instructions) if s==insn];assert len(sites)==1
        assert instructions[sites[0]+1]=='fwait'
    eligible=report['eligible'];ops=[r['operand'] for r in eligible];assert len(ops)==len(set(ops))==1526
    challenge.independent.constants(root);cache={};manifests=[]
    binaries=[root/'src/fsincos_skylake',root/'tmp/ledger33/current/h1713_promotion_checks_v2/ubsan']
    software_checks=0
    for insn in challenge.INSTRUCTIONS:
        for mode in challenge.MODES:
            reference=[challenge.prediction(op,insn,mode,cache) for op in ops]
            assert reference==[row['predictions'][insn][mode] for row in eligible]
            for binary in binaries:
                assert challenge.c_predictions(binary,insn,mode,ops)==reference
                software_checks+=len(ops)
    for row in eligible:
        for insn in challenge.INSTRUCTIONS:
            for mode in challenge.MODES:
                for pc in (24,53,64):
                    case=f'A{len(manifests)+1:05d}'
                    manifests.append(dict(case_id=case,instruction=insn,mode=mode,pc=pc,operand=row['operand'],
                        kinds=row['kinds'],prediction=row['predictions'][insn][mode],capture_state='FROZEN_UNOPENED',
                        capture_line=f'{case} {insn} {mode} pc{pc} 3f 1 clear {row["operand"]}'))
    assert len(manifests)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in manifests})==54936
    preflight=scorer.preflight(manifests)
    print('Independent/default/UBSan predictions and scorer mutations pass; refreshing local freshness.',flush=True)
    public,again,hidden,positive,private_sigs,clean=audit.refresh(root,private,root/AUDIT,bank['operands'],root/AUDIT/'candidate_signatures.txt')
    assert clean and again==eligible and len(public)==report['rejected_public_significands']
    runner=(root/'experiments/h1712_run_capture.sh').read_text().replace('H1712','H1714').replace('paired tuples','three-instruction rounding-boundary tuples').replace('13800','54936')
    out.mkdir(parents=True)
    save(out/'manifest.json',manifests)
    with (out/'inputs.txt').open('x') as f:f.write(''.join(r['capture_line']+'\n' for r in manifests))
    with (out/'run_capture.sh').open('x') as f:f.write(runner)
    provenance=dict(source_audit_sha256=digest(root/AUDIT/'report.json'),public_rejected_significands=len(public),
        selected_public_collisions=0,selected_private_possible_collisions=0,private_counts=dict(hidden),
        private_identities_contents_hashes_membership_lists_published=False,
        public_excluded_software_directories=[*audit.SOFTWARE,AUDIT],limits=report['limits'],policy=report['policy'])
    save(out/'provenance.json',provenance)
    evidence={**LOCKS,**bank['sha256']['evidence'],audit.BANK:digest(root/audit.BANK),
        AUDIT+'/report.json':digest(root/AUDIT/'report.json')}
    freeze=dict(experiment='h1714_rounding_boundaries',capture_state='FROZEN_UNOPENED',
        frozen_utc=datetime.now(timezone.utc).isoformat(),unique_operands=len(ops),unique_capture_tuples=len(manifests),
        target_host='45.32.204.118',target_cpu=dict(family=6,model=85),capture_binary_sha256=LOCKS[CAPTURE+'x87_state_capture'],
        one_observation_maximum_per_tuple=True,instruction_retries=0,candidate_changed=False,paper_changed=False,
        scorer_preflight=preflight,independent_compiler_checks=software_checks,
        kind_memberships=dict(Counter(k for r in eligible for k in r['kinds'])),
        claim_boundary='Fixed promoted graph, targeted final-rounding brackets and modular residual lifts. All RC and PC24/53/64, not exhaustive silicon or physical uniqueness.',
        sha256=dict(evidence=evidence,manifest=digest(out/'manifest.json'),inputs=digest(out/'inputs.txt'),
            provenance=digest(out/'provenance.json'),runner=digest(out/'run_capture.sh'),
            scorer=digest(Path(scorer.__file__)),parser=digest(Path(scorer.parse.__code__.co_filename)),
            freezer=digest(Path(__file__)),compiler_binaries={str(b.relative_to(root)):digest(b) for b in binaries}))
    save(out/'FREEZE.json',freeze)
    with (out/'CHECKSUMS.sha256').open('x') as f:
        for name in ('FREEZE.json','manifest.json','inputs.txt','provenance.json','run_capture.sh'):f.write(f'{digest(out/name)}  {name}\n')
    print(json.dumps(dict(status='FROZEN_UNOPENED',operands=len(ops),tuples=len(manifests),preflight=preflight)),flush=True)


if __name__=='__main__':main()
