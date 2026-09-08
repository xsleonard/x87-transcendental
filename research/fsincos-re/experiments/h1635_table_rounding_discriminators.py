#!/usr/bin/env python3
"""Check H1634's double-rounding witnesses in C, plus current frontier transfer.

Compile only isolated analysis binaries; preserve every prior artifact and
canonical/default source. No hardware or private-ledger access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
import h1633_shared_table_audit as table

PARENT='tmp/ledger33/current/h1633_shared_table_audit/'
INDEPENDENT='tmp/ledger33/current/h1634_independent_table_certificate/report.json'
FRONTIER='tmp/ledger33/current/h1632_legacy_and_frontier_transfer/report.json'
LOCKS={
    **table.LOCKS,
    PARENT+'report.json':'935a4352843b0b0b96559fb4447fc1a329b0da9d5530c85790b622b3bc5bb51c',
    FRONTIER:'6889b6f933c226e4722d12ac28106ed1dd5ac22deb2c5a62ce11479c092d34b7',
    'experiments/h1634_independent_table_certificate.py':'41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa',
    'experiments/h1633_shared_table.h':'238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1633_shared_table_audit.py':'3f23458fff3cc1b4965215554874eb011d53283ab18c93a6fa8fce933bbf864b',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--independent-sha256',required=True)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve()
    assert not output.exists()
    evidence={**LOCKS,INDEPENDENT:args.independent_sha256}
    for name,expected in evidence.items(): assert table.records.digest(root/name)==expected,name
    parent=json.loads((root/PARENT/'report.json').read_text())
    independent=json.loads((root/INDEPENDENT).read_text())
    frontier=json.loads((root/FRONTIER).read_text())
    assert independent['status']=='PASS'
    selected=independent['double_rounding_counterexamples']; assert selected
    source=table.source_string(root)
    header=(root/'experiments/h1633_shared_table.h').read_text()
    needle='return p5_wv_mul_round(x, y, 64, P5_ROUND_RN);'
    assert header.count(needle)==1
    altered=header.replace(needle,'''/* H1635 negative control: deliberately add a CHOP67 intermediate. */
    return p5_wv_mul_round(p5_wv_mul_round(x, y, 67, P5_ROUND_CHOP),
                            one, 64, P5_ROUND_RN);''')
    assert source.count('#include "h1633_shared_table.h"')==1
    source=source.replace('#include "h1633_shared_table.h"',altered)
    output.mkdir(parents=True)
    binaries={}
    for label,flags in (('double_round_O2',['-O2']),('double_round_ubsan',['-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined'])):
        binary=output/label
        proc=subprocess.run(['cc',*flags,'-std=c11','-DG_ROUND84=0','-DG_H1630_POLYNOMIAL=1','-DG_H1633_TABLE=1',
            '-I',str(root/'src'),'-I',str(root/'experiments'),'-x','c','-','-lm','-o',str(binary)],input=source,text=True,capture_output=True,check=True)
        assert not proc.stderr; binaries[label]=binary
    for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan'):
        binary=root/PARENT/label
        assert table.records.digest(binary)==parent['sha256']['binaries'][label]
        binaries[label]=binary
    # Reauthenticate the exact positional raw lines, not only the copied
    # witness labels in the independent report.
    prepared=json.loads((root/PARENT/'prepared.json').read_text())
    inventories={b['tag']:b for b in prepared['inventories']}
    for name,expected in parent['sha256']['evidence'].items(): assert table.records.digest(root/name)==expected,name
    for row in selected:
        bank=inventories[row['bank']]; assert bank['instruction']==row['instruction']
        assert (root/bank['inputs']).read_text().splitlines()[row['index']]==row['operand']
        hardware,sw=table.records.parse_output((root/bank['captures'][row['mode']]).read_text().splitlines()[row['index']],True)
        assert hardware==row['hardware'] and (sw>>9)&1==row['hardware_C1']
    results={}
    banks={'double_rounding_discriminators':selected}
    for name in ('frontier','legacy'):
        banks[name]=frontier['results'][name]['builds']['candidate_O2']['rows']
    for name,rows in banks.items():
        checks={}
        for label,binary in binaries.items():
            if label.startswith('double_round') and name!='double_rounding_discriminators': continue
            details=[]; counts=Counter()
            for insn,mode in sorted({(r['instruction'],r['mode']) for r in rows}):
                subset=[r for r in rows if (r['instruction'],r['mode'])==(insn,mode)]
                values,metadata,_,_=table.run(binary,insn,mode,[r['operand'] for r in subset])
                for i,(row,value) in enumerate(zip(subset,values)):
                    meta=metadata[i]; c1=meta['C1']; known=row.get('hardware_C1')
                    expected=row['double_rounded_output'] if label.startswith('double_round') else row['hardware']
                    expected_c1=row['double_rounded_C1'] if label.startswith('double_round') else known
                    assert value==expected and (expected_c1 is None or c1==expected_c1)
                    counts['rows']+=1; counts['hardware_output_misses']+=value!=row['hardware']
                    counts['known_C1']+=known is not None; counts['hardware_C1_misses']+=known is not None and c1!=known
                    counts[meta['lane']+'_rows']+=1
                    details.append(dict(instruction=insn,mode=mode,operand=row['operand'],output=value,C1=c1,hardware=row['hardware'],hardware_C1=known,lane=meta['lane']))
            checks[label]=dict(counts=dict(counts),rows=details)
        for label in ('candidate_O0','candidate_O3','candidate_ubsan'): assert checks[label]==checks['candidate_O2']
        if name=='double_rounding_discriminators': assert checks['double_round_O2']==checks['double_round_ubsan']
        results[name]=checks
        print(name,{k:v['counts'] for k,v in checks.items()},flush=True)
    result=dict(experiment='h1635_table_rounding_discriminators',status='PASS_C_REPRODUCTION_AND_FRONTIER',results=results,
        claim_boundary='Selected retained witnesses confirm the negative control, not an exhaustive new bank or fresh observation. Legacy hardware-line provenance remains weaker than indexed raw streams. Polynomial frontier transfer is regression, not new table coverage. No hardware/default/paper/private-ledger action.',
        sha256=dict(script=table.records.digest(Path(__file__)),altered_source=hashlib.sha256(source.encode()).hexdigest(),evidence=evidence,binaries={k:table.records.digest(v) for k,v in binaries.items()}))
    table.records.save(output/'report.json',result)


if __name__=='__main__': main()
