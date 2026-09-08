#!/usr/bin/env python3
"""Score sealed one-shot results from both CPUs; never execute hardware."""
import argparse
import json
from collections import Counter
from pathlib import Path
import h1715_score_capture as base
import suite


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();kit=a.kit.resolve();out=a.output_dir.resolve()
    freeze=json.loads((kit/'FREEZE.json').read_text())
    for key,path in [('manifest',kit/'manifest.json'),('scorer',Path(__file__)),('base_scorer',Path(base.__file__)),('suite',Path(suite.__file__))]:
        assert suite.digest(path)==freeze['sha256'][key],key
    rows=json.loads((kit/'manifest.json').read_text());assert len(rows)==freeze['tuples_per_CPU']
    assert base.preflight(rows)==freeze['scorer_preflight']
    reports={};misses=[];outputs={}
    for host in ('i7','skylake'):
        run=kit/('run-'+host);done=json.loads((run/'COMPLETE.json').read_text())
        assert done['status']=='OPENED_ONCE_DO_NOT_RERUN' and done['rows']==len(rows) and not done['instruction_retries']
        for key,name in [('outputs_sha256','outputs.txt'),('inputs_sha256','inputs.txt'),('cpu_sha256','cpu.json'),('cpu_after_sha256','cpu-after.json')]:
            assert suite.digest(run/name)==done[key],(host,key)
        assert done['inputs_sha256']==freeze['job']['inputs_sha256'] and done['binary_sha256']==freeze['job']['binary_sha256']
        cpu=json.loads((run/'cpu.json').read_text());after=json.loads((run/'cpu-after.json').read_text())
        assert cpu['context_id']==after['context_id'] and cpu['affinity_pinned'] and done['affinity_pinned']
        assert (cpu['context']['family'],cpu['context']['model'],cpu['context']['stepping'])==((6,94,3) if host=='i7' else (6,85,4))
        counts=Counter();matrix=Counter();values=[]
        with (run/'outputs.txt').open() as stream:
            for row in rows:
                line=next(stream);fields=suite.parse_numeric(line);result=base.checks(row,fields)
                counts['instruction_rows']+=1;matrix[row['instruction'],row['mode'],row['pc']]+=1
                for key,passed in result.items():counts[key+'_checks']+=1;counts[key+'_misses']+=not passed
                if not all(result.values()):misses.append(dict(host=host,row=row,checks=result,raw=line.strip()))
                if row.get('policy1_prediction') is not None:
                    counterfactual=dict(row,prediction=row['policy1_prediction'])
                    old=base.checks(counterfactual,fields)
                    counts['policy1_counterfactual_rows']+=1
                    counts['policy1_counterfactual_misses']+=not all(old.values())
                values.append((fields['SIN'],fields['COS'],int(fields['A_SW'],16)&0x600))
            assert not stream.readline()
        outputs[host]=values
        reports[host]=dict(cpu=cpu,counts=dict(counts),
            matrix=[dict(instruction=i,mode=r,pc=p,rows=n) for (i,r,p),n in sorted(matrix.items())],
            sha256=dict(complete=suite.digest(run/'COMPLETE.json'),raw=done['outputs_sha256'],cpu=done['cpu_sha256']))
    disagreements=sum(x!=y for x,y in zip(outputs['i7'],outputs['skylake']))
    report=dict(status='PASS_FROZEN_TWO_CPU_ADVERSARIAL' if not misses and not disagreements else 'FROZEN_MODEL_OR_CROSS_CPU_DISAGREEMENT',
        unique_operands=freeze['unique_operands'],unique_observations_across_two_CPU_contexts=2*len(rows),
        miss_count=len(misses),cross_CPU_output_C1_C2_disagreements=disagreements,hosts=reports,
        prediction_protocol='Independent integer/rational and C/UBSan agreement before labels; fixed algorithm.',
        candidate_changed=False,paper_changed=False,instruction_retries=0,
        limits='Strong finite adversarial evidence, not exhaustive raw80 or cross-generation proof. Xeon is a reported virtualized CPUID.',
        sha256=dict(freeze=suite.digest(kit/'FREEZE.json'),scorer=suite.digest(Path(__file__))))
    out.mkdir(parents=True,exist_ok=False);suite.save(out/'misses.json',misses);suite.save(out/'report.json',report)
    suite.save(kit/'OPENED.json',dict(status='OPENED_ONCE_DO_NOT_RERUN',instruction_retries=0,
        sha256=dict(freeze=suite.digest(kit/'FREEZE.json'),score=suite.digest(out/'report.json'),misses=suite.digest(out/'misses.json'))))
    print(json.dumps({k:report[k] for k in ('status','unique_operands','unique_observations_across_two_CPU_contexts','miss_count','cross_CPU_output_C1_C2_disagreements')}),flush=True)


if __name__=='__main__':main()
