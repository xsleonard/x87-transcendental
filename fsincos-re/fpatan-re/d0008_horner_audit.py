"""Operation-role Horner precision and forced-entry causal diagnostics."""
import dataclasses
import itertools
from d0008_frontier_audit import targets,score,BASE
from graph_v4 import PROGRAM
from graph_v3 import prevalue
from prepare import save


def main():
    data=targets();results=[]
    for add,last,mul in itertools.product(('rn64','chop67','rn67','exact'),
            ('rn64','chop64','rn65','chop65','rn67','chop67','exact'),('chop67','rn64','rn67','exact')):
        results.append(score(dataclasses.replace(PROGRAM,add=add,last_add=last,last_multiply=mul),data))
    results.sort(key=lambda r:r['counts']['output_misses']+r['counts']['C1_misses'])
    zero=[r for r in results if not (r['counts']['output_misses'] or r['counts']['C1_misses'])]
    entries=[]
    for key,rows in data.items():
        t={};prevalue(*key,PROGRAM,t);n=t['n'];trials=[]
        for a in sorted({0,max(1,n-1),max(1,n),min(32,n+1)}):
            trials.append(dict(index=a,counts=score(dataclasses.replace(PROGRAM,forced_index=a),{key:rows})['counts']))
        entries.append(dict(raw=key,nominal=n,trials=trials))
    print('programs',len(results),'target-exact',len(zero))
    for r in results[:8]:print(r['counts'],{k:r['program'][k] for k in ('add','last_add','last_multiply')})
    print('forced-entry trials',entries)
    save(BASE/'d0008-horner-audit.json',dict(status='TARGET_SCREEN_ONLY',results=results,zero_target_misses=zero,forced_entries=entries,hardware_executed=False))


if __name__=='__main__':main()
