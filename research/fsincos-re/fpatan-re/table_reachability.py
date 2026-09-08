"""Analysis-only localize remaining errors; forced entries are NOT selectors.

Each forced entry is checked against every saved mode/sign/scale in the same
normalized pair. This script does not propose a mapping from operands to
entries. Global kernel cuts are additionally checked on the complete bank.
"""
import dataclasses
from graph_v3 import Program,prevalue
from table_stage_audit import groups,score,BASE
from prepare import save


def errors(s):return sum(v for k,v in s['counts'].items() if k.endswith('_misses'))


def main():
    data=groups();p=Program(direct_numerator=3,direct_limit=64)
    baseline=score(p,data);ids={m['id'] for m in baseline['misses']}
    targets={k:rows for k,rows in data.items() if any(i in ids for _,_,_,i in rows)}
    localized=[]
    for key,rows in targets.items():
        trace={};prevalue(*key,p,trace);n=trace['n'];tries=[]
        for alternative in sorted({0,max(1,n-1),n,min(32,n+1)}):
            result=score(dataclasses.replace(p,forced_index=alternative),{key:rows})
            tries.append(dict(n=alternative,counts=result['counts']))
        localized.append(dict(raw=[f'{v:x}' for v in key],index=n,tries=tries))
        print('entries',key,n,tries,flush=True)
    kernels=[]
    for k in ('chop68','chop69','chop70','chop72','rn68','rn69','rn70'):
        q=dataclasses.replace(p,kernel_cut=k);screen=score(q,targets)
        result=dict(kernel=k,screen=screen['counts'])
        if errors(screen)<errors(baseline):
            result['full']=score(q,data)
            print('kernel',k,result['full']['counts'],flush=True)
        kernels.append(result)
    save(BASE/'table-reachability.json',dict(status='CAUSAL_DISCOVERY_NOT_SELECTOR',
        forced_entry_trials=localized,kernels=kernels,hardware_executed=False))


if __name__=='__main__':main()
