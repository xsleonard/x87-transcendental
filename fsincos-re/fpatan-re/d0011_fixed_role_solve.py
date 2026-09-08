"""Exact backwards finite-state solve for globally fixed Horner roles.

Forward reachable-value sets are finite and retain every allowed state.
Backward intersection requires the same operation policy on every input at
each of five coefficient-add roles. Equivalent policy transitions are merged,
not selected by input. This explores 108**5 schedules without a SAT solver.
Any survivor is discovery-only and needs full-corpus and fresh verification.
"""
import collections
import argparse
import functools
import itertools
import json
import time
from d0010_causal_intervals import BASE,observation_interval,restore
from d0011_relaxed_horner import READS,FORMATS
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save

POLICIES=tuple(itertools.product(READS,FORMATS,FORMATS))


def operation(u,h,k,p):
    hr,m,a=p
    return cut(ROM[k]+cut(u*cut(h,hr),m),a)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='d0011-fixed-role-solve.json');args=ap.parse_args()
    assert args.out.startswith('d0011-') and '/' not in args.out
    start=time.monotonic();grouped=collections.defaultdict(list)
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']=='direct':grouped[t['z']].append((pair,t,observation_interval(pair['rows'])))
    points=[]
    for index,(z,rows) in enumerate(grouped.items()):
        u=cut(z*cut(z,'chop64'),'rn64');cube=cut(z*u,'chop67')
        states=[[ROM[123]]];inverse=[]
        for k in range(122,117,-1):
            table=[[operation(u,h,k,p) for h in states[-1]] for p in POLICIES]
            next_values=sorted(set(v for row in table for v in row));ids={v:i for i,v in enumerate(next_values)}
            stage=[]
            for row in table:
                back=[0]*len(next_values)
                for previous,v in enumerate(row):back[ids[v]]|=1<<previous
                stage.append(tuple(back))
            inverse.append(tuple(stage));states.append(next_values)
        allowed=0
        for i,h in enumerate(states[-1]):
            kernel=z+cut(cube*h,'chop67')
            if all(band.contains(abs(restore(kernel,t,pair['raw']))) for pair,t,band in rows):allowed|=1<<i
        assert allowed,'Even relaxed Horner cannot reach this grouped endpoint'
        points.append(dict(z=z,u=u,cube=cube,rows=rows,states=states,inverse=inverse,allowed=allowed))
        if (index+1)%16==0:print('constructed transition graphs',index+1,flush=True)
    points.sort(key=lambda p:(p['allowed'].bit_count(),len(p['states'][-1])))
    initial=tuple(p['allowed'] for p in points);visited=collections.Counter();edges=[]
    @functools.lru_cache(maxsize=None)
    def preimage(point,stage,policy,mask):
        result=0;back=points[point]['inverse'][stage][policy]
        while mask:
            bit=mask&-mask;result|=back[bit.bit_length()-1];mask^=bit
        return result
    @functools.lru_cache(maxsize=None)
    def search(stage,allowed):
        if stage<0:return 1,((),)
        visited[stage]+=1
        groups=collections.defaultdict(list)
        for policy in range(len(POLICIES)):
            masks=[]
            for point,mask in enumerate(allowed):
                before=preimage(point,stage,policy,mask)
                if not before:break
                masks.append(before)
            else:groups[tuple(masks)].append(policy)
        total=0;examples=[]
        for masks,aliases in groups.items():
            count,prefixes=search(stage-1,masks)
            total+=len(aliases)*count
            if count:
                for prefix in prefixes:
                    if len(examples)<64:examples.append(prefix+(aliases[0],))
        edges.append(dict(stage=stage,allowed_masks=list(allowed),nonempty_transition_classes=len(groups),
                          satisfying_schedules=total))
        if sum(visited.values())%1000==0:print('search nodes',sum(visited.values()),'partial count',total,flush=True)
        return total,tuple(examples)
    count,examples=search(4,initial)
    support=[]
    for i,point in enumerate(points):
        mask=sum(1<<p for p in range(len(POLICIES)) if preimage(i,4,p,point['allowed']))
        support.append(mask)
    core=None
    if not count:
        # A two-point obstruction is stronger and simpler to independently
        # replay than a large schedule count. Report it only when present.
        for i,j in itertools.combinations(range(len(points)),2):
            if not support[i]&support[j]:core=(i,j);break
    core_report=[]
    if core is not None:
        for i in core:
            point=points[i]
            core_report.append(dict(z=str(point['z']),u=str(point['u']),
                rows=[dict(raw=pair['raw'],observations=pair['rows']) for pair,t,band in point['rows']],
                allowed_final_policies=[p for p in range(len(POLICIES)) if support[i]>>p&1],
                all_reachable_h119=[str(h) for h in point['states'][-2]],
                allowed_h118=[str(h) for n,h in enumerate(point['states'][-1]) if point['allowed']>>n&1]))
    programs=[]
    for example in examples:
        for point in points:
            h=ROM[123]
            for k,policy in zip(range(122,117,-1),example):h=operation(point['u'],h,k,POLICIES[policy])
            kernel=point['z']+cut(point['cube']*h,'chop67')
            assert all(band.contains(abs(restore(kernel,t,pair['raw']))) for pair,t,band in point['rows'])
        programs.append([dict(rom=k,horner_read=POLICIES[p][0],multiply=POLICIES[p][1],add=POLICIES[p][2])
                         for k,p in zip(range(122,117,-1),example)])
    report=dict(status='EXACT_FINITE_SHARED_ROLE_DISCOVERY_SOLVE',square='RN64(z*CHOP64(z))',
        tail='CHOP67(CHOP67(z*u)*h)',policy_fields=('horner_read','multiply','add'),policies=POLICIES,
        schedule_space=len(POLICIES)**5,constrained_ratio_groups=len(points),
        constrained_raw_groups=sum(len(p['rows']) for p in points),satisfying_schedules=count,
        representative_schedules=programs,search_nodes=dict(visited),search_certificate=edges,
        two_point_final_role_obstruction=core_report,
        elapsed_seconds=time.monotonic()-start,hardware_executed=False)
    save(BASE/args.out,report)
    print('COMPLETE',len(POLICIES)**5,'fixed schedules;',count,'satisfy direct frontier;',
          sum(visited.values()),'backward states',flush=True)


if __name__=='__main__':main()
