"""Causal arithmetic ablations for the remaining table-path discrepancies.

Enumerate global operation widths, first against the incumbent's failing
operand groups, then against every non-small opened control for any survivor.
The partial screening score is explicitly separate from the full score.
"""
import collections
import dataclasses
import itertools
from graph_v3 import Program,prevalue
from table_stage_audit import groups,score,BASE
from model import encode,value
from prepare import save


def main():
    data=groups();base=Program(direct_numerator=3,direct_limit=64)
    baseline=score(base,data);target_ids={m['id'] for m in baseline['misses']}
    targets={k:rows for k,rows in data.items() if any(i in target_ids for _,_,_,i in rows)}
    programs=[dataclasses.replace(base,numerator=n,denominator=d,table_divider=v)
        for n,d,v in itertools.product(('chop67','rn67','rn64','exact'),
            ('chop67','rn67','rn64','exact'),('chop67','rn67','rn64','exact'))]
    programs.extend(dataclasses.replace(base,kernel_cut=k) for k in ('chop67','rn67','rn64'))
    results=[]
    for p in programs:
        screened=score(p,targets)
        errors=sum(v for k,v in screened['counts'].items() if k.endswith('_misses'))
        result={'program':screened['program'],'screen_counts':screened['counts']}
        if errors<=12:
            full=score(p,data);result['full']=full
            print('FULL',p.numerator,p.denominator,p.table_divider,p.kernel_cut,full['counts'],flush=True)
        results.append(result)
    save(BASE/'reduction-stage-audit.json',dict(status='DISCOVERY_ONLY',
        baseline=baseline,target_operand_groups=len(targets),results=results,
        hardware_executed=False,screen_rule='full score only when output+C1 target errors <= 12'))


if __name__=='__main__':main()
