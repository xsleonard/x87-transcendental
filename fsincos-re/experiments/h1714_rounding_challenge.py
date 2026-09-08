#!/usr/bin/env python3
"""Freeze-ready software proposals: exact rounding brackets and high-q lifts.

Independent rational replay certifies every C prediction and inverse bracket.
No hardware labels or private files are read by this generator.
"""
import argparse
import json
import subprocess
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import h1710_verify_paired_program as independent
from h1709_paired_retained_census import digest, save

SCAN = 'tmp/ledger33/current/h1714_rounding_scan_v2'
MODES = ('rn', 'rd', 'ru', 'rz')
INSTRUCTIONS = ('fsin', 'fcos', 'fsincos')


def prevalue(op, kind):
    r, rs, cosine, negative, reduced = independent.rational.external(op, 'fcos' if kind % 2 else 'fsin')
    assert not reduced and not rs and not negative
    if r < Fraction(1, 4):
        return independent.polynomial(r, 'last')[kind] if kind < 2 else independent.rational.polynomial_graph(r, kind-2)
    return independent.rational.table_graph(r, independent.rational.table_lane(r))[0][kind % 2]


def prediction(op, insn, mode, cache):
    if insn == 'fsincos':
        value, meta = independent.expected(op, mode, 'last', cache)
        return dict(outputs=list(value) if value else None, path=meta[0] if meta else 'range', C1=meta[3] if meta and meta[1] else None)
    info = independent.tiny.evaluate(op, insn, mode)
    if info['output'] is not None:
        return dict(outputs=None if info['output'] == 'C2' else [info['output']],
            path='range' if info['output'] == 'C2' else 'tiny', C1=info['C1'])
    r, rs, cosine, negative, reduced = independent.rational.external(op, insn)
    path = 'polynomial' if r < Fraction(1,4) else 'table'
    pre = independent.rational.polynomial_graph(r, cosine) if path == 'polynomial' else independent.rational.table_graph(r, independent.rational.table_lane(r))[0][cosine]
    value, c1 = independent.rational.final(pre, negative, mode)
    return dict(outputs=[value], path=path, C1=c1)


def c_predictions(binary, insn, mode, ops):
    if insn == 'fsincos':
        values, metas = independent.run(binary, mode, ops, True)
        return [dict(outputs=list(value) if value else None, path=metas[i][0] if i in metas else 'range',
            C1=metas[i][3] if i in metas and metas[i][1] else None) for i,value in enumerate(values)]
    proc = subprocess.run([str(binary),'--batch','--'+insn+'-standalone','--rc='+mode,'--general-trace'],
        input=''.join(op+'\n' for op in ops), text=True, capture_output=True, check=True)
    values = []
    for line in proc.stdout.splitlines():
        words = line.split(); assert words[0] in ('C2','OK')
        values.append(None if words[0] == 'C2' else [words[1]+':'+words[2]])
    metas = {}
    for line in proc.stderr.splitlines():
        w = line.split(); index = int(w[1]); assert index not in metas
        assert w[0] in ('HPOLY','HTABLE','HTINY')
        metas[index] = ('tiny' if w[0]=='HTINY' else 'polynomial' if w[0]=='HPOLY' else 'table',
            int(w[6] if w[0]=='HTINY' else w[-2]))
    assert len(values) == len(ops)
    return [dict(outputs=value,path=metas[i][0] if i in metas else 'range',C1=metas[i][1] if i in metas else None)
        for i,value in enumerate(values)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a = p.parse_args(); root = a.root.resolve(); out = a.output_dir.resolve(); assert not out.exists()
    prepared = json.loads((root/SCAN/'prepared.json').read_text())
    for name, sha in prepared['sha256']['evidence'].items(): assert digest(root/name)==sha,name
    assert digest(root/SCAN/'scanner') == prepared['sha256']['binary']
    assert (root/SCAN/'scan.stderr').read_text().endswith('DONE software_operands=1000000\n')
    independent.constants(root); R=independent.rational
    kinds=defaultdict(set); relations=defaultdict(list); inverses=[]; mined=[]; bounded_lift_failures=[]
    def add(op, kind):
        se, sig = op.split(); assert 1<<63 <= int(sig,16) < 1<<64
        kinds[op].add(kind); kinds[f'{int(se,16)^0x8000:04x} {sig}'].add(kind)
    lines=(root/SCAN/'proposals.txt').read_text().splitlines()
    for line in lines:
        words=line.split(); op=' '.join(words[:2]); kind=int(words[3]); label=words[2]
        add(op,label)
        pre=prevalue(op,kind); unit=R.p2(R.top(pre)-63)
        frac=(pre/unit)%1
        margin=min(frac,1-frac) if label.endswith('integer') else abs(frac-Fraction(1,2))
        entry=dict(operand=op,graph_lane=kind,kind=label,margin_ulps=str(margin))
        if label.startswith('inverse'):
            target=((int(words[5],16)<<64)|int(words[6],16))*R.p2(int(words[7]))
            entry.update(target=str(target),signed_distance_ulps=str((pre-target)/unit))
            inverses.append(entry)
        else:
            # The scanner uses a floor-normalized 64-bit ranking key, whereas
            # this certificate retains the exact rational distance.
            entry['scanner_rank_key']=words[5]; mined.append(entry)
            for delta in (-1,1): add(f'{op.split()[0]} {int(op.split()[1],16)+delta:016x}', 'mined_boundary_neighbor')
    for low,high in zip(inverses[::2],inverses[1::2]):
        assert low['target']==high['target'] and low['graph_lane']==high['graph_lane']
        assert low['operand'].split()[0]==high['operand'].split()[0]
        assert int(high['operand'].split()[1],16)-int(low['operand'].split()[1],16)==1
        assert Fraction(low['signed_distance_ulps'])>0 and Fraction(high['signed_distance_ulps'])<=0
    # Lift nearest 65-bit residual lattice points through exact modular
    # reduction. The lift itself is exact. Unless the selected D equals the
    # direct residual exactly, its relationship to the direct seed is a
    # bracket, never an isomorph. External exponents cover low and high q.
    for seed in sorted({m['operand'] for m in mined}):
        r=R.external(seed,'fsin')[0]; scaled=r*R.p2(65); center=scaled.numerator//scaled.denominator
        for e in (0,4,16,32,48,62):
            modulus=1<<(e+2); inv=pow(R.M66,-1,modulus)
            for direction in (-1,1):
                for delta in [0,*[s*k for k in range(1,129) for s in (-1,1)]]:
                    d=direction*(center+delta)
                    q0=(-d*inv)%modulus
                    lower=((1<<63)*modulus-d+R.M66-1)//R.M66
                    upper=(((1<<64)-1)*modulus-d)//R.M66
                    q=q0+max(0,(lower-q0+modulus-1)//modulus)*modulus
                    if q>upper: continue
                    sig=(q*R.M66+d)//modulus
                    op=f'{e+16383:04x} {sig:016x}'
                    actual=R.external(op,'fsin')[0]
                    assert actual==abs(d)*R.p2(-65)
                    exact=actual==r
                    add(op,'exact_reduction_preimage' if exact else 'modular_reduction_bracket')
                    relations[op].append(dict(seed=seed,q=q,signed_D=str(d),
                        exact_direct_isomorph=exact,residual_distance=str(actual-r),external_exponent=e))
                    break
                else: bounded_lift_failures.append(dict(seed=seed,external_exponent=e,residual_direction=direction))
    rows=[dict(operand=op,kinds=sorted(kinds[op]),relations=relations[op],predictions={}) for op in sorted(kinds)]
    cache={}; ops=[r['operand'] for r in rows]; counts=Counter()
    for insn in INSTRUCTIONS:
        for mode in MODES:
            actual=c_predictions(root/'src/fsincos_skylake',insn,mode,ops)
            for row, observed in zip(rows,actual):
                expected=prediction(row['operand'],insn,mode,cache)
                assert expected==observed,(insn,mode,row['operand'],expected,observed)
                row['predictions'].setdefault(insn,{})[mode]=expected
                counts['independent_instruction_rows']+=1
                counts['independent_lane_outputs']+=len(expected['outputs'] or [])
            print(insn,mode,'independent predictions pass',flush=True)
    evidence={**prepared['sha256']['evidence'],SCAN+'/prepared.json':digest(root/SCAN/'prepared.json'),
        SCAN+'/proposals.txt':digest(root/SCAN/'proposals.txt'),SCAN+'/scan.stderr':digest(root/SCAN/'scan.stderr'),
        'src/fsincos_skylake':digest(root/'src/fsincos_skylake')}
    for module in (independent,independent.integer,independent.old_pair,R,independent.tiny):
        path=Path(module.__file__); evidence[str(path.relative_to(root))]=digest(path)
    out.mkdir(parents=True)
    save(out/'boundary_certificate.json',dict(inverse=inverses,mined=mined,
        independent_adjacent_brackets=len(inverses)//2,software_screened=1000000,
        bounded_lift_searches_without_witness=bounded_lift_failures,
        scope='Exact distances in the fixed graph, not distances to mathematical sin/cos or silicon internals.'))
    bank=dict(experiment='h1714_rounding_challenge',capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        candidate_changed=False,manifest_frozen=False,hardware_execution='none',private_access='none',
        operands=rows,counts=dict(counts),kind_memberships=dict(Counter(k for r in rows for k in r['kinds'])),
        sha256=dict(evidence=evidence,script=digest(Path(__file__)),certificate=digest(out/'boundary_certificate.json')))
    save(out/'bank.json',bank)
    print(json.dumps(dict(operands=len(rows),counts=dict(counts),kinds=bank['kind_memberships'])))


if __name__=='__main__': main()
