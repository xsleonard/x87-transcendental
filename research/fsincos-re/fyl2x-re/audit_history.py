"""Read-only audit of public research-host files for prior FYL2X usage.

Run BEFORE uploading any FYL2X capture job. Does not scan unrelated projects
or private local supplemental records. A positive finding requires manual
reconciliation; it cannot authorize a new capture. No hardware instructions.
"""
import bz2
import gzip
import json
import lzma
from pathlib import Path
import re
import tarfile
import time
import zipfile


def main():
    roots=sorted(p for p in Path('/root').iterdir() if
        (p.is_dir() and (p.name.startswith(('fsincos','fpatan','fptan','f2xm1')) or re.fullmatch(r'h\d+.*',p.name))))
    hits=[];files=0;byte_count=0;unread=[]
    def scan(stream,name):
        nonlocal byte_count
        tail=b''
        while True:
            b=stream.read(1<<20)
            if not b:break
            byte_count+=len(b)
            if b'fyl2x' in (tail+b).lower():hits.append(name);break
            tail=b[-6:]
    suffixes={'.c','.h','.py','.sh','.md','.txt','.json','.jsonl','.log','.tsv','.csv','.out','.gz','.xz','.bz2','.zip','.tgz','.tar'}
    for root in roots:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.is_symlink():continue
            if 'fyl2x' in path.name.lower():hits.append(str(path)+' [filename]')
            if path.suffix not in suffixes:continue
            files+=1
            try:
                with path.open('rb') as raw: magic=raw.read(4)
                if magic==b'\x00\x05\x16\x07':
                    # macOS AppleDouble sidecars inherit the payload suffix
                    # but are metadata containers, not compressed payloads.
                    # Scan their actual bytes rather than silently skip them.
                    with path.open('rb') as f:scan(f,str(path))
                elif path.name.endswith(('.tar.gz','.tgz','.tar','.tar.xz','.tar.bz2')):
                    with tarfile.open(path,'r:*') as archive:
                        for member in archive:
                            if member.isfile():
                                with archive.extractfile(member) as f:scan(f,str(path)+':'+member.name)
                elif path.suffix=='.zip':
                    with zipfile.ZipFile(path) as archive:
                        for member in archive.infolist():
                            if not member.is_dir():
                                with archive.open(member) as f:scan(f,str(path)+':'+member.filename)
                else:
                    opener={'.gz':gzip.open,'.bz2':bz2.open,'.xz':lzma.open}.get(path.suffix,open)
                    with opener(path,'rb') as f:scan(f,str(path))
            except (OSError,EOFError,ValueError,tarfile.TarError,zipfile.BadZipFile) as e:
                unread.append(dict(path=str(path),error=type(e).__name__))
    # Export aggregate clearance only. Even public research filenames and
    # matching text stay on the host; a positive result cannot clear a run.
    print(json.dumps(dict(status='NO_PRIOR_FYL2X_FOUND' if not hits and not unread else 'REVIEW_REQUIRED',
        root_count=len(roots),files=files,bytes_scanned=byte_count,hits=len(hits),unread=len(unread),
        hardware_executed=False,time=time.time(),
        limits='Text/source/archive audit of existing public x87 research roots; local private/corpus pair checks are separate. Unrelated project trees excluded.'),indent=2))


if __name__=='__main__':main()
