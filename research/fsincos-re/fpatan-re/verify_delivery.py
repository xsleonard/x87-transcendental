"""Authenticate every recorded FPATAN job and replay a delivered C binary.

Runs only the local reconstruction. Hardware results are immutable evidence;
the original per-job frozen scores remain unchanged, including old failures.
This proves corpus agreement, not exhaustive raw80 or cross-CPU coverage.
"""
import argparse
import collections
import json
from pathlib import Path

from d0008_schedule_replay import BASE, digest, replay
from prepare import save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--jobs',nargs='+',help='Defaults to every frozen job; unfinished jobs fail closed')
    args=parser.parse_args()
    assert not args.out.exists()
    jobs=args.jobs or sorted(p.parent.name for p in BASE.glob('d[0-9][0-9][0-9][0-9]/MANIFEST.json'))
    assert jobs and len(jobs)==len(set(jobs))
    report=dict(status='AUTHENTICATED_SAVED_CORPUS_REPLAY',hardware_executed=False,
        binary_sha256=digest(args.binary),jobs={},counts={},
        limitations='No exhaustive all-raw80 or cross-CPU proof is asserted.',
        sources={name:digest(Path(__file__).with_name(name)) for name in
            ('fpatan_candidate.c','fpatan_library.c','fpatan_library.h',
             'example_batch.c','protocol.py','d0008_schedule_replay.py','verify_delivery.py')})
    totals=collections.Counter()
    for name in jobs:
        assert Path(name).name==name and name.startswith('d')
        root=BASE/name
        m=json.loads((root/'MANIFEST.json').read_text())
        start=json.loads((root/'STARTED.json').read_text())
        complete=json.loads((root/'COMPLETE.json').read_text())
        assert complete['state']=='OBSERVED'
        assert start['identity'].split()[1]==m['expected_signature']=='00050654'
        assert start['microcode']==[m['expected_microcode']]==['0x1']
        assert start['manifest_sha256']==complete['manifest_sha256']==digest(root/'MANIFEST.json')
        if (root/'hardware.txt.gz').exists():
            assert digest(root/'hardware.txt.gz')==complete['hardware_gzip_sha256']
        source_locations={}
        for source,sha in m['source_pins'].items():
            original=root/'sources'/source
            # D0001 predates per-job source copies. Its source bytes are
            # still available unchanged; require the original pinned hash,
            # and report this resolution rather than inventing a snapshot.
            resolved=original if original.exists() else Path(__file__).with_name(source)
            assert digest(resolved)==sha
            source_locations[source]='frozen-copy' if original.exists() else 'current-identical-to-original-pin'
        result=replay(args.binary.resolve(),None,name)
        result['original_source_resolution']=source_locations
        report['jobs'][name]=result
        totals.update(result['counts'])
        print(name,result['counts'],flush=True)
    report['counts']=dict(totals)
    save(args.out,report)
    assert all(not count for key,count in totals.items() if key!='rows'), 'Recorded mismatches: inspect the report'
    print('PASS',len(jobs),'authenticated jobs;',totals['rows'],'rows; all recorded output/status fields exact',flush=True)


if __name__=='__main__':main()
