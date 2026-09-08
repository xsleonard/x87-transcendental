"""Run the local C boundary miner and verify its brackets independently."""
import argparse
import collections
import json
from pathlib import Path
import subprocess

from compressed_guard import digest
from d0010_causal_intervals import BASE
from graph_v7 import prevalue
from model import encode
from prepare import save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',type=Path,required=True)
    args=parser.parse_args()
    assert args.binary.is_file(), 'Build the local miner before creating its output artifact'
    output=BASE/'d0026-rounding-boundary-seeds.tsv'
    with output.open('xb') as dest:
        child=subprocess.run([str(args.binary)],stdout=dest,stderr=subprocess.PIPE,check=True)
    counts=json.loads(child.stderr)
    grouped=collections.defaultdict(dict)
    families=collections.Counter()
    for line in output.read_text().splitlines():
        ident,family,rc,offset,ys,ym,xs,xm=line.split()
        raw=tuple(int(s,16) for s in (ys,ym,xs,xm))
        grouped[int(ident)][int(offset)]=(raw,rc)
        families[family+':'+rc]+=1
    assert len(grouped)==counts['seeds'] and sum(families.values())==counts['rows']
    for records in grouped.values():
        assert set(records)=={-2,-1,0,1,2}
        below,rc=records[-1];above,arc=records[0]
        assert arc==rc and below[0]==above[0] and below[2:]==above[2:] and above[1]==below[1]+1
        q0=encode(prevalue(*below),rc)
        q1=encode(prevalue(*above),rc)
        assert q0<q1,'Independent Python does not reproduce the adjacent output crossing'
    sources=('d0026_rounding_boundary_miner.c','d0026_rounding_boundary_mining.py',
             'fpatan_candidate_v7.c','graph_v7.py')
    save(BASE/'d0026-rounding-boundary-mining.json',dict(
        status='SOFTWARE_ONLY_BOUNDARIES_NOT_FROZEN_OR_CAPTURED',counts=counts,
        family_counts=families,independently_verified_brackets=len(grouped),
        seeds_sha256=digest(output),binary_sha256=digest(args.binary),
        sources={name:digest(Path(__file__).with_name(name)) for name in sources},
        hardware_labels_opened=False,hardware_executed=False,numerical_model_promoted=False))
    print('PASS',len(grouped),'independent adjacent output-transition brackets;',counts['rows'],'neighbor seeds; no hardware',flush=True)


if __name__=='__main__':main()
