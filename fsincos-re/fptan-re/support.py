"""Local/public artifact utilities. No numerical model or private data."""
import gzip
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'tmp/fptan-re'


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            result.update(block)
    return result.hexdigest()


def save(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def read(path):
    return json.loads(Path(path).read_text())


def copy(source, target):
    import shutil
    with Path(source).open('rb') as original, Path(target).open('xb') as dest:
        shutil.copyfileobj(original, dest)


def lines(path):
    with gzip.open(path, 'rt', encoding='ascii') as stream:
        yield from stream
