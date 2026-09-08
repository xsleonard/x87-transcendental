"""Exact inverse-rounding intervals and saved-frontier stage localization.

Intervals use every saved RC value and C1 bit, not fitted error labels. Stage
perturbations are diagnostic reachability, never candidate selectors. No
native instructions or mathematical atan oracle are used.
"""
import collections
import dataclasses
import json
from pathlib import Path
from model import F,ROM,cut,encode,exponent,pow2,value
from graph_v5 import prevalue
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


@dataclasses.dataclass(frozen=True)
class Interval:
    lo:F
    hi:F
    lc:bool
    hc:bool

    def contains(self,v):
        return (v>self.lo or (v==self.lo and self.lc)) and (v<self.hi or (v==self.hi and self.hc))

    def intersect(self,other):
        lo=max(self.lo,other.lo);hi=min(self.hi,other.hi)
        return Interval(lo,hi,(self.lc if lo==self.lo else True) and (other.lc if lo==other.lo else True),
                        (self.hc if hi==self.hi else True) and (other.hc if hi==other.hi else True))

    def valid(self):return self.lo<self.hi or (self.lo==self.hi and self.lc and self.hc)
    def json(self):return dict(lo=str(self.lo),hi=str(self.hi),lo_closed=self.lc,hi_closed=self.hc)


def inverse(row):
    se,sig=row['se'],row['sig'];q=abs(value(se,sig))
    step=pow2(max((se&32767)-16383,-16382)-63)
    prev=q-(step/2 if sig==1<<63 and (se&32767)>1 else step);nxt=q+step
    rc=row['rc']
    if se&32768:rc={'rd':'ru','ru':'rd'}.get(rc,rc)
    if q==0:
        if row['C1']:return Interval(F(1),F(0),False,False)
        if rc=='rn':return Interval(F(0),step/2,True,True)
        if rc=='ru':return Interval(F(0),F(0),True,True)
        return Interval(F(0),step,True,False)
    if rc=='rn':out=Interval((prev+q)/2,(q+nxt)/2,not(sig&1),not(sig&1))
    elif rc=='ru':out=Interval(prev,q,False,True)
    else:out=Interval(q,nxt,True,False)
    # C1 says magnitude increased by the final rounding, independently of
    # the mathematical sign. Exact outputs therefore have C1=0.
    if row['C1']:out=out.intersect(Interval(F(0),q,True,False))
    else:out=out.intersect(Interval(q,2*nxt,True,True))
    return out


def observation_interval(rows):
    out=inverse(rows[0])
    for row in rows[1:]:out=out.intersect(inverse(row))
    return out


def kernel(z,short,stage=None,delta=0,trace=None):
    def node(name,v,bits):
        if stage==name and v:v+=delta*pow2(exponent(v)-bits+1)
        if trace is not None:trace[name]=(v,bits)
        return v
    z=node('z',z,67);u=node('square',cut(z*z,'chop67'),67)
    low,high=(114,117) if short else (118,123);h=ROM[high]
    for k in range(high-1,low-1,-1):
        m=node('multiply'+str(k),cut(u*h,'chop67'),67)
        h=node('horner'+str(k),cut(ROM[k]+m,'rn64'),64)
    product=node('tail_first',cut(u*h,'chop67'),67)
    rz=node('tail_z',cut(z,'chop64'),64)
    tail=node('tail',cut(product*rz,'chop67'),67)
    return z+tail


def restore(k,t,raw):
    angle=cut(k,'chop67')+ROM[124+t['n']] if t['n'] else k
    intermediate=cut(angle,'chop67') if t['swap'] or raw[2]&32768 else angle
    if t['swap']:result=ROM[20]+(intermediate if raw[2]&32768 else -intermediate)
    elif raw[2]&32768:result=ROM[19]-intermediate
    else:result=intermediate
    return -result if raw[0]&32768 else result


def selftest():
    for v in (F(0),pow2(-16447),pow2(-16446),3*pow2(-16447),pow2(-16445)):
        for sign in (1,-1):
            rows=[]
            for rc in ('rn','rd','ru','rz'):
                se,sig=encode(sign*v,rc,zero_sign=int(sign<0));c1=int(abs(value(se,sig))>v)
                row=dict(se=se,sig=sig,C1=c1,rc=rc);assert inverse(row).contains(v);rows.append(row)
            assert observation_interval(rows).contains(v)
    for q in (F(1),F(5,4),pow2(-16400),F(0xc90fdaa22168c235)*pow2(-64)):
        for v in (q,q-pow2(exponent(q)-67),q+pow2(exponent(q)-67)):
            for sign in (1,-1):
                rows=[]
                for rc in ('rn','rd','ru','rz'):
                    se,sig=encode(sign*v,rc);c1=int(abs(value(se,sig))>v)
                    row=dict(se=se,sig=sig,C1=c1,rc=rc);assert inverse(row).contains(v);rows.append(row)
                assert observation_interval(rows).contains(v)


def main():
    selftest();result=[];summary=collections.Counter();reach=collections.defaultdict(collections.Counter)
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        raw=pair['raw'];interval=observation_interval(pair['rows']);summary['groups']+=1
        assert interval.valid(),'No common RC-independent value'
        trace={};baseline=prevalue(*raw,trace=trace);nodes={}
        k=kernel(trace['z'],trace['kind']=='table',trace=nodes)
        assert restore(k,trace,raw)==baseline
        exact=interval.contains(abs(baseline));summary['baseline_exact_groups' if exact else 'baseline_failed_groups']+=1
        probes={}
        if not exact:
            for stage in nodes:
                good=[]
                for delta in (-16,-8,-4,-2,-1,1,2,4,8,16):
                    v=restore(kernel(trace['z'],trace['kind']=='table',stage,delta),trace,raw)
                    if interval.contains(abs(v)):good.append(delta)
                probes[stage]=good;reach[stage]['reachable_groups']+=bool(good)
                reach[stage]['unit_reachable_groups']+=(-1 in good or 1 in good)
        # On an unrotated direct path, infer the required correction in
        # final-tail ULPs without pretending a particular point is observed.
        offset=None
        if trace['kind']=='direct' and not trace['swap'] and not(raw[2]&32768):
            step=pow2(exponent(nodes['tail'][0])-66)
            offset=Interval((interval.lo-abs(baseline))/step,(interval.hi-abs(baseline))/step,interval.lc,interval.hc).json()
        result.append(dict(raw=raw,interval=interval.json(),baseline=str(baseline),baseline_exact=exact,
            kind=trace['kind'],n=trace['n'],ratio=str(trace['ratio']),z=str(trace['z']),
            tail_ulp_correction=offset,reachable_deltas=probes))
    report=dict(status='CAUSAL_INTERVALS_NOT_A_SELECTOR',summary=dict(summary),reachability={k:dict(v) for k,v in reach.items()},
                groups=result,hardware_executed=False)
    save(BASE/'d0010-causal-intervals.json',report)
    print(dict(summary),flush=True)
    for k,v in reach.items():print(k,dict(v),flush=True)


if __name__=='__main__':main()
