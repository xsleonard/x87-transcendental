"""Direct-kernel constant-read and output-cut audit; no selector fitting."""
import itertools
import json
from d0009_kernel_audit import BASE
from d0008_operand_format_audit import restore
from graph_v5 import prevalue
from model import ROM,cut,encode,value
from prepare import save


def main():
    data=[]
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*p['raw'],trace=t)
        if t['kind']=='direct':data.append((p['raw'],p['rows'],t))
    results=[];survivors=[]
    for fmt,which,sc,mul,add,first,last,zread,order in itertools.product(
            ('rn64','chop64','exact'),('all','last'),('chop67','rn64','chop64'),
            ('chop67','rn64'),('rn64','chop67'),('chop67','rn64','chop64'),
            ('chop67','rn64'),('exact','rn64','chop64'),('square-h-z','square-z-h')):
        cache={};failure=None;tested=0
        for raw,rows,t in data:
            z=t['z']
            if z not in cache:
                u=cut(z*z,sc);h=cut(ROM[123],fmt) if which=='all' else ROM[123]
                for k in range(122,117,-1):
                    a=cut(ROM[k],fmt) if which=='all' or k==118 else ROM[k]
                    h=cut(a+cut(u*h,mul),add)
                rz=cut(z,zread)
                tail=cut(cut(u*h,first)*rz,last) if order=='square-h-z' else cut(cut(u*rz,first)*h,last)
                cache[z]=z+tail
            before=restore(cache[z],t,raw[0],raw[2])
            for row in rows:
                se,sig=encode(before,row['rc']);c1=int(abs(value(se,sig))>abs(before));tested+=1
                if (se,sig,c1)!=(row['se'],row['sig'],row['C1']):
                    failure=dict(input=row['input'],predicted=[se,sig,c1],observed=[row['se'],row['sig'],row['C1']],tested_rows=tested);break
            if failure:break
        r=dict(rom_read=fmt,which_coefficients=which,square=sc,multiply=mul,add=add,tail_first=first,
               tail_second=last,z_read=zread,tail_order=order,counterexample=failure)
        results.append(r)
        if failure is None:survivors.append(r);print('TARGET SURVIVOR',r,flush=True)
    print('programs',len(results),'direct survivors',len(survivors),flush=True)
    save(BASE/'d0009-rom-read-audit.json',dict(status='DIRECT_TARGET_SCREEN_ONLY',results=results,survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
