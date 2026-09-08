#!/usr/bin/env python3
"""Build the isolated tiny predecessor rule and audit complete mixed banks.

Uses the unchanged H1630/H1633 polynomial/table headers. R84 is OFF. The
H1637 integer specification checks every tiny output/C1 and route metadata.
No hardware, private-ledger access, canonical/default or paper change.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
import h1633_shared_table_audit as table
import h1637_tiny_closed_form_audit as spec

PARENT='tmp/ledger33/current/h1633_shared_table_audit/'
TINY='tmp/ledger33/current/h1637_tiny_closed_form_audit/'
FRONTIER='tmp/ledger33/current/h1632_legacy_and_frontier_transfer/report.json'
LOCKS={
    **table.LOCKS,
    PARENT+'report.json':'935a4352843b0b0b96559fb4447fc1a329b0da9d5530c85790b622b3bc5bb51c',
    TINY+'report.json':'a18fb1a7a9dad745e7fea87430bfa1820273a52d43e99a175a8de5becb0d7158',
    FRONTIER:'6889b6f933c226e4722d12ac28106ed1dd5ac22deb2c5a62ce11479c092d34b7',
    'experiments/h1633_shared_table.h':'238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1633_shared_table_audit.py':'3f23458fff3cc1b4965215554874eb011d53283ab18c93a6fa8fce933bbf864b',
    'experiments/h1637_tiny_closed_form_audit.py':'ea6e22d450dda2d5046d1ed309d971b2d50a8434cc5b934b7413995c81ebf0f2',
}


def source_string(root):
    source=table.source_string(root)
    for insn,phase in (('fsin',0),('fcos',1)):
        out='sin_out' if not phase else 'cos_out'
        anchor=f'static fsincos_status_t {insn}_ref(x80_t in, x80_t *{out}, sf_rc_t rc)\n{{'
        assert source.count(anchor)==1
        hook=f'''\n    /* H1638 isolated tiny rule; unchanged fallback for every other path. */
    if (G_H1638_TINY && h1638_tiny_entry(in, {phase}, rc, {out}))
        return FSINCOS_OK;
'''
        source=source.replace(anchor,('#include "h1638_tiny_closed_form.h"\n\n' if not phase else '')+anchor+hook)
    return source


def run(binary,instruction,mode,operands):
    proc=subprocess.run([str(binary),'--batch','--'+instruction+'-standalone','--rc='+mode],
        input=''.join(op+'\n' for op in operands),text=True,capture_output=True,check=True)
    values=[table.records.parse_output(line) for line in proc.stdout.splitlines()]
    assert len(values)==len(operands)
    metadata={}
    for line in proc.stderr.splitlines():
        words=line.split(); index=int(words[1]); assert 0<=index<len(operands) and index not in metadata
        if words[0]=='HTINY':
            assert len(words)==9
            fields=('reduced','cosine','bypass','negative','C1','input_top','residual_top')
            meta=dict(zip(fields,map(int,words[2:])),lane='tiny')
        else:
            assert words[0] in ('HTABLE','HPOLY')
            lane='table' if words[0]=='HTABLE' else 'polynomial'
            fields=('cosine','top','b','precision','residual_sign','negative','C1') if lane=='table' else ('cosine','top','precision','residual_sign','negative','C1')
            assert len(words)==len(fields)+3
            meta=dict(zip(fields,map(int,words[2:-1])),lane=lane,magnitude=words[-1])
        metadata[index]=meta
    return values,metadata,proc.stdout


def check_spec(op,instruction,mode,value,meta):
    expected=spec.evaluate(op,instruction,mode)
    tiny=expected['C1'] is not None
    assert tiny==(meta is not None and meta['lane']=='tiny')
    if tiny:
        assert expected['output']==value and expected['C1']==meta['C1']
        assert expected['reduced']==bool(meta['reduced'])
        assert expected['input_top']==meta['input_top']
        assert ('bypass' in expected['path'])==bool(meta['bypass'])
        assert expected['path'].endswith('cosine')==bool(meta['cosine'])
        assert int(value[:4],16)>>15==meta['negative']
        if not meta['bypass']: assert expected['residual_top']==meta['residual_top']
    elif expected['output'] is not None: assert expected['output']==value
    return tiny


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve(); assert not output.exists()
    digest=table.records.digest; evidence=dict(LOCKS)
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    parent=json.loads((root/PARENT/'report.json').read_text())
    tiny_report=json.loads((root/TINY/'report.json').read_text())
    for report in (parent,tiny_report):
        for name,expected in report['sha256']['evidence'].items():
            assert digest(root/name)==expected,name
            evidence[name]=expected
    for name,expected in tiny_report['sha256']['artifacts'].items(): assert digest(root/TINY/name)==expected,name
    inventories=json.loads((root/TINY/'prepared.json').read_text())['inventories']
    source=source_string(root)
    evidence['experiments/h1638_tiny_closed_form.h']=digest(root/'experiments/h1638_tiny_closed_form.h')
    output.mkdir(parents=True)
    table.records.save(output/'prepared.json',dict(state='SOFTWARE_ONLY_TINY_C_TRANSFER',inventories=inventories,
        sha256=dict(script=digest(Path(__file__)),source=hashlib.sha256(source.encode()).hexdigest(),evidence=evidence)))
    binaries={}
    for label,(enabled,flags) in table.poly.CONFIGS.items():
        binary=output/label
        proc=subprocess.run(['cc',*flags,'-std=c11','-DG_ROUND84=0','-DG_H1630_POLYNOMIAL=1','-DG_H1633_TABLE=1',
            '-DG_H1638_TINY='+str(enabled),'-I',str(root/'src'),'-I',str(root/'experiments'),'-x','c','-','-lm','-o',str(binary)],
            input=source,text=True,capture_output=True,check=True)
        assert not proc.stderr
        test=subprocess.run([str(binary),'--selftest'],text=True,capture_output=True,check=True)
        assert test.stdout=='SELFTEST: ok\n' and not test.stderr
        binaries[label]=binary
    baseline=root/PARENT/'candidate_O2'; assert digest(baseline)==parent['sha256']['binaries']['candidate_O2']
    # Broad software encoding/threshold bank. Exceptional fallback is only
    # software equality here, not additional special-value hardware evidence.
    software=set()
    for ef in (0,1,2,0x3fba,0x3fbb,0x3fbc,0x3fdd,0x3fde,0x3fdf,0x3fe0,0x3ffd,0x3ffe,0x3fff,0x4000,0x403d,0x403e,0x7ffe,0x7fff):
        for sign in (0,0x8000):
            for sig in (0,1,(1<<62),(1<<63)-1,1<<63,(1<<63)+1,0xc000000000000000,0xc90fdaa22168c234,(1<<64)-1):
                software.add(f'{sign|ef:04x} {sig:016x}')
    # Canonical M66 near-multiples furnish independently checked reduced
    # tiny cases without ever issuing a hardware instruction.
    for q in (1,2,3,4,7,16,31,64,127):
        v=q*spec.M66; width=v.bit_length(); e=width-1-65
        sig=v>>(width-64)
        for d in (-1,0,1):
            for sign in (0,0x8000): software.add(f'{sign|e+16383:04x} {sig+d:016x}')
    software=sorted(software); preflight=Counter()
    for insn in ('fsin','fcos'):
        for mode in ('rn','rd','ru','rz'):
            base,base_meta,_=run(baseline,insn,mode,software)
            reference=None
            for label,binary in binaries.items():
                values,metadata,_=run(binary,insn,mode,software)
                assert values==base
                if label=='disabled_O2': assert metadata==base_meta; continue
                if reference is None: reference=values,metadata
                assert (values,metadata)==reference
                for i,value in enumerate(values):
                    hit=check_spec(software[i],insn,mode,value,metadata.get(i))
                    preflight['rows']+=1; preflight['tiny_rows']+=hit
                    if not hit: assert metadata.get(i)==base_meta.get(i)
    table.records.save(output/'software_preflight.json',dict(operands=software,counts=dict(preflight),hardware_observations=0))
    print('PREFLIGHT PASS',dict(preflight),flush=True)
    totals,reports=Counter(),[]
    for b in inventories:
        operands=(root/b['inputs']).read_text().splitlines(); hardware=(root/b['capture']).read_text().splitlines()
        assert len(operands)==len(hardware)==b['count']; directory=output/b['tag']; directory.mkdir()
        counts=Counter()
        with ExitStack() as stack:
            streams={label:(table.records.zipped(stack,directory/(label+'.stdout.gz')),table.records.zipped(stack,directory/(label+'.metadata.jsonl.gz'))) for label in binaries if label!='disabled_O2'}
            for start in range(0,len(operands),4096):
                batch=operands[start:start+4096]; base,base_meta,_=run(baseline,b['instruction'],b['mode'],batch); reference=None
                for label,binary in binaries.items():
                    if label=='disabled_O2': continue
                    values,metadata,stdout=run(binary,b['instruction'],b['mode'],batch)
                    assert values==base
                    if reference is None: reference=values,metadata
                    assert (values,metadata)==reference
                    streams[label][0].write(stdout.encode())
                    for i,meta in sorted(metadata.items()): streams[label][1].write((json.dumps(dict(index=start+i,**meta),sort_keys=True)+'\n').encode())
                    for i,value in enumerate(values):
                        meta=metadata.get(i); hit=check_spec(batch[i],b['instruction'],b['mode'],value,meta)
                        actual,sw=spec.raw_reader.raw(hardware[start+i],True)
                        assert actual==value
                        if meta: assert meta['C1']==(sw>>9)&1
                        if not hit: assert meta==base_meta.get(i)
                        if label=='candidate_O2':
                            counts['observed_rows']+=1
                            lane=meta['lane'] if meta else 'fallback'; counts[lane+'_rows']+=1
                            if meta: counts[lane+'_output_C1_checks']+=1
                counts['compiler_row_checks']+=len(batch)*4
        reports.append(dict(bank=b['tag'],counts=dict(counts),sha256={p.name:digest(p) for p in sorted(directory.iterdir())}))
        totals.update(counts); print(b['tag'],dict(counts),flush=True)
    old=json.loads((root/FRONTIER).read_text()); frontier_checks={}
    for name in ('frontier','legacy'):
        rows=old['results'][name]['builds']['candidate_O2']['rows']; checks={}
        for label,binary in binaries.items():
            if label=='disabled_O2': continue
            details=[]
            for insn,mode in sorted({(r['instruction'],r['mode']) for r in rows}):
                selected=[r for r in rows if (r['instruction'],r['mode'])==(insn,mode)]
                values,metadata,_=run(binary,insn,mode,[r['operand'] for r in selected])
                for i,(row,value) in enumerate(zip(selected,values)):
                    assert value==row['hardware'] and metadata[i]['lane']=='polynomial'
                    if row['hardware_C1'] is not None: assert metadata[i]['C1']==row['hardware_C1']
                    details.append(dict(instruction=insn,mode=mode,operand=row['operand'],output=value,metadata=metadata[i]))
            checks[label]=details
        assert all(v==checks['candidate_O2'] for v in checks.values())
        frontier_checks[name]=checks
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    result=dict(experiment='h1638_tiny_c_transfer',status='PASS_TINY_C_AND_UNCHANGED_OTHER_PATHS',counts=dict(totals),banks=reports,
        frontier_checks=frontier_checks,preflight=dict(preflight),hardware_execution='none',private_ledger_access='none',canonical_default_or_paper_change='none',
        claim_boundary='Four compiler builds over retained mixed banks; tiny outputs/C1 newly implemented, polynomial/table numerical metadata unchanged. Software exceptional coverage is not hardware validation. No full status/PC/stack/unmasked API or universal silicon proof.',
        sha256=dict(script=digest(Path(__file__)),prepared=digest(output/'prepared.json'),evidence=evidence,binaries={k:digest(v) for k,v in binaries.items()}))
    table.records.save(output/'report.json',result); print(result['status'],dict(totals),flush=True)


if __name__=='__main__': main()
