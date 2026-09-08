"""Test table-cell dispatch jointly with the precision of the index read.

The 3/64 boundary is the midpoint between the first two n/32 ROM entries;
it is a structural alternative to dispatch on exponent alone. No threshold
or entry is selected from individual error operands.
"""
import itertools
from graph_v3 import Program
from table_stage_audit import groups,score,BASE
from prepare import save


def main():
    data=groups();results=[]
    for dispatch,read,index in itertools.product(('ratio3/64','exponent'),
            ('exact','chop64','rn64','rn65','chop67'),('nearest','even','floor')):
        p=Program(direct_test='exponent' if dispatch=='exponent' else 'ratio',
                  direct_numerator=3,direct_limit=64,index_read=read,table_index=index)
        result=score(p,data);results.append(result)
        print(dispatch,read,index,result['counts'],flush=True)
    results.sort(key=lambda x:sum(v for k,v in x['counts'].items() if k.endswith('_misses')))
    save(BASE/'index-dispatch-audit.json',dict(status='DISCOVERY_ONLY',results=results,best=results[:8],hardware_executed=False))


if __name__=='__main__':main()
