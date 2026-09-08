#!/usr/bin/env python3
"""Recheck fixed predictions/provenance and freeze the one-shot paired challenge."""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import h1710_verify_paired_program as independent
import h1712_paired_freshness as audit
import h1712_score_paired_capture as scorer
from h1709_paired_retained_census import digest, save

AUDIT = 'tmp/ledger33/current/h1712_paired_freshness'
LOCKS = {
    AUDIT+'/report.json':'2555145dca2c419b94734b281e7f4b5ea39f4e547c171a87995355f9dcb9197f',
    audit.BANK:'236dab47e446c825e4d2c777eb276179d2c9fd21beb92c8c0ad1aa046cf04da1',
    'capture-kit/x87_state_capture.c':'1b2df713deeb44576169c7f75e86a1365f92b6315da284280e8c76437588980b',
    'tmp/ledger33/current/h1712_capture_build/x87_state_capture':'2a2adae7cf86348e78c6c5a3cd35c18762971b19542fdafcee52d9fabf369a82',
    'tmp/ledger33/current/h1712_capture_build/capture.disassembly.txt':'f1e993faa6902739c73a4f595a8e870e49232a94cfb23a347daf353db9ce1eab',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path); p.add_argument('--private-ledger-dir', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root=a.root.resolve(); private=a.private_ledger_dir.resolve(); out=a.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    for name, sha in LOCKS.items(): assert digest(root / name) == sha, name
    report=json.loads((root / AUDIT / 'report.json').read_text()); bank=json.loads((root / audit.BANK).read_text())
    assert report['status']=='AUDITED_NOT_FROZEN' and digest(root / audit.BANK)==report['sha256']['bank']
    assert digest(Path(audit.__file__))==report['sha256']['script']
    assert digest(Path(audit.private_audit.__file__))==report['sha256']['private_scanner']
    assert digest(Path(audit.matches.__code__.co_filename))==report['sha256']['scanner']
    for name, sha in bank['sha256']['evidence'].items(): assert digest(root/name)==sha,name
    assert digest(Path(independent.__file__))==bank['sha256']['verifier']
    # The pinned compiler emitted one FSINCOS site, then FWAIT and FXSAVE.
    # No warmup, timing loop, or second target instruction is used per row.
    disassembly=(root/'tmp/ledger33/current/h1712_capture_build/capture.disassembly.txt').read_text()
    instructions=[]
    for line in disassembly.splitlines():
        fields=line.split('\t')
        if len(fields)>=3 and re.fullmatch(r'\s*[0-9a-f]+:',fields[0]): instructions.append(fields[2].strip())
    sites=[i for i,s in enumerate(instructions) if s=='fsincos']; assert len(sites)==1
    pos=sites[0]; assert instructions[pos+1]=='fwait'
    sequence=instructions[pos+2:pos+8]
    assert sequence[-1].startswith('fxsave ') and not any(re.match(r'f(?!xsave)',s) for s in sequence)
    eligible=report['eligible']; ops=[r['operand'] for r in eligible]
    assert len(ops)==len(set(ops))==1150
    independent.constants(root); cache={}; manifests=[]
    primary_report=json.loads((root/'tmp/ledger33/current/h1710_independent_paired_program/report.json').read_text())
    for policy in ('baseline','last','all'):
        binary=root/'tmp/ledger33/current/h1710_independent_paired_program'/(policy+'_O2')
        assert digest(binary)==primary_report['sha256']['binaries'][binary.name]
        for mode in ('rn','rd','ru','rz'):
            values,meta=independent.run(binary,mode,ops,True)
            for i,row in enumerate(eligible):
                value,metadata=independent.expected(row['operand'],mode,policy,cache)
                assert (values[i],meta.get(i))==(value,metadata)
                expected=dict(outputs=list(value) if value else None,path=metadata[0] if metadata else 'range',
                    C1=metadata[3] if metadata and metadata[1] else None)
                assert row['predictions'][policy][mode]==expected
    for row in eligible:
        for mode in ('rn','rd','ru','rz'):
            for pc in (24,53,64):
                case=f'P{len(manifests)+1:05d}'
                manifests.append(dict(row,case_id=case,instruction='fsincos',mode=mode,pc=pc,
                    capture_state='FROZEN_UNOPENED',capture_line=f'{case} fsincos {mode} pc{pc} 3f 1 clear {row["operand"]}'))
    assert len(manifests)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in manifests})==13800
    preflight=scorer.preflight(manifests)
    print('Predictions and scorer preflight pass; refreshing public/private freshness immediately before freeze.',flush=True)
    patterns=root/AUDIT/'candidate_signatures.txt'
    public=audit.matches(root,patterns,[private,root/AUDIT,*(root/name for name in audit.SOFTWARE)])
    assert len(public)==report['rejected_public_significands']
    assert not {op.split()[1] for op in ops}&public
    assert not audit.matches(private,patterns,[])
    hidden,positive=audit.private_audit.inspect(private,set(ops))
    assert not positive and not hidden['numeric_parse_failures'] and not hidden['long_numeric_tokens_unparsed']
    out.mkdir(parents=True)
    save(out/'manifest.json',manifests)
    with (out/'inputs.txt').open('x') as stream: stream.write(''.join(r['capture_line']+'\n' for r in manifests))
    with (out/'run_capture.sh').open('x') as stream: stream.write((root/'experiments/h1712_run_capture.sh').read_text())
    provenance=dict(source_audit_sha256=digest(root/AUDIT/'report.json'),
        public_rejected_significands=len(public),selected_public_collisions=0,selected_private_possible_collisions=0,
        private_counts=dict(hidden),private_identities_contents_hashes_membership_lists_published=False,
        public_excluded_software_directories=[*audit.SOFTWARE,AUDIT],limits=report['limits'],policy=report['policy'])
    save(out/'provenance.json',provenance)
    freeze=dict(experiment='h1712_paired_materialization',capture_state='FROZEN_UNOPENED',
        frozen_utc=datetime.now(timezone.utc).isoformat(),unique_operands=len(ops),unique_capture_tuples=len(manifests),
        target_host='45.32.204.118',target_cpu=dict(family=6,model=85),
        capture_binary_sha256=LOCKS['tmp/ledger33/current/h1712_capture_build/x87_state_capture'],
        one_observation_maximum_per_tuple=True,instruction_retries=0,candidate_changed=False,scorer_preflight=preflight,
        kind_memberships=dict(Counter(k for r in eligible for k in r['kinds'])),
        discriminator_operands=sum(bool(r['discriminator_modes']) for r in eligible),
        claim_boundary='Fixed paired minimal/all-edge and archived predictions. All-RC/PC24,53,64 prospective domain/discriminator tests, not exhaustive or physical-circuit proof.',
        sha256=dict(evidence={**LOCKS,**bank['sha256']['evidence']},manifest=digest(out/'manifest.json'),
            inputs=digest(out/'inputs.txt'),provenance=digest(out/'provenance.json'),runner=digest(out/'run_capture.sh'),
            scorer=digest(Path(scorer.__file__)),freezer=digest(Path(__file__))))
    save(out/'FREEZE.json',freeze)
    with (out/'CHECKSUMS.sha256').open('x') as stream:
        for name in ('FREEZE.json','manifest.json','inputs.txt','provenance.json','run_capture.sh'):
            stream.write(f'{digest(out/name)}  {name}\n')
    print(json.dumps(dict(status='FROZEN_UNOPENED',operands=len(ops),tuples=len(manifests),scorer_preflight=preflight)),flush=True)


if __name__=='__main__': main()
