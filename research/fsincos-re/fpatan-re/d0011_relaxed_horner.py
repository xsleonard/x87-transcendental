"""A nondeterministic retained-width supergraph, for exclusion only.

Every Horner operation may independently choose a format and operand read,
even differently for each input. This deliberately over-approximates a fixed
microcode schedule. An unreachable saved endpoint rejects the whole bounded
family; a reachable endpoint is NOT a candidate or a shared selector.
Identical exact state values are merged without dropping any reachable value.
"""
import collections
import argparse
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval
from d0011_terminal_preimage import Recipe,tail
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save

READS=('exact','chop64','rn64')
FORMATS=tuple(f'{m}{w}' for w in (64,67,69) for m in ('chop','rn'))


def reachable(z,u=None):
    if u is None:u=cut(z*z,'chop67')
    states={ROM[123]:[]};counts=[]
    for k in range(122,117,-1):
        products={}
        for h,path in states.items():
            for ur in READS:
                a=cut(u,ur)
                for hr in READS:
                    v=a*cut(h,hr)
                    for fmt in FORMATS:
                        p=cut(v,fmt)
                        if p not in products:products[p]=(path,dict(rom=k,square_read=ur,horner_read=hr,multiply=fmt))
        following={}
        for p,(path,operation) in products.items():
            for fmt in FORMATS:
                h=cut(ROM[k]+p,fmt)
                if h not in following:following[h]=path+[dict(**operation,add=fmt)]
        states=following;counts.append(dict(rom=k,products=len(products),states=len(states)))
    return states,counts


def expanded(data):
    # This audit does not use the fixed-square terminal prefilter. Square
    # production is itself nondeterministic, but its value is shared by the
    # Horner recurrence and the terminal products within each local witness.
    choices=list(itertools.product(READS,FORMATS+('exact',),FORMATS+('exact',),range(3)))
    failures=collections.Counter();reports=[]
    for index,(pair,t,band) in enumerate(data):
        z=t['z'];squares={}
        for left,right,fmt in itertools.product(READS,READS,FORMATS):
            u=cut(cut(z,left)*cut(z,right),fmt)
            squares.setdefault(u,dict(left_read=left,right_read=right,format=fmt))
        states={u:reachable(z,u) for u in squares};witnesses={}
        for number,(zr,first,last,order) in enumerate(choices):
            rz=cut(z,zr);found=None
            for u,(hs,counts) in states.items():
                for h,path in hs.items():
                    if order==0:tail_value=cut(cut(u*h,first)*rz,last)
                    elif order==1:tail_value=cut(cut(rz*h,first)*u,last)
                    else:tail_value=cut(cut(u*rz,first)*h,last)
                    v=z+tail_value
                    if band.contains(v):
                        found=dict(square=squares[u],u=str(u),h=str(h),operations=path,prevalue=str(v));break
                if found:break
            if found:witnesses[number]=found
            else:failures[number]+=1
        reports.append(dict(input=pair['rows'][0]['input'],z=str(z),interval=band.json(),
                            square_variants=len(squares),local_witnesses=witnesses))
        if (index+1)%16==0:print('expanded groups',index+1,'squares',len(squares),'local terminals',len(witnesses),flush=True)
    compatible=[i for i in range(len(choices)) if not failures[i]]
    save(BASE/'d0011-relaxed-horner-expanded.json',dict(status='RELAXED_SUPERGRAPH_NOT_A_SHARED_ALGORITHM',
        reads=READS,formats=FORMATS,square='same locally chosen square for Horner and tail',
        coefficients='unchanged public P5 ROM A118..123',groups=len(data),
        terminal_choices=[dict(z_read=z,first=f,last=l,order=o) for z,f,l,o in choices],
        failed_groups_by_terminal=dict(failures),inputwise_compatible_terminals=compatible,
        unreachable_groups=sum(not r['local_witnesses'] for r in reports),results=reports,hardware_executed=False))
    print('EXPANDED COMPLETE groups',len(data),'terminals',len(choices),'inputwise-compatible',len(compatible),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--expanded-square',action='store_true');args=ap.parse_args()
    data=[];seen=set()
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        raw=pair['raw'];t={};prevalue(*raw,trace=t)
        if t['kind']!='direct' or t['swap'] or raw[2]&32768:continue
        band=observation_interval(pair['rows']);key=(t['z'],band)
        if key in seen:continue
        seen.add(key);data.append((pair,t,band))
    if args.expanded_square:
        expanded(data);return
    preimage_report=json.loads((BASE/'d0011-terminal-preimage-expanded.json').read_text())
    recipes=[Recipe(**r['recipe']) for r in preimage_report['reports'] if r['impossible']==0]
    failures=collections.Counter();reports=[]
    for index,(pair,t,band) in enumerate(data):
        states,counts=reachable(t['z']);witnesses={}
        for p in recipes:
            for h,path in states.items():
                assert h<0
                if cut(h,'chop'+str(p.h_bits))!=h:continue
                v=t['z']-tail(t['z'],-h,p)
                if band.contains(v):
                    witnesses[p.name]=dict(h=str(h),operations=path,prevalue=str(v));break
            else:failures[p.name]+=1
        reports.append(dict(input=pair['rows'][0]['input'],z=str(t['z']),interval=band.json(),
                            state_counts=counts,local_witnesses=witnesses))
        if (index+1)%16==0:print('groups',index+1,'latest states',len(states),'local compatible terminals',len(witnesses),flush=True)
    impossible=[r for r in reports if not r['local_witnesses']]
    compatible=[p.name for p in recipes if not failures[p.name]]
    save(BASE/'d0011-relaxed-horner.json',dict(status='RELAXED_SUPERGRAPH_NOT_A_SHARED_ALGORITHM',
        reads=READS,formats=FORMATS,square='CHOP67(z*z)',coefficients='unchanged public P5 ROM A118..123',
        groups=len(data),terminal_recipes=[vars(p) for p in recipes],failed_groups_by_terminal=dict(failures),
        inputwise_compatible_terminal_names=compatible,unreachable_groups=len(impossible),results=reports,hardware_executed=False))
    print('COMPLETE groups',len(data),'unreachable under every terminal',len(impossible),
          'inputwise-compatible terminals',len(compatible),flush=True)


if __name__=='__main__':main()
