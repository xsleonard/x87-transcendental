"""Exact shared-coefficient SMT audit for one fixed FPATAN arithmetic graph.

Six constant offsets are global integers, not functions of input or error.
Every retained arithmetic node is encoded with exact rational inequalities
and an integer significand; RN ties use output parity. Coefficient bounds
also certify a fixed sign/binade at each operation. The query is saved before
solving. SAT requires concrete forward replay; UNKNOWN remains UNKNOWN.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import time
import z3
from d0010_causal_intervals import BASE,observation_interval
from graph_v5 import prevalue
from model import F,ROM,cut,exponent,pow2
from prepare import save


def rat(v):
    v=F(v)
    return z3.RealVal(v.numerator)/v.denominator


class Graph:
    def __init__(self,data,bound_bits,coefficient_bits):
        self.solver=z3.Solver();self.data=data;self.nodes=[];self.endpoints=[]
        self.offsets={k:z3.Int(f'delta_{k}') for k in range(118,124)}
        self.units={k:pow2(exponent(ROM[k])-coefficient_bits+1) for k in self.offsets}
        self.bound=1<<bound_bits
        for d in self.offsets.values():self.solver.add(d>=-self.bound,d<=self.bound)
        for index,(pair,t,band) in enumerate(data):self.point(index,t,band)

    def quantize(self,expr,bounds,bits,mode,name):
        lo,hi=bounds;assert lo<=hi and lo*hi>0
        sign=1 if lo>0 else -1
        elo,ehi=exponent(lo),exponent(hi)
        if elo!=ehi:raise ValueError(f'{name}: binade not fixed throughout the coefficient bounds')
        step=pow2(elo-bits+1);q=z3.Int(name);m=sign*expr/rat(step)
        if mode=='chop':self.solver.add(q<=m,m<q+1)
        else:
            assert mode=='rn'
            self.solver.add(2*q-1<=2*m,2*m<=2*q+1,
                z3.Or(q%2==0,z3.And(2*q-1<2*m,2*m<2*q+1)))
        outbounds=(cut(lo,mode+str(bits)),cut(hi,mode+str(bits)))
        qbounds=sorted(abs(v)/step for v in outbounds)
        assert all(v.denominator==1 for v in qbounds)
        self.solver.add(q>=int(qbounds[0]),q<=int(qbounds[1]))
        out=sign*q*rat(step)
        self.nodes.append((name,out,step,sign,elo,bits,mode))
        return out,outbounds

    def coefficient(self,k):
        span=self.bound*self.units[k]
        return rat(ROM[k])+self.offsets[k]*rat(self.units[k]),(ROM[k]-span,ROM[k]+span)

    def point(self,index,t,band):
        z=t['z'];u=cut(z*cut(z,'chop64'),'rn64');cube=cut(z*u,'chop67')
        h,hb=self.coefficient(123)
        for k in range(122,117,-1):
            p,pb=self.quantize(rat(u)*h,(u*hb[0],u*hb[1]),67,'chop',f'p{index}_m{k}')
            a,ab=self.coefficient(k)
            h,hb=self.quantize(a+p,(ab[0]+pb[0],ab[1]+pb[1]),64,'rn',f'p{index}_h{k}')
        tail,tb=self.quantize(rat(cube)*h,(cube*hb[0],cube*hb[1]),67,'chop',f'p{index}_tail')
        endpoint=rat(z)+tail
        condition=z3.And(endpoint>=rat(band.lo) if band.lc else endpoint>rat(band.lo),
                         endpoint<=rat(band.hi) if band.hc else endpoint<rat(band.hi))
        self.endpoints.append((endpoint,condition))


def forward(z,coefficients):
    u=cut(z*cut(z,'chop64'),'rn64');cube=cut(z*u,'chop67');h=coefficients[123];nodes={}
    for k in range(122,117,-1):
        p=cut(u*h,'chop67');h=cut(coefficients[k]+p,'rn64')
        nodes[f'm{k}']=p;nodes[f'h{k}']=h
    tail=cut(cube*h,'chop67');nodes['tail']=tail
    return z+tail,nodes


def as_fraction(v):
    v=z3.simplify(v);assert z3.is_rational_value(v)
    return F(v.numerator_as_long(),v.denominator_as_long())


def check_encoding(g,offsets):
    # Calibration is an exact assignment check, not another integer search.
    # Binding every intermediate to its independently evaluated value avoids
    # spending the solver budget rediscovering a completely known trace.
    bindings=[(g.offsets[k],z3.IntVal(d)) for k,d in offsets.items()]
    coefficients={k:ROM[k]+d*g.units[k] for k,d in offsets.items()}
    concrete={};scores=0
    for index,(_,t,band) in enumerate(g.data):
        endpoint,nodes=forward(t['z'],coefficients);concrete.update({f'p{index}_{k}':v for k,v in nodes.items()})
        scores+=not band.contains(endpoint)
    for name,expr,step,sign,*_ in g.nodes:
        q=sign*concrete[name]/step;assert q.denominator==1
        bindings.append((z3.Int(name),z3.IntVal(q.numerator)))
    assigned=z3.simplify(z3.substitute(z3.And(*g.solver.assertions()),*bindings))
    assert z3.is_true(assigned),'Concrete arithmetic trace violates the symbolic constraints'
    return scores


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bound-bits',type=int,default=28)
    ap.add_argument('--coefficient-bits',type=int,default=69);ap.add_argument('--timeout-ms',type=int,default=60000)
    ap.add_argument('--tag',default='b28-p69');args=ap.parse_args()
    assert 0<=args.bound_bits<=40 and 67<=args.coefficient_bits<=72
    assert args.tag and all(c.isalnum() or c=='-' for c in args.tag)
    stem=BASE/f'd0012-coefficient-solve-{args.tag}'
    assert not stem.with_suffix('.smt2').exists() and not stem.with_suffix('.json').exists()
    data=[];seen=set()
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']!='direct' or t['swap'] or pair['raw'][2]&32768:continue
        band=observation_interval(pair['rows']);key=(t['z'],band)
        if key in seen:continue
        seen.add(key);data.append((pair,t,band))
    data.sort(key=lambda p:p[2].lo!=p[2].hi)
    started=time.monotonic();g=Graph(data,args.bound_bits,args.coefficient_bits)
    tests=[]
    for name,offsets in (('P5',{k:0 for k in range(118,124)}),
            ('positive-bound',{k:g.bound for k in range(118,124)}),
            ('negative-bound',{k:-g.bound for k in range(118,124)}),
            ('alternating-bound',{k:(-1 if k%2 else 1)*g.bound for k in range(118,124)})):
        failed=check_encoding(g,offsets);tests.append(dict(test=name,failed_endpoint_groups=failed))
        print('encoding replay PASS',name,failed,'endpoint misses',flush=True)
    assert tests[0]['failed_endpoint_groups']>0
    for _,condition in g.endpoints:g.solver.add(condition)
    query=g.solver.to_smt2()
    with stem.with_suffix('.smt2').open('x') as f:f.write(query)
    print('SOLVING',len(data),'points',len(g.nodes),'quantized nodes',flush=True)
    # Z3's internal timeout was not promptly honored by one earlier query.
    # Run the immutable query in a child and enforce a real external deadline.
    child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('d0012_smt_worker.py')),
        str(stem.with_suffix('.smt2')),'--timeout-ms',str(args.timeout_ms)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    external_deadline=False
    try:
        stdout,stderr=child.communicate(timeout=args.timeout_ms/1000+2)
    except subprocess.TimeoutExpired:
        external_deadline=True;child.terminate()
        stdout,stderr=child.communicate(timeout=10)
    if external_deadline:
        solved=dict(result='unknown',reason_unknown='external deadline; child terminated')
    else:
        assert child.returncode==0,(child.returncode,stdout,stderr)
        solved=json.loads(stdout)
    outcome=solved['result'];candidate=None
    if outcome=='sat':
        offsets={int(k):v for k,v in solved['offsets'].items()}
        coefficients={k:ROM[k]+offsets[k]*g.units[k] for k in offsets}
        for _,t,band in data:assert band.contains(forward(t['z'],coefficients)[0])
        candidate=dict(offsets=offsets,coefficients={k:str(v) for k,v in coefficients.items()},concrete_replay='PASS')
    report=dict(status='EXACT_SHARED_CONSTANT_QUERY_'+outcome.upper(),solver=z3.get_version_string(),
        timeout_ms=args.timeout_ms,reason_unknown=solved['reason_unknown'],
        external_deadline=external_deadline,worker_returncode=child.returncode,worker_stderr=stderr,
        graph='MR64 asymmetric square; cube-first CHOP67 tail; CHOP67 Horner products and RN64 adds',
        coefficient_bits=args.coefficient_bits,offset_bound_in_grid_ULPs=g.bound,
        grid_units={k:str(v) for k,v in g.units.items()},groups=len(data),quantized_nodes=len(g.nodes),
        encoding_tests=tests,query_sha256=hashlib.sha256(query.encode()).hexdigest(),candidate=candidate,
        inputs=[p['rows'][0]['input'] for p,t,b in data],elapsed_seconds=time.monotonic()-started,hardware_executed=False)
    save(stem.with_suffix('.json'),report)
    print('COMPLETE',outcome,report['reason_unknown'],flush=True)


if __name__=='__main__':main()
