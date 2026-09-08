#!/usr/bin/env python3
"""Fresh compound-rounding proposals with fixed independent predictions."""
import argparse
import json
import random
from collections import Counter,defaultdict
from pathlib import Path
import h1714_rounding_challenge as check
from h1709_paired_retained_census import digest,save

SCAN='tmp/ledger33/current/h1715_internal_scan'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    assert not out.exists();prep=json.loads((root/SCAN/'prepared.json').read_text())
    for name,sha in prep['sha256']['evidence'].items():assert digest(root/name)==sha,name
    assert digest(root/SCAN/'scanner')==prep['sha256']['binary']
    assert (root/SCAN/'scan.stderr').read_text().endswith('DONE operands=3000000 proposals=444\n')
    check.independent.constants(root);R=check.independent.rational;rng=random.Random(0x1715)
    kinds=defaultdict(set);events=[]
    def add(se,sig,kind):
        assert 1<<63<=sig<1<<64
        for sign in (0,0x8000):kinds[f'{se|sign:04x} {sig:016x}'].add(kind)
    for line in (root/SCAN/'proposals.txt').read_text().splitlines():
        se,sig,stratum,insn,category,score,first,second,final=line.split()
        se,sig=int(se,16),int(sig,16)
        label='compound_internal_RN' if category=='0' else 'compound_internal_final'
        add(se,sig,label)
        events.append(dict(operand=f'{se:04x} {sig:016x}',stratum=int(stratum),instruction=('fsin','fcos','fsincos')[int(insn)],
            kind=label,rank_key=int(score),first_RN_key=int(first),second_RN_key=int(second),final_key=int(final)))
        for delta in (-1,1):add(se,sig+delta,'compound_neighbor')
    # Small nonzero deltas around every reachable table center stress severe
    # subtractive cancellation. The center itself stays covered by retained
    # observations; these newly generated deltas are freshness-audited later.
    for b in (18,22,26,30,36,44,52):
        e=-2 if b<32 else -1;se=e+16383;center=b<<(57-e)
        for exponent in (12,25,39,51):
            delta=(1<<exponent)+rng.randrange(257,65536)
            for direction in (-1,1):
                sig=center+direction*delta
                if se==0x3ffe and sig>=0xc90fdaa22168c234:continue
                add(se,sig,'table_center_cancellation')
    for e in (-70,-69,-68,-67,-34,-33,-32,-31,-3,-2,-1,0,1,30,48,61,62,63):
        for edge in (1<<63,(1<<64)-1):
            delta=rng.randrange(1<<17,1<<35)
            add(e+16383,edge+delta if edge==1<<63 else edge-delta,'dispatch_binade_edge')
    # Complement direct compound cases with raw external high-q inputs; this
    # is a domain control, not an asserted residual isomorph.
    for e in range(63):
        for _ in range(2):add(e+16383,rng.getrandbits(63)|(1<<63),'high_q_control')
    rows=[dict(operand=op,kinds=sorted(kinds[op]),predictions={}) for op in sorted(kinds)]
    ops=[r['operand'] for r in rows];cache={};counts=Counter()
    for insn in check.INSTRUCTIONS:
        for mode in check.MODES:
            actual=check.c_predictions(root/'src/fsincos_skylake',insn,mode,ops)
            for row,value in zip(rows,actual):
                expected=check.prediction(row['operand'],insn,mode,cache)
                assert value==expected,(row['operand'],insn,mode,value,expected)
                row['predictions'].setdefault(insn,{})[mode]=expected
                counts['independent_instruction_rows']+=1;counts['independent_outputs']+=len(expected['outputs'] or [])
            print(insn,mode,'independent pass',flush=True)
    out.mkdir(parents=True);save(out/'rank_events.json',events)
    evidence={**prep['sha256']['evidence'],SCAN+'/proposals.txt':digest(root/SCAN/'proposals.txt'),
        SCAN+'/scan.stderr':digest(root/SCAN/'scan.stderr'),'experiments/h1714_rounding_challenge.py':digest(Path(check.__file__)),
        'src/fsincos_skylake':digest(root/'src/fsincos_skylake')}
    for module in (check.independent,check.independent.integer,check.independent.old_pair,R,check.independent.tiny):
        path=Path(module.__file__);evidence[str(path.relative_to(root))]=digest(path)
    save(out/'bank.json',dict(experiment='h1715_challenge_bank',capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        candidate_changed=False,manifest_frozen=False,hardware_execution='none',private_access='none',operands=rows,
        kind_memberships=dict(Counter(k for r in rows for k in r['kinds'])),counts=dict(counts),
        limits='Compound stages are ranked by truncated 32-bit fraction keys, not exact tie proofs. Every final prediction is independently exact. No labels used in generation.',
        sha256=dict(evidence=evidence,script=digest(Path(__file__)),events=digest(out/'rank_events.json'))))
    print('SOFTWARE_ONLY operands=',len(rows),'counts=',dict(counts))


if __name__=='__main__':main()
