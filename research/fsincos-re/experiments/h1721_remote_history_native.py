#!/usr/bin/env python3
"""Native fixed-string prefilter for the same read-only public history audit.

Matching whole lines (not -o fragments) preserves overlapping candidate
matches. Python checks all 16-hex substrings on those lines. A decompressor
or search diagnostic is fatal. No hardware capture, deletion or private export.
"""
import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--patterns',required=True,type=Path)
    p.add_argument('--roots',nargs='+',required=True,type=Path);a=p.parse_args()
    wanted=set(a.patterns.read_bytes().lower().split());assert wanted and all(re.fullmatch(rb'[0-9a-f]{16}',x) for x in wanted)
    token=re.compile(rb'[0-9a-fA-F]{16,}');hits=set();counts=Counter();selected=[]
    for root in a.roots:
        assert root.is_dir()
        for path in root.rglob('*'):
            if any(part.startswith('.') for part in path.relative_to(root).parts):continue
            if path.is_symlink() or not path.is_file():continue
            if path.suffix.lower() not in ('.txt','.json','.jsonl','.tsv','.csv','.log','.out','.gz','.bz2','.xz','.zip','.sqlite','.db','.pkl','.pickle','.dat','.c','.h','.py','.sh'):continue
            selected.append(path)
    for path in sorted(set(selected)):
        counts['files']+=1;counts['stored_bytes']+=path.stat().st_size
        command=['grep','-a','-i','-F','-f',str(a.patterns)]
        decoder={'.gz':['gzip','-cd','--'],'.bz2':['bzip2','-cd','--'],'.xz':['xz','-cd','--'],'.zip':['unzip','-p']}.get(path.suffix)
        dec=None
        if decoder:
            dec=subprocess.Popen(decoder+[str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            search=subprocess.Popen(command,stdin=dec.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            dec.stdout.close()
        else:search=subprocess.Popen(command+['--',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for line in search.stdout:
            counts['matching_lines']+=1
            for m in token.finditer(line):
                word=m.group().lower()
                for j in range(len(word)-15):
                    candidate=word[j:j+16]
                    if candidate in wanted:hits.add(candidate)
        search.stdout.close();err=search.stderr.read();code=search.wait()
        if code not in (0,1) or err:raise RuntimeError('public search diagnostic; audit incomplete')
        if dec:
            err=dec.stderr.read();code=dec.wait()
            if code or err:raise RuntimeError('public decompression diagnostic; audit incomplete')
    print(json.dumps(dict(status='PUBLIC_REMOTE_HISTORY_AUDITED',counts=dict(counts),
        matching_candidate_significands=sorted(h.decode() for h in hits),
        patterns_sha256=hashlib.sha256(a.patterns.read_bytes()).hexdigest(),
        roots=[str(r) for r in a.roots],hardware_execution='none',
        limits='Explicit public campaign trees, text/compressed records and ASCII IDs in SQLite; generated inputs need separate domain exclusion.')))


if __name__=='__main__':main()
