"""Score immutable predictions frozen before capture; never re-run hardware."""
import argparse
import collections
import json
from pathlib import Path
from protocol import validate_output
from prepare import save,digest

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


def main():
    p=argparse.ArgumentParser();p.add_argument('job');a=p.parse_args()
    job=BASE/a.job;manifest=json.loads((job/'MANIFEST.json').read_text())
    assert digest(job/'alternatives.json')==manifest['files']['alternatives.json']
    complete=json.loads((job/'COMPLETE.json').read_text())
    assert digest(job/'hardware.txt')==complete['hardware_sha256']
    alternatives={r['id']:r['predictions'] for r in json.loads((job/'alternatives.json').read_text())}
    categories=json.loads((job/'categories.json').read_text())
    counts=collections.defaultdict(collections.Counter);groups=collections.defaultdict(lambda:collections.defaultdict(collections.Counter))
    for i,h in zip((job/'inputs.txt').read_text().splitlines(),(job/'hardware.txt').read_text().splitlines()):
        o=validate_output(h,i);ident=i.split()[0]
        for name,(se,sig,c1) in alternatives[ident].items():
            for c in (counts[name],groups[name][categories[ident]]):
                c['rows']+=1;c['output_misses']+=(se,sig)!=(o['se'],o['sig']);c['C1_misses']+=c1!=o['C1']
    report=dict(status='FROZEN_ALTERNATIVES_SCORED',counts={k:dict(v) for k,v in counts.items()},
        groups={k:{q:dict(c) for q,c in v.items()} for k,v in groups.items()},hardware_executed=False)
    save(job/'ALTERNATIVES-SCORE.json',report);print(json.dumps(report['counts'],indent=2))


if __name__=='__main__':main()
