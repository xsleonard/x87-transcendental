#!/usr/bin/env python3
"""Audit corpus uniqueness, fixture inclusion, exports and independent core predictions."""
import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite
import h1714_rounding_challenge as independent
from h1709_paired_retained_census import save


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    directory=root/'corpus-suite/corpus-v1';manifest=suite.verify_dataset(directory)
    counts=Counter();core=[];smoke=[];previous=None;sources=json.loads((directory/'sources.json').read_text())
    old=root/'corpus-suite/releases/h1716-v1-original/corpus-v1'
    suite.verify_dataset(old)
    prior_stream=gzip.open(old/'operands.tsv.gz','rt');prior_reader=csv.DictReader(prior_stream,delimiter='\t')
    prior=next(prior_reader,None);preserved=0
    with gzip.open(directory/'operands.tsv.gz','rt') as f:
        for row in csv.DictReader(f,delimiter='\t'):
            op=row['se']+' '+row['sig'];suite.case_id('fsin','rn',64,op)
            assert previous is None or previous<op;previous=op;counts['full']+=1
            flags=int(row['profiles']);assert flags&~3==0 and 0<int(row['sources'],16)<1<<len(sources)
            if prior is not None:
                prior_op=prior['se']+' '+prior['sig'];assert prior_op>=op,('missing prior operand',prior_op)
                if prior_op==op:
                    assert flags&int(prior['profiles'])==int(prior['profiles'])
                    assert int(row['sources'],16)&int(prior['sources'],16)==int(prior['sources'],16)
                    preserved+=1;prior=next(prior_reader,None)
            if flags&1:core.append(op);counts['core']+=1
            if flags&2:assert flags&1;smoke.append(op);counts['smoke']+=1
    assert prior is None and preserved==4010549;prior_stream.close()
    assert {k:v['operands'] for k,v in manifest['profiles'].items()}==dict(counts)
    selected=set(core);included={}
    mandatory=json.loads((directory/'mandatory-misses.json').read_text())['operands']
    assert set(mandatory)<=set(smoke)<=selected
    assert '3ffc e79000000c3e46e7' in mandatory
    for campaign in ('h1712','h1714','h1715'):
        rows=json.loads((root/'transfer-tests'/campaign/'manifest.json').read_text());ops={r['operand'] for r in rows}
        assert ops<=selected;included[campaign]=len(ops)
    all_cases=set();export_counts={}
    for profile in ('core','smoke'):
        export=root/'corpus-suite'/('jobs-'+profile);spec=json.loads((export/'EXPORT.json').read_text());cases=set()
        for job in spec['jobs']:
            path=export/job['directory'];assert suite.digest(path/'JOB.json')==job['job_sha256']
            info=json.loads((path/'JOB.json').read_text());assert suite.digest(path/'inputs.txt')==info['inputs_sha256']
            lines=(path/'inputs.txt').read_text().splitlines();assert len(lines)==info['rows']
            for line in lines:
                case=line.split()[0];assert suite.capture_line(case)==line and case not in cases
                insn,mode,pc,op=suite.decode_case(case);assert op in selected;cases.add(case)
        assert len(cases)==counts[profile]*36==spec['exported_rows'];export_counts[profile]=len(cases)
        if profile=='core':all_cases=cases
        else:assert cases<=all_cases
    independent.independent.constants(root);cache={};checks=Counter()
    for insn in independent.INSTRUCTIONS:
        for mode in independent.MODES:
            c=independent.c_predictions(root/'src/fsincos_skylake',insn,mode,core)
            for op,actual in zip(core,c):
                if insn=='fsincos':
                    value,meta=independent.independent.expected(op,mode,'all',cache)
                    expected=dict(outputs=list(value) if value else None,C1=meta[3] if meta and meta[1] else None)
                else:expected=independent.prediction(op,insn,mode,cache)
                assert expected['outputs']==actual['outputs'],(op,insn,mode,expected,actual)
                checks['instruction_rows']+=1;checks['output_lanes']+=len(expected['outputs'] or [])
                if expected['C1'] is not None:
                    assert expected['C1']==actual['C1'],(op,insn,mode,expected,actual);checks['known_C1']+=1
            print('CORE independent',insn,mode,'PASS',flush=True)
    out.mkdir(parents=True);report=dict(status='PASS_CORPUS_AND_INDEPENDENT_CORE',unique_operands=dict(counts),
        included_adversarial_operands=included,exported_unique_cases=export_counts,independent_checks=dict(checks),
        preserved_previous_operands=preserved,mandatory_miss_and_legacy_inputs=len(mandatory),hardware_executions=0,private_access=False,
        limits='Core exact predictions are software checks, not new hardware labels. Full corpus membership and dedup are verified; full Cartesian matrix has not been observed on the reference CPU.',
        sha256=dict(corpus_manifest=suite.digest(directory/'MANIFEST.json'),script=suite.digest(Path(__file__)),
            main_source=suite.digest(root/'src/fsincos_skylake.c'),main_binary=suite.digest(root/'src/fsincos_skylake')))
    save(out/'report.json',report);print(json.dumps(report,sort_keys=True),flush=True)


if __name__=='__main__':main()
