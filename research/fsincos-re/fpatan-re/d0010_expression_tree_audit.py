"""Static polynomial expression trees, not input-dependent decision trees.

Enumerate canonical binary partitions of the seven coefficient positions
in u*(A1+...+A6*u**5), including the zero constant term. Each subtree is
normalized to its minimum exponent; its right child is scaled by a fixed
power. This includes Horner, split odd/even, and other regroupings. Exact
arithmetic identity is checked independently before retained-width scoring.
"""
import collections
import argparse
import functools
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from graph_v5 import prevalue
from model import F,ROM,cut
from prepare import save

COEFF=(F(0),)+tuple(ROM[k] for k in range(118,124))


@functools.lru_cache(maxsize=None)
def trees(mask):
    if mask&(mask-1)==0:return ((mask.bit_length()-1),)
    low=mask&-mask;out=[];sub=(mask-1)&mask
    while sub:
        other=mask^sub
        if sub&low and other:
            shift=(other&-other).bit_length()-low.bit_length()
            for a in trees(sub):
                for b in trees(other):out.append((shift,a,b))
        sub=(sub-1)&mask
    return tuple(out)


def exact_identity(alltrees):
    for u in (F(1,257),F(3,1024)):
        @functools.lru_cache(maxsize=None)
        def evaluate(t):
            if isinstance(t,int):return COEFF[t]
            k,a,b=t;return evaluate(a)+u**k*evaluate(b)
        expected=sum(c*u**i for i,c in enumerate(COEFF))
        assert all(evaluate(t)==expected for t in alltrees)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--additional-ports',action='store_true');args=ap.parse_args()
    alltrees=trees((1<<7)-1);assert len(alltrees)==10395;exact_identity(alltrees)
    rows=[];coordinates=[];ids={}
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*p['raw'],trace=t)
        if t['kind']!='direct':continue
        z=t['z']
        if z not in ids:ids[z]=len(coordinates);coordinates.append(z)
        rows.append((p['raw'],p['rows'][0]['input'],t,observation_interval(p['rows']),ids[z]))
    rows.sort(key=lambda r:r[3].lo!=r[3].hi)
    results=[];survivors=[];total=0
    ports=(('chop64','left'),('rn64','left'),('chop64','both'),('rn64','both')) if args.additional_ports else (
           ('chop64','right'),('rn64','right'),('exact','right'))
    for (narrow,side),square_source,power_order in itertools.product(ports,
                   ('wide','same-port','rn64'),('linear','balanced','dyadic')):
        def mul(a,b):
            ar=narrow if side in ('left','both') else 'chop67'
            br=narrow if side in ('right','both') else 'chop67'
            return cut(cut(a,ar)*cut(b,br),'chop67')
        powers=[]
        for z in coordinates:
            u=cut(z*z,'chop67') if square_source=='wide' else (cut(z*z,'rn64') if square_source=='rn64' else mul(z,z))
            p=[F(1),u]
            for i in range(2,7):
                if power_order=='linear':a,b=i-1,1
                elif power_order=='balanced':a=i//2;b=i-a
                else:a=1<<(i.bit_length()-1);a=a//2 if a==i else a;b=i-a
                p.append(mul(p[a],p[b]))
            powers.append(p)
        @functools.lru_cache(maxsize=250000)
        def evaluate(tree,index):
            if isinstance(tree,int):return COEFF[tree]
            shift,left,right=tree
            a=evaluate(left,index);b=mul(powers[index][shift],evaluate(right,index))
            # The zero coefficient is structural; omitting 0+b does not
            # introduce a predicate on an observed numerical error state.
            return b if left==0 else cut(a+b,'rn64')
        counts=collections.Counter();examples=[]
        for number,tree in enumerate(alltrees):
            total+=1
            for raw,line,t,band,index in rows:
                z=coordinates[index];k=z+mul(z,evaluate(tree,index));v=restore(k,t,raw)
                if not band.contains(abs(v)):
                    counts[line]+=1
                    if len(examples)<3:examples.append(dict(tree_index=number,input=line,prevalue=str(v)))
                    break
            else:
                r=dict(narrow=narrow,side=side,square_source=square_source,power_order=power_order,tree=tree,tree_index=number)
                survivors.append(r);print('DIRECT FRONTIER SURVIVOR',r,flush=True)
        results.append(dict(narrow=narrow,side=side,square_source=square_source,power_order=power_order,
                            rejected=dict(counts),examples=examples))
        print('policy',narrow,side,square_source,power_order,'tested',total,'survivors',len(survivors),flush=True)
        evaluate.cache_clear()
    dest='d0010-expression-tree-additional-ports.json' if args.additional_ports else 'd0010-expression-tree-audit.json'
    save(BASE/dest,dict(status='DIRECT_DISCOVERY_ONLY',programs=total,
         exact_polynomial_identity='PASS for every static tree at two rational arguments',trees=len(alltrees),
         policies=results,survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
