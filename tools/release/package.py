"""Create a source-only package from the maintained product allowlist.

No source generation, hardware capture, upload, deletion or license assignment.
Existing output packages are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
DIRECTORIES=('include','src','cmake','tests','examples','tools/cli','tools/compat',
             'tools/integration','integrations/bochs')
ROOT_FILES=('CMakeLists.txt','Makefile','README.md','SOURCE.md','AGENTS.md','.clang-format',
            'LICENSE.md','COPYING','COPYING.LESSER')
DOCS=('api.md','integration.md','validation.md','provenance.md',
      'research-sources.md','bochs.md','finite-arithmetic.md',
      'code-documentation-guidelines.md')
SUFFIXES={'.c','.h','.cmake','.in','.py','.json','.txt','.md','.tsv','.inc','.gz'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output=args.output or ROOT/'output/release'/f'x87trans-0.2.0-{stamp}.tar.gz'
    paths=[ROOT/p for p in ROOT_FILES]
    paths += [ROOT/'docs'/p for p in DOCS]
    paths += sorted((ROOT/'docs/algorithms').glob('*.md'))
    paths += [ROOT/'tools/release/package.py']
    for directory in DIRECTORIES:
        paths += sorted(p for p in (ROOT/directory).rglob('*')
            if p.is_file() and not p.is_symlink() and p.suffix in SUFFIXES
            and '__pycache__' not in p.parts)
    paths=sorted(set(paths))
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream, tarfile.open(fileobj=stream,mode='w:gz') as archive:
        for path in paths:
            archive.add(path,arcname='x87trans-0.2.0/'+str(path.relative_to(ROOT)),recursive=False)
        import io
        data=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
        info=tarfile.TarInfo('x87trans-0.2.0/SOURCE-MANIFEST.json')
        info.size=len(data);info.mode=0o644
        archive.addfile(info,io.BytesIO(data))
    print(json.dumps(dict(archive=str(output),files=len(paths),
        sha256=hashlib.sha256(output.read_bytes()).hexdigest(),license='LGPL-3.0-only')))

if __name__=='__main__':main()
