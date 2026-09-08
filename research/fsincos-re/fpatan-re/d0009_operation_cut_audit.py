"""Global operation-result cuts and multiplication order, saved data only.

ROM-role choices are evaluated again with the corrected short table set;
the earlier D0008 output-cut search had incorrectly used long coefficients
everywhere. This is a bounded graph-family test, not an exception classifier.
"""
import itertools
import json
from d0009_kernel_audit import BASE
from d0008_operand_format_audit import restore
from graph_v5 import prevalue
from model import F,ROM,cut,encode,value
from prepare import save


def kernel(z,domain,t,sc,first,last,order,read,add):
    short=t['kind']=='table' if domain=='table' else (domain=='short' or
          (domain in ('64','32') and abs(z)<F(1,int(domain))))
    low,high=(114,117) if short else (118,123)
    u=cut(z*z,sc);h=ROM[high]
    for k in range(high-1,low-1,-1):h=cut(ROM[k]+cut(u*h,'chop67'),add if k==low else 'rn64')
    rz=cut(z,read)
    if order=='square-h-z':tail=cut(cut(u*h,first)*rz,last)
    elif order=='z-h-square':tail=cut(cut(rz*h,first)*u,last)
    else:tail=cut(cut(u*rz,first)*h,last)
    return z+tail


def main():
    data=[]
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*p['raw'],trace=t);data.append((p['raw'],p['rows'],t))
    results=[];survivors=[];cuts=('chop67','rn64','rn67','chop64','exact')
    for args in itertools.product(('table','long','short','64','32'),cuts,cuts,cuts,
            ('square-h-z','z-h-square','square-z-h'),('exact','rn64','chop64'),('rn64','chop67','rn67')):
        domain,sc,first,last,order,read,add=args;cache={};failure=None;tested=0
        for raw,rows,t in data:
            key=(t['z'],t['kind']=='table')
            if key not in cache:cache[key]=kernel(t['z'],domain,t,sc,first,last,order,read,add)
            before=restore(cache[key],t,raw[0],raw[2])
            for row in rows:
                se,sig=encode(before,row['rc']);c1=int(abs(value(se,sig))>abs(before));tested+=1
                if (se,sig,c1)!=(row['se'],row['sig'],row['C1']):
                    failure=dict(input=row['input'],predicted=[se,sig,c1],observed=[row['se'],row['sig'],row['C1']],tested_rows=tested);break
            if failure:break
        r=dict(coefficient_domain=domain,square=sc,tail_first=first,tail_second=last,
               tail_order=order,z_read=read,last_add=add,counterexample=failure)
        results.append(r)
        if failure is None:survivors.append(r);print('TARGET SURVIVOR',r,flush=True)
    print('programs',len(results),'survivors',len(survivors),flush=True)
    save(BASE/'d0009-operation-cut-audit.json',dict(status='TARGET_SCREEN_ONLY',results=results,survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
