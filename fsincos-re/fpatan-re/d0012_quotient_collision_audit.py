"""Search saved hardware for different ratios with an identical C67 lead.

Only normal, unrotated direct-path PC64 cases are compared, with negative-y
rounding modes reflected to positive magnitude. Original observations are
authenticated. This tests whether discarded quotient bits are observable;
it does not fit any arithmetic correction or execute hardware.
"""
import collections
import hashlib
import itertools
import json
import math
from fractions import Fraction
from d0010_causal_intervals import BASE
from d0008_schedule_replay import opened,digest
from protocol import validate_output
from prepare import save


def main():
    groups={};counts=collections.Counter();conflicts=[];sources=[]
    for number in range(1,10):
        job=BASE/f'd{number:04d}';m=json.loads((job/'MANIFEST.json').read_text());c=json.loads((job/'COMPLETE.json').read_text())
        assert digest(job/'MANIFEST.json')==c['manifest_sha256']
        compressed=m.get('format')=='fpatan-gzip-v2';inp=job/('inputs.txt.gz' if compressed else 'inputs.txt')
        hw=job/('hardware.txt.gz' if compressed else 'hardware.txt');assert digest(inp)==m['files'][inp.name]
        sha=hashlib.sha256();total=0
        with opened(inp) as inputs,opened(hw) as hardware:
            for line,out in itertools.zip_longest(inputs,hardware):
                assert line is not None and out is not None
                total+=1;sha.update(out.encode());actual=validate_output(out,line);t=line.split()
                if t[2]!='64':continue
                ys,ym,xs,xm=(int(v,16) for v in t[3:]);ye,xe=ys&32767,xs&32767
                if xs&32768 or not (0<ye<32767 and 0<xe<32767) or min(ym,xm)<1<<63:continue
                d=ye-xe;e=d-int(ym<xm)
                if not -40<=e<=-5:continue
                if d>=0 or 64*ym>=3*xm*(1<<(-d)):continue
                q=(ym<<(66+d-e))//xm;key=(q,e)
                assert 1<<66<=q<1<<67
                ratio=Fraction(ym,xm*(1<<(-d)))
                rc=t[1]
                if ys&32768:rc={'rd':'ru','ru':'rd'}.get(rc,rc)
                value=(actual['se']&32767,actual['sig'],actual['C1'])
                counts['selected_rows']+=1
                if key not in groups:groups[key]=dict(ratios=set(),modes={},first=line.strip())
                g=groups[key];g['ratios'].add(ratio)
                if rc in g['modes']:
                    old=g['modes'][rc]
                    if old['value']!=value:
                        conflicts.append(dict(lead_significand=q,lead_exponent=e,mode=rc,
                            first_input=old['input'],first_ratio=str(old['ratio']),first_value=old['value'],
                            second_input=line.strip(),second_ratio=str(ratio),second_value=value,
                            different_exact_ratio=old['ratio']!=ratio))
                else:g['modes'][rc]=dict(input=line.strip(),ratio=ratio,value=value)
        assert total==c['rows'] and sha.hexdigest()==c['hardware_sha256']
        counts['authenticated_rows']+=total;sources.append(dict(job=job.name,rows=total,hardware_sha256=sha.hexdigest()))
        print(job.name,'authenticated',total,'current conflicts',len(conflicts),flush=True)
    counts['lead_groups']=len(groups)
    counts['multiple_ratio_lead_groups']=sum(len(g['ratios'])>1 for g in groups.values())
    counts['conflicting_observations']=len(conflicts)
    collisions=[dict(lead_significand=q,lead_exponent=e,distinct_ratios=len(g['ratios']),first_input=g['first'])
                for (q,e),g in groups.items() if len(g['ratios'])>1]
    save(BASE/'d0012-quotient-collision-audit.json',dict(status='SAVED_QUOTIENT_STATE_OBSERVABILITY_AUDIT',
        counts=dict(counts),sources=sources,collisions=collisions,conflicts=conflicts,hardware_executed=False))
    print('COMPLETE',dict(counts),flush=True)


if __name__=='__main__':main()
