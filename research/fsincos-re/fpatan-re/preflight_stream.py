"""Compare a local C binary to every immutable frozen gzip prediction."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import threading
from compressed_guard import digest
from prepare import save


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--out',type=Path,help='Separate exclusive-create report for an additional compiler check')
    a=p.parse_args();m=json.loads((a.job/'MANIFEST.json').read_text())
    for name,sha in m['files'].items():assert digest(a.job/name)==sha
    child=subprocess.Popen([str(a.binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);errors=[]
    def feed():
        try:
            with gzip.open(a.job/'inputs.txt.gz','rb') as f:shutil.copyfileobj(f,child.stdin,1<<20)
            child.stdin.close()
        except BaseException as e:errors.append(type(e).__name__)
    thread=threading.Thread(target=feed);thread.start();count=0;misses=0
    with gzip.open(a.job/'predictions.txt.gz','rb') as predictions:
        for expected in predictions:
            actual=child.stdout.readline();assert actual,'Incomplete C output'
            misses+=actual!=expected;count+=1
        assert not child.stdout.read(1)
    thread.join();err=child.stderr.read();rc=child.wait();assert not errors and not rc and not err
    assert count==m['rows'] and not misses
    save(a.out or a.job/'C-PREFLIGHT.json',dict(rows=count,C_frozen_Python_differences=misses,
        binary_sha256=digest(a.binary),hardware_labels_opened=False,stderr_empty=True))
    print('PASS C/frozen Python',count,'rows',flush=True)


if __name__=='__main__':main()
