#!/usr/bin/env python3
"""Current paired FSINCOS census over retained raw captures, without hardware.

Historical input order is explicit. SHA256SUMS are checked where retained;
stageA lacks an original checksum manifest and is labeled snapshot provenance.
No private data, learned rule, source/default or paper change.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

MODES = ('rn','rd','ru')
SOURCE_SHA = 'e1e88e4ffa53f01f23ce11f678a17c5a9a699774decca632ecab072862b59029'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20), b''): h.update(block)
    return h.hexdigest()


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n')


def parse(line, hardware=False):
    words = line.lower().split()
    if words[0] == 'c2':
        assert len(words) == (3 if hardware else 1)
        if hardware: assert words[1] == 'sw'
        return None, int(words[-1],16) if hardware else None
    assert words[0] == 'ok' and len(words) == (7 if hardware else 5)
    assert re.fullmatch('[0-9a-f]{4}', words[1]) and re.fullmatch('[0-9a-f]{4}', words[3])
    assert re.fullmatch('[0-9a-f]{16}', words[2]) and re.fullmatch('[0-9a-f]{16}', words[4])
    if hardware: assert words[5] == 'sw'
    return (words[1]+':'+words[2], words[3]+':'+words[4]), int(words[-1],16) if hardware else None


def inventory(root):
    banks = []; evidence = {}
    def record(path):
        name = str(path.relative_to(root)); evidence[name] = digest(path)
        return name
    def checksums(directory):
        manifest = directory/'SHA256SUMS'; record(manifest); found={}
        for line in manifest.read_text().splitlines():
            sha,name=line.split(None,1); name=name.strip().lstrip('*')
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
            found[name]=sha
        return found
    def add(tag, inputs, directory, pattern, provenance, expected=None):
        hashes=checksums(directory) if (directory/'SHA256SUMS').exists() else {}
        paths={m:directory/pattern.format(m=m) for m in MODES}
        if inputs is not None:
            input_name=record(inputs)
            if inputs.parent==directory and hashes: assert hashes[inputs.name]==evidence[input_name]
        else: input_name=None
        for path in paths.values():
            name=record(path)
            if hashes: assert hashes[path.name]==evidence[name]
        banks.append(dict(tag=tag, inputs=input_name, captures={m:str(p.relative_to(root)) for m,p in paths.items()},
            provenance=provenance, expected=expected))
    cap=root/'capture-kit-captures'
    for tag,name,count in [('sweep','sweep_inputs.txt',50038),('dense','dense_qn.txt',240000)]:
        add(tag,root/'capture-kit/inputs'/name,cap/'skylake-perinsn-20260807',tag+'_fsincos_{m}.txt',
            'capture_manifest_with_retained_shared_positional_input',count)
    for tag in ('h285','h292','h301','h307','h314','h320','h347','h349'):
        directory=cap/('skylake-trig-'+tag)
        add(tag,directory/'inputs.txt',directory,'fsincos_{m}_status.txt','original_input_and_capture_manifest')
    stage=root/'stageA'
    for tag,name in [('comb4','comb4_sincos_inputs.txt'),('h589','h589_inputs.txt'),
                     ('h590f','h590f_inputs.txt'),('h590k','h590k_inputs.txt')]:
        add(tag,stage/name,stage,tag+'_sc_{m}_status.txt','retained_stageA_snapshot_no_original_checksum_manifest')
    record(stage/'ties_comb7.txt'); record(root/'experiments/h624_paired_replica.py')
    add('comb7',None,stage,'comb7_sc_{m}_status.txt',
        'sorted_unique_ties_comb7_significands_as_documented_by_h624_no_original_checksum_manifest',1947982)
    return banks,evidence


def operands(root,bank):
    if bank['inputs']:
        result=(root/bank['inputs']).read_text().splitlines()
    else:
        with (root/'stageA/ties_comb7.txt').open() as f:
            significands=sorted({line.split()[0] for line in f if line.strip()})
        assert all(re.fullmatch('[0-9a-f]{16}', m) for m in significands)
        result=['3ffc '+m for m in significands]
    assert all(re.fullmatch('[0-9a-fA-F]{4} [0-9a-fA-F]{16}',x) for x in result)
    if bank['expected'] is not None: assert len(result)==bank['expected']
    return result


def classify(operand):
    se,s=map(lambda x:int(x,16),operand.split()); ef=se&0x7fff
    if ef==0x7fff or not s or (ef and not s>>63): return 'special'
    e=ef-16383 if ef else -16382
    e += s.bit_length()-64
    if e>=63: return 'range'
    if e < -1 or (e==-1 and s<0xc90fdaa22168c234): top=e; reduced=False
    else:
        a=s<<(e+2); m=0x3243f6a8885a308d3; q,rem=divmod(a,m); q+=2*rem>m
        d=abs(a-q*m); assert d; top=d.bit_length()-1-65; reduced=True
    return ('reduced_' if reduced else 'direct_')+('tiny' if top < -32 else 'polynomial' if top < -2 else 'table')


def score(root,binary,bank,out):
    inputs=operands(root,bank); counts=Counter(); bypath=Counter(); misses=[]; hashes={m:hashlib.sha256() for m in MODES}
    with ExitStack() as stack:
        streams={m:stack.enter_context((root/p).open()) for m,p in bank['captures'].items()}
        for start in range(0,len(inputs),4096):
            batch=inputs[start:start+4096]; predicted={}; raws={}
            for mode in MODES:
                proc=subprocess.run([str(binary),'--batch','--rc='+mode],input=''.join(x+'\n' for x in batch),
                    text=True,capture_output=True,check=True)
                assert not proc.stderr
                predicted[mode]=[parse(l)[0] for l in proc.stdout.splitlines()]
                assert len(predicted[mode])==len(batch)
                hashes[mode].update(proc.stdout.encode())
                raws[mode]=[parse(next(streams[mode]),True) for _ in batch]
            for i,operand in enumerate(batch):
                path=classify(operand)
                for mode in MODES:
                    actual=predicted[mode][i]; expected,sw=raws[mode][i]
                    counts['instruction_rows']+=1; bypath[path]+=1
                    if actual is None or expected is None:
                        miss=actual!=expected; counts['C2_checks']+=1; counts['response_misses']+=miss
                        if miss: misses.append(dict(index=start+i,operand=operand,mode=mode,path=path,hardware=expected,model=actual))
                        continue
                    counts['lane_results']+=2
                    changed=[lane for j,lane in enumerate(('sin','cos')) if actual[j]!=expected[j]]
                    for lane in changed: counts[lane+'_misses']+=1
                    negative=int(actual[1][:4],16)>>15
                    toward=predicted['ru' if negative else 'rd'][i]
                    c1=int(actual[1]!=toward[1])
                    # This is the explicit cosine-bound hypothesis, not a
                    # complete status emulator or a physical-prevalue proof.
                    c1_miss=c1!=((sw>>9)&1)
                    counts['C1_bound_checks']+=1; counts['C1_bound_misses']+=c1_miss
                    if changed or c1_miss:
                        misses.append(dict(index=start+i,operand=operand,mode=mode,path=path,hardware=expected,model=actual,
                            changed_lanes=changed,hardware_C1=(sw>>9)&1,cosine_bound_C1=c1))
            if start and start%262144==0: print(bank['tag'],start,'rows processed',flush=True)
        assert all(f.readline()=='' for f in streams.values())
    result=dict(bank=bank,counts=dict(counts),paths=dict(bypath),misses=misses,
        model_stdout_sha256={m:h.hexdigest() for m,h in hashes.items()})
    save(out/(bank['tag']+'.json'),result)
    print(bank['tag'],json.dumps(dict(counts),sort_keys=True),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--binary',type=Path)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    assert digest(root/'src/fsincos_skylake.c')==SOURCE_SHA
    binary=a.binary.resolve() if a.binary else root/'src/fsincos_skylake'
    banks,evidence=inventory(root);out.mkdir(parents=True)
    save(out/'prepared.json',dict(banks=banks,evidence=evidence,source_sha256=SOURCE_SHA,binary_sha256=digest(binary)))
    totals=Counter(); results=[]
    for bank in banks:
        result=score(root,binary,bank,out);totals.update(result['counts']);results.append(result)
    frontier=[dict(bank=r['bank']['tag'],**miss) for r in results for miss in r['misses']]
    save(out/'frontier.json',frontier)
    report=dict(experiment='h1709_paired_retained_census',counts=dict(totals),frontier_appearances=len(frontier),
        banks=len(banks),hardware_execution='none',private_access='none',source_or_paper_change=False,
        boundary='Retained bank appearances, not unique tuples; C1 is the explicit cosine-directed-bound hypothesis. StageA positional snapshots have weaker provenance than original manifests.',
        sha256=dict(script=digest(Path(__file__)),source=SOURCE_SHA,binary=digest(binary),
            prepared=digest(out/'prepared.json'),frontier=digest(out/'frontier.json'),
            banks={r['bank']['tag']:digest(out/(r['bank']['tag']+'.json')) for r in results}))
    save(out/'report.json',report);print(json.dumps(report,sort_keys=True),flush=True)


if __name__=='__main__': main()
