"""Small fixed split-square and final-sum-cut controls, saved data only."""
import collections
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save


def horner(u):
    h=ROM[123]
    for k in range(122,117,-1):h=cut(ROM[k]+cut(u*h,'chop67'),'rn64')
    return h


def main():
    rows=[]
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']!='direct':continue
        z=t['z'];u=cut(z*z,'chop67');h=horner(u)
        mr=cut(z*cut(z,'chop64'),'rn64')
        kernels=dict(V4=z+cut(cut(u*h,'chop67')*z,'chop67'),
                     V5=z+cut(cut(u*h,'chop67')*cut(z,'chop64'),'chop67'),
                     MR=z+cut(cut(z*mr,'chop67')*horner(mr),'chop67'))
        rows.append((pair,t,observation_interval(pair['rows']),kernels))
    def failure(pair,t,band,k):return not band.contains(abs(restore(k,t,pair['raw'])))
    scores={name:sum(failure(p,t,b,ks[name]) for p,t,b,ks in rows) for name in ('V4','V5','MR')}
    sums=[]
    for name,mode,bits in itertools.product(('V4','V5','MR'),('chop','rn'),range(64,129)):
        fmt=mode+str(bits)
        bad=[p['rows'][0]['input'] for p,t,b,ks in rows if failure(p,t,b,cut(ks[name],fmt))]
        sums.append(dict(template=name,final_sum_cut=fmt,failed_groups=len(bad),counterexample=bad[0] if bad else None))
    splits=[]
    for fmt,read in itertools.product(('chop64','rn64','chop67','rn67','chop69','rn69'),('exact','chop64','rn64')):
        bad=[]
        for p,t,b,ks in rows:
            z=t['z'];uh=cut(z*cut(z,read),fmt);ut=cut(z*cut(z,'chop64'),'rn64')
            k=z+cut(cut(z*ut,'chop67')*horner(uh),'chop67')
            if failure(p,t,b,k):bad.append(p['rows'][0]['input'])
        splits.append(dict(horner_square_format=fmt,horner_square_read=read,
            tail_square='RN64(z*CHOP64(z))',failed_groups=len(bad),counterexample=bad[0] if bad else None))
    save(BASE/'d0011-auxiliary-audits.json',dict(status='BOUNDED_FIXED_GRAPH_CONTROLS',
        direct_raw_groups=len(rows),baseline_failed_groups=scores,final_sum_programs=sums,
        split_square_programs=splits,hardware_executed=False))
    print('baseline failed groups',scores,'sum-cut survivors',sum(not r['failed_groups'] for r in sums),
          'split-square survivors',sum(not r['failed_groups'] for r in splits),flush=True)


if __name__=='__main__':main()
