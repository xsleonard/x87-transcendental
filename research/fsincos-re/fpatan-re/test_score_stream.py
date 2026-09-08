"""Positive and mutation tests of streaming score, using saved observations."""
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
from compressed_guard import digest
from prepare import save
from protocol import validate_output
from score_stream import score


def main():
    base=Path(tempfile.mkdtemp(prefix='fpatan-scorer-test-'))
    old=Path(__file__).resolve().parents[1]/'tmp/fpatan-re/d0007'
    with (old/'inputs.txt').open() as f:inputs=list(itertools.islice(f,12))
    with (old/'hardware.txt').open() as f:hardware=list(itertools.islice(f,12))
    for mutation in (False,True):
        job=base/('mutated' if mutation else 'exact');job.mkdir();predictions=[];categories=[]
        for index,(i,h) in enumerate(zip(inputs,hardware)):
            o=validate_output(h,i);ident=i.split()[0];toggle=int(mutation and index==0)
            predictions.append(f"{ident} {o['se']:04x} {o['sig']^toggle:016x} {o['C1']^toggle} {(o['sw']&63)^toggle:02x} {(o['before']&63)^toggle:02x}\n")
            categories.append(ident+'\tsaved-fixture\n')
        streams={'inputs.txt.gz':inputs,'hardware.txt.gz':hardware,'predictions.txt.gz':predictions,'categories.tsv.gz':categories}
        for name,lines in streams.items():
            with gzip.open(job/name,'wt') as f:f.writelines(lines)
        save(job/'MANIFEST.json',dict(rows=12,files={n:digest(job/n) for n in streams if n!='hardware.txt.gz'},status='SYNTHETIC_REPLAY_FIXTURE'))
        save(job/'COMPLETE.json',dict(rows=12,hardware_sha256=hashlib.sha256(''.join(hardware).encode()).hexdigest(),
            hardware_gzip_sha256=digest(job/'hardware.txt.gz'),manifest_sha256=digest(job/'MANIFEST.json')))
        score(job);c=json.loads((job/'SCORE.json').read_text())['counts']
        for k in ('candidate_misses','candidate_C1_misses','exception_misses','before_exception_misses'):assert c[k]==int(mutation)
    print('PASS streaming positive/mutation scoring; saved data only, no hardware')


if __name__=='__main__':main()
