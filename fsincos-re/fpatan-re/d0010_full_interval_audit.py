"""Authenticate all saved rows and test RC-independent endpoint feasibility.

This is an architectural consistency check, not a numerical solution. It
includes zero/subnormal outputs, excludes NaN results, and groups PC64 rows
by their exact ordered raw inputs. Missing RC coverage is reported explicitly.
"""
import collections
import gzip
import hashlib
import itertools
import json
from d0010_causal_intervals import BASE,inverse,selftest
from d0008_schedule_replay import digest,opened
from protocol import validate_output,MODES
from prepare import save


def main():
    selftest();results={};overall=collections.Counter()
    for n in range(1,10):
        job=BASE/f'd{n:04d}';m=json.loads((job/'MANIFEST.json').read_text());complete=json.loads((job/'COMPLETE.json').read_text())
        assert digest(job/'MANIFEST.json')==complete['manifest_sha256']
        compressed=m.get('format')=='fpatan-gzip-v2';inp=job/('inputs.txt.gz' if compressed else 'inputs.txt')
        hw=job/('hardware.txt.gz' if compressed else 'hardware.txt');assert digest(inp)==m['files'][inp.name]
        groups={};counts=collections.Counter();sha=hashlib.sha256()
        with opened(inp) as inputs,opened(hw) as hardware:
            for line,out in itertools.zip_longest(inputs,hardware):
                assert line is not None and out is not None
                sha.update(out.encode());counts['authenticated_rows']+=1;o=validate_output(out,line);t=line.split()
                if t[2]!='64':counts['non_PC64_rows']+=1;continue
                if o['se']&32767==32767:counts['nonfinite_output_rows']+=1;continue
                band=inverse(dict(se=o['se'],sig=o['sig'],C1=o['C1'],rc=t[1]));key=tuple(t[3:]);mask=1<<MODES.index(t[1])
                if key in groups:
                    previous,seen,first=groups[key];assert not seen&mask,'Repeated PC64 RC/input tuple'
                    groups[key]=(previous.intersect(band),seen|mask,first)
                else:groups[key]=(band,mask,line.strip())
        assert counts['authenticated_rows']==complete['rows'] and sha.hexdigest()==complete['hardware_sha256']
        contradictions=[]
        for band,mask,line in groups.values():
            counts['full_four_RC_groups' if mask==15 else 'partial_RC_groups']+=1
            counts['exact_point_groups']+=band.valid() and band.lo==band.hi
            if not band.valid():contradictions.append(dict(input=line,modes_mask=mask,interval=band.json()))
        counts['inconsistent_groups']=len(contradictions)
        results[job.name]=dict(counts=dict(counts),contradictions=contradictions,hardware_sha256=sha.hexdigest())
        overall.update(counts);print(job.name,dict(counts),flush=True)
    save(BASE/'d0010-full-interval-audit.json',dict(status='ENDPOINT_FEASIBILITY_NOT_ALGORITHM_CLOSURE',jobs=results,
         counts=dict(overall),hardware_executed=False))


if __name__=='__main__':main()
