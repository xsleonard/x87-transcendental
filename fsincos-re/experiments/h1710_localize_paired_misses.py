#!/usr/bin/env python3
"""Bounded fixed-Horner materialization audit on the two retained paired misses.

This diagnoses a schedule, not a physical mechanism or unseen-label validation.
"""
import argparse
import itertools
import json
from pathlib import Path
import h1592_independent_integer_spec as s
import h1601_paired_square_discriminator as old
from h1709_paired_retained_census import digest, save, parse


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();assert not a.output.exists()
    directory=root/'tmp/ledger33/current/h1709_paired_retained_census'
    assert digest(directory/'report.json')=='700e0656409c0f420371a96ea86f6def4485e96a382de763af5094e257cbdd60'
    frontier=json.loads((directory/'frontier.json').read_text())
    inputs={(r['bank'],r['index'],r['operand']) for r in frontier};assert len(inputs)==2
    prep=json.loads((directory/'prepared.json').read_text());rows=[]
    for bank,index,operand in sorted(inputs):
        expected={};paths={}
        for mode in ('rn','rd','ru'):
            path=root/'stageA'/f'{bank}_sc_{mode}_status.txt'
            assert digest(path)==prep['evidence'][str(path.relative_to(root))]
            with path.open() as f:
                for i,line in enumerate(f):
                    if i==index:expected[mode]=parse(line,True)[0];break
            paths[mode]=digest(path)
        x=s.decode_external(operand);square=s.mul(x,x,67);survivors=[];choices=[]
        for mask,double in itertools.product(range(32),(False,True)):
            v=old.SINE[6];stages=[]
            for edge,i in enumerate((5,4,3,2,1)):
                product=s.exact_mul(v,square)
                if mask>>edge&1:product=s.quantize(product,67,'chop')
                v=s.add(product,old.SINE[i],64,'rn');stages.append(v.record())
            product=s.exact_mul(v,square)
            if double:product=s.quantize(product,67,'chop')
            product=s.quantize(product,64,'rn');tail=s.mul(product,x,67)
            values={mode:s.encode_external(s.add(x,tail,64,mode)) for mode in expected}
            exact=all(values[m]==expected[m][0] for m in expected)
            choice=dict(sine_edge_mask=mask,double_round_sine_product=double,
                outputs=values,exact=exact,factors=stages,tail=tail.record())
            choices.append(choice)
            if exact:survivors.append([mask,int(double)])
        assert len(survivors)==32 and all(mask&16 for mask,_ in survivors)
        rows.append(dict(operand=operand,bank=bank,index=index,observed=expected,
            capture_sha256=paths,survivors=survivors,choices=choices))
    save(a.output,dict(experiment='h1710_localize_paired_misses',rows=rows,
        tested_fixed_schedules_per_operand=64,necessary_within_family='last sine Horner product materialized at CHOP67 before RN64 coefficient add',
        hardware_execution='none',private_access='none',promotion=False,
        boundary='Earlier-edge materialization and terminal-product double rounding are not distinguished by these two operands; no universal uniqueness or silicon claim.',
        sha256=dict(script=digest(Path(__file__)),integer_spec=digest(Path(s.__file__)),
            old_paired_spec=digest(Path(old.__file__)),frontier=digest(directory/'frontier.json'))))
    print('Two operands; 64 fixed schedules each; last sine product cut necessary within family; 32 survivors each')


if __name__=='__main__':main()
