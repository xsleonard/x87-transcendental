"""Couple fixed operand alignment with square and tail producer/read roles.

All choices are global program parameters. This composes the new alignment
operation with staged squares rather than fitting a selector to its misses.
"""
import functools
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from d0012_staged_format_audit import READS,NARROW,pipe
from d0012_aligned_add_audit import add
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save


def main():
    data=[]
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']=='direct':data.append((pair,t,observation_interval(pair['rows'])))
    data.sort(key=lambda r:r[2].lo!=r[2].hi)
    @functools.lru_cache(maxsize=100000)
    def prefix(z,sr,sq,width,mode,both,read):
        u=pipe(z*pipe(z,sr),sq);h=ROM[123]
        for k in range(122,117,-1):h=add(ROM[k],cut(u*h,'chop67'),width,mode,both,read)
        return u,h
    results=[];survivors=[]
    choices=itertools.product(READS,NARROW,range(64,71),('chop','rn','away','odd'),
        (False,True),('chop64','rn64'),READS,('chop67','rn64','chop67>rn64'),range(3))
    for number,(sr,sq,width,mode,both,read,zread,first,order) in enumerate(choices):
        failure=None;tested=0
        for pair,t,band in data:
            z=t['z'];u,h=prefix(z,sr,sq,width,mode,both,read);rz=pipe(z,zread)
            if order==0:tail=cut(pipe(u*h,first)*rz,'chop67')
            elif order==1:tail=cut(pipe(rz*h,first)*u,'chop67')
            else:tail=cut(pipe(rz*u,first)*h,'chop67')
            v=restore(z+tail,t,pair['raw']);tested+=1
            if not band.contains(abs(v)):
                failure=dict(input=pair['rows'][0]['input'],prevalue=str(v),interval=band.json());break
        recipe=dict(square_read=sr,square=sq,alignment_width=width,alignment_mode=mode,
            align_both=both,add_read=read,tail_z_read=zread,tail_first=first,tail_order=order)
        r=dict(recipe=recipe,tested_groups=tested,counterexample=failure);results.append(r)
        if failure is None:survivors.append(r);print('DIRECT DISCOVERY SURVIVOR',recipe,flush=True)
        if (number+1)%10000==0:print('tested',number+1,'survivors',len(survivors),flush=True)
    save(BASE/'d0012-aligned-datapath-audit.json',dict(status='FIXED_ALIGNED_DATAPATH_DISCOVERY_AUDIT',
        programs=len(results),groups=len(data),survivors=survivors,results=results,hardware_executed=False))
    print('COMPLETE',len(results),'programs;',len(survivors),'direct survivors',flush=True)


if __name__=='__main__':main()
