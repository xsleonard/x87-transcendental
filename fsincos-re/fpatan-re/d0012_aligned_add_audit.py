"""Literal fixed-point operand alignment before a narrow Horner add read.

The alignment width, discarded-bit handling and consumer read are fixed
per program. No comparison uses a known miss, operand ID or fitted boundary.
These are arithmetic hypotheses, not recovered physical control signals.
"""
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from graph_v5 import prevalue
from model import F,ROM,cut,exponent,pow2
from prepare import save


def fixed(v,unit,mode):
    if not v:return v
    sign=-1 if v<0 else 1;q=abs(v)/unit;n,r=divmod(q.numerator,q.denominator)
    if mode=='away':n+=bool(r)
    elif mode=='rn':n+=2*r>q.denominator or (2*r==q.denominator and n&1)
    elif mode=='odd':n|=int(bool(r))
    else:assert mode=='chop'
    return sign*n*unit


def add(a,b,width,mode,both,read):
    unit=pow2(max(exponent(a),exponent(b))-width+1)
    # The polynomial coefficient is the larger operand on this direct
    # domain. Preserve it exactly or explicitly align both source operands.
    assert abs(a)>abs(b)
    aa=fixed(a,unit,mode) if both else a
    return cut(aa+fixed(b,unit,mode),read)


def main():
    rows=[]
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']=='direct':rows.append((pair,t,observation_interval(pair['rows'])))
    rows.sort(key=lambda r:r[2].lo!=r[2].hi)
    results=[];survivors=[]
    for kind,width,mode,both,read,scope in itertools.product(('V4','V5','MR'),range(64,74),
            ('chop','rn','away','odd'),(False,True),('chop64','rn64'),('all','last')):
        failures=[];cache={}
        for pair,t,band in rows:
            z=t['z']
            if z not in cache:
                u=cut(z*cut(z,'chop64'),'rn64') if kind=='MR' else cut(z*z,'chop67')
                h=ROM[123]
                for k in range(122,117,-1):
                    product=cut(u*h,'chop67')
                    h=add(ROM[k],product,width,mode,both,read) if scope=='all' or k==118 else cut(ROM[k]+product,'rn64')
                tail=cut(cut(z*u,'chop67')*h,'chop67') if kind=='MR' else cut(cut(u*h,'chop67')*cut(z,'chop64' if kind=='V5' else 'exact'),'chop67')
                cache[z]=z+tail
            v=restore(cache[z],t,pair['raw'])
            if not band.contains(abs(v)):failures.append(pair['rows'][0]['input'])
        recipe=dict(template=kind,width=width,alignment_mode=mode,align_both=both,read=read,scope=scope)
        r=dict(recipe=recipe,failed_groups=len(failures),counterexample=failures[0] if failures else None);results.append(r)
        if not failures:survivors.append(r);print('DIRECT DISCOVERY SURVIVOR',recipe,flush=True)
    save(BASE/'d0012-aligned-add-audit.json',dict(status='FIXED_ALIGNMENT_DIRECT_DISCOVERY_AUDIT',
        groups=len(rows),programs=len(results),survivors=survivors,results=results,hardware_executed=False))
    print('COMPLETE',len(results),'programs;',len(survivors),'direct survivors',flush=True)
    print('best',sorted(results,key=lambda r:r['failed_groups'])[:3],flush=True)


if __name__=='__main__':main()
