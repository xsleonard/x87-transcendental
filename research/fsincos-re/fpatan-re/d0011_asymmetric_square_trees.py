"""Static regroupings of the P5 polynomial with the MR64 square.

Every tree represents the same six-coefficient polynomial over exact reals.
The square and cubic-first tail follow the terminal feasibility discriminator;
retained-width operation roles are fixed per program, never per operand.
"""
import collections
import functools
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from d0010_expression_tree_audit import trees
from graph_v5 import prevalue
from model import F,ROM,cut
from prepare import save

COEFF=tuple(ROM[k] for k in range(118,124))


def main():
    alltrees=trees(63);assert len(alltrees)==945
    for u in (F(1,257),F(3,1024)):
        @functools.lru_cache(maxsize=None)
        def exact(t):
            if isinstance(t,int):return COEFF[t]
            k,a,b=t;return exact(a)+u**k*exact(b)
        want=sum(a*u**i for i,a in enumerate(COEFF))
        assert all(exact(t)==want for t in alltrees)
    rows=[];coords=[];ids={}
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']!='direct':continue
        z=t['z']
        if z not in ids:ids[z]=len(coords);coords.append(z)
        rows.append((pair,t,observation_interval(pair['rows']),ids[z]))
    rows.sort(key=lambda r:r[2].lo!=r[2].hi)
    reports=[];survivors=[];total=0
    choices=itertools.product(('exact','chop64','rn64'),('exact','chop64','rn64'),
            ('chop67','rn64'),('chop67','rn64'),('linear','balanced','dyadic'))
    for left,right,fmt,power_fmt,power_order in choices:
        def mul(a,b):return cut(cut(a,left)*cut(b,right),fmt)
        powers=[];cubes=[]
        for z in coords:
            u=cut(z*cut(z,'chop64'),'rn64');p=[F(1),u];cubes.append(cut(z*u,'chop67'))
            for k in range(2,6):
                if power_order=='linear':a,b=k-1,1
                elif power_order=='balanced':a=k//2;b=k-a
                else:a=1<<(k.bit_length()-1);a=a//2 if a==k else a;b=k-a
                p.append(cut(p[a]*p[b],power_fmt))
            powers.append(p)
        @functools.lru_cache(maxsize=100000)
        def evaluate(t,i):
            if isinstance(t,int):return COEFF[t]
            shift,a,b=t
            return cut(evaluate(a,i)+mul(powers[i][shift],evaluate(b,i)),'rn64')
        rejected=collections.Counter();examples=[]
        for tree_index,tree in enumerate(alltrees):
            total+=1
            for pair,t,band,i in rows:
                h=evaluate(tree,i);v=restore(t['z']+cut(cubes[i]*h,'chop67'),t,pair['raw'])
                if not band.contains(abs(v)):
                    line=pair['rows'][0]['input'];rejected[line]+=1
                    if len(examples)<3:examples.append(dict(tree_index=tree_index,input=line,prevalue=str(v)))
                    break
            else:
                r=dict(left_read=left,right_read=right,multiply=fmt,power_format=power_fmt,
                       power_order=power_order,tree=tree,tree_index=tree_index)
                survivors.append(r);print('DIRECT FRONTIER SURVIVOR',r,flush=True)
        reports.append(dict(left_read=left,right_read=right,multiply=fmt,power_format=power_fmt,
                            power_order=power_order,rejected=dict(rejected),examples=examples))
        evaluate.cache_clear()
        if len(reports)%12==0:print('trees tested',total,'survivors',len(survivors),flush=True)
    save(BASE/'d0011-asymmetric-square-trees.json',dict(status='STATIC_POLYNOMIAL_DISCOVERY_AUDIT',
        square='RN64(z*CHOP64(z))',tail='CHOP67(CHOP67(z*u)*H(u))',add='RN64',trees=len(alltrees),
        exact_identity='Every tree verified at two exact rational points',programs=total,
        survivors=survivors,policies=reports,hardware_executed=False))
    print('COMPLETE',total,'programs;',len(survivors),'direct frontier survivors',flush=True)


if __name__=='__main__':main()
