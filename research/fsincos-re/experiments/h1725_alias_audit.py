#!/usr/bin/env python3
"""Identify extra public input aliases not covered by the native inventory."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);a=p.parse_args()
cfg=json.loads(a.config.read_text());sizes={r['bytes'] for r in cfg['known_inputs'].values()}
hashes={r['sha256'] for r in cfg['known_inputs'].values()};aliases=[];seen=set()
for root in cfg['roots']:
    for path in Path(root).rglob('*.txt'):
        if path.is_symlink() or not path.is_file() or path in seen:continue
        seen.add(path)
        if any(str(path)==s or str(path).startswith(s+'/') for s in cfg['software_only_roots']):continue
        if str(path) in cfg['known_inputs'] or path.stat().st_size not in sizes:continue
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1<<20),b''):h.update(block)
        if h.hexdigest() in hashes:aliases.append(dict(path=str(path),sha256=h.hexdigest()))
print(json.dumps(dict(status='PUBLIC_INPUT_ALIAS_AUDIT_COMPLETE',aliases=aliases,hardware_execution='none')))
