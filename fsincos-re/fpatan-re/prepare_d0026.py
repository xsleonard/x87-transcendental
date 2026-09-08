"""Prospective final-rounding wall plus independent broad-domain controls.

Use software-mined RN/RD output transitions in direct/table ranges, expand
five adjacent significands across signs/octants and wide common scales,
and add independent full-exponent pairs. No hardware labels are consulted.
"""
from dataclasses import replace
import json
import random

from architecture import POLICY
from compressed_guard import digest
from d0010_causal_intervals import BASE
from freeze_stream import freeze

SEED='fpatan-d0026-final-rounding-wall-and-full-range-20260905'


def generate():
    rng=random.Random(SEED)
    report=json.loads((BASE/'d0026-rounding-boundary-mining.json').read_text())
    source=BASE/'d0026-rounding-boundary-seeds.tsv'
    assert digest(source)==report['seeds_sha256']
    for line in source.read_text().splitlines():
        ident,family,rc,offset,*words=line.split()
        ys,ym,xs,xm=(int(s,16) for s in words)
        for swap in (False,True):
            for sy in (0,32768):
                for sx in (0,32768):
                    shift=rng.randrange(-15000,15001)
                    a,b=(ys+shift,ym),(xs+shift,xm)
                    if swap:a,b=b,a
                    assert 0<a[0]<32767 and 0<b[0]<32767
                    yield (a[0]|sy,a[1],b[0]|sx,b[1]),('table' if family=='1' else 'small-ratio')+'-'+rc+'-transition-'+offset
    for _ in range(8192):
        ys,xs=rng.randrange(1,32767),rng.randrange(1,32767)
        ym,xm=rng.getrandbits(63)|(1<<63),rng.getrandbits(63)|(1<<63)
        yield (ys|rng.getrandbits(1)<<15,ym,xs|rng.getrandbits(1)<<15,xm),'independent-full-exponent-control'


if __name__=='__main__':
    freeze('d0026',SEED,generate,
           ('prepare_d0026.py','d0026_rounding_boundary_miner.c',
            'd0026_rounding_boundary_mining.py','graph_v5.py','graph_v6.py',
            'graph_v7.py','d0023_index_hypotheses.py','d0010_causal_intervals.py',
            'fpatan_candidate_v7.c'),policy=replace(POLICY,numerical_graph='v7'),
           purpose='Prospective RN/RD output-transition neighbors in direct/table ranges, all sign/octant orbits and independent full-exponent controls')
