"""Streaming saved-result verification for the compressed corpus format."""
import collections
import gzip
import hashlib
import itertools
import json
from protocol import parse_line,validate_output
from prepare import save
from compressed_guard import digest


def score(job):
    m=json.loads((job/'MANIFEST.json').read_text());complete=json.loads((job/'COMPLETE.json').read_text())
    for name,sha in m['files'].items():assert digest(job/name)==sha
    assert digest(job/'hardware.txt.gz')==complete['hardware_gzip_sha256']
    assert digest(job/'MANIFEST.json')==complete['manifest_sha256']
    counts=collections.Counter();groups=collections.defaultdict(collections.Counter);rawhash=hashlib.sha256()
    pair=None;pcgroups=collections.defaultdict(dict)
    def flush():
        for modes in pcgroups.values():
            if len(modes)==3:
                counts['all_PC_groups']+=1;counts['PC_value_or_status_differences']+=len(set(modes.values()))!=1
        pcgroups.clear()
    with gzip.open(job/'inputs.txt.gz','rt') as inputs,gzip.open(job/'hardware.txt.gz','rt') as hardware,gzip.open(job/'predictions.txt.gz','rt') as predictions,gzip.open(job/'categories.tsv.gz','rt') as categories,gzip.open(job/'candidate-misses.jsonl.gz','xt') as misses:
        for i,h,p,c in itertools.zip_longest(inputs,hardware,predictions,categories):
            assert None not in (i,h,p,c),'length mismatch'
            parse_line(i);o=validate_output(h,i);t=i.split();q=p.split();cid,category=c.rstrip().split('\t')
            assert q[0]==cid==t[0] and len(q)==6
            se,sig,c1,flags,before=(int(s,16) for s in q[1:])
            om=(se,sig)!=(o['se'],o['sig']);cm=c1!=o['C1'];fm=flags!=(o['sw']&63);bm=before!=(o['before']&63)
            for counter in (counts,groups[category],groups['rc-'+t[1]],groups['pc-'+t[2]]):
                counter['rows']+=1;counter['candidate_misses']+=om;counter['candidate_C1_misses']+=cm
                counter['exception_misses']+=fm;counter['before_exception_misses']+=bm
            counts['candidate_C1_checks']+=1;counts['exception_checks']+=1
            counts['IE_set']+=bool(o['sw']&1);counts['UE_set']+=bool(o['sw']&16)
            if tuple(t[3:])!=pair:flush();pair=tuple(t[3:])
            pcgroups[t[1]][t[2]]=o['se'],o['sig'],o['sw']
            if om or cm or fm or bm:
                misses.write(json.dumps(dict(input=i.strip(),kind=category,prediction=[se,sig,c1,flags,before],
                    observed=[o['se'],o['sig'],o['C1'],o['sw']&63,o['before']&63]))+'\n')
            rawhash.update(h.encode('ascii'))
    flush();assert counts['rows']==m['rows']==complete['rows'];assert rawhash.hexdigest()==complete['hardware_sha256']
    report=dict(status='FROZEN_PROSPECTIVE_CORPUS_SCORED',counts=dict(counts),groups={k:dict(v) for k,v in groups.items()},
        hardware_sha256=complete['hardware_sha256'],candidate_frozen_before_capture=True,hardware_executed=False,paper_changed=False)
    save(job/'SCORE.json',report);print(json.dumps(report['counts'],indent=2),flush=True)
