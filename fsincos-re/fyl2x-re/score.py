"""Authenticate and compare a completed frozen logarithm discovery pack."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from protocol import validate_inputs, validate_output


def score(job):
    manifest = json.loads((job/'MANIFEST.json').read_text())
    complete = json.loads((job/'COMPLETE.json').read_text())
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for name,want in manifest['files'].items():
        assert digest(job/name) == want
    assert digest(job/'hardware.txt') == complete['hardware_sha256']
    assert digest(job/'MANIFEST.json') == complete['manifest_sha256']
    lines,_ = validate_inputs((job/'inputs.txt').read_text())
    observed = (job/'hardware.txt').read_text().splitlines()
    predictions = (job/'predictions.txt').read_text().splitlines()
    categories = json.loads((job/'categories.json').read_text())
    assert len(lines) == len(observed) == len(predictions) == manifest['rows'] == complete['rows']
    counts=Counter(); misses=[]
    for line,got,pred in zip(lines,observed,predictions):
        h=validate_output(got,line); p=pred.split()
        assert p[0] == line.split()[0]
        result_miss=(h['se'],h['sig']) != (int(p[1],16),int(p[2],16))
        c1_miss=h['C1'] != int(p[3])
        flags_miss=len(p)>4 and (h['sw'] & 63) != int(p[4],16)
        preload_miss=len(p)>5 and (h['before'] & 63) != int(p[5],16)
        op=line.split()[1]; kind=categories[p[0]]
        counts[op+'/rows'] += 1
        if result_miss: counts[op+'/result_misses'] += 1; counts[kind+'/result_misses'] += 1
        if c1_miss: counts[op+'/C1_misses'] += 1
        if flags_miss: counts[op+'/exception_misses'] += 1
        if preload_miss: counts[op+'/preload_misses'] += 1
        if result_miss or c1_miss or flags_miss or preload_miss:
            misses.append(dict(input=line,prediction=pred,hardware=got,category=kind))
    result=dict(status='FROZEN_DISCOVERY_SCORED',counts=dict(counts),mismatched_rows=len(misses),
                inputs_sha256=manifest['files']['inputs.txt'],hardware_sha256=complete['hardware_sha256'])
    (job/'SCORE.json').write_text(json.dumps(result,indent=2)+'\n')
    (job/'misses.json').write_text(json.dumps(misses,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('job',type=Path);score(p.parse_args().job)
