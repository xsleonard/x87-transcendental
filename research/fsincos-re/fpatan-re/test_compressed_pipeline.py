"""Exercise gzip capture/commit/failure recovery using a synthetic process."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from unittest.mock import patch
import compressed_guard as guard
from protocol import make_line


def main():
    base=Path(tempfile.mkdtemp(prefix='fpatan-pipeline-test-'));here=Path(__file__).resolve().parent
    def make_job(name,offset):
        job=base/name;job.mkdir()
        for f in ('capture.c','protocol.py','compressed_guard.py'):shutil.copy2(here/f,job/f)
        shutil.copy2(here/'test_capture_simulator.py',job/'capture');(job/'capture').chmod(0o700)
        with gzip.open(job/'inputs.txt.gz','wt') as f:
            for pc in (24,53,64):
                for rc in ('rn','rd','ru','rz'):f.write(make_line(rc,pc,0x3fff,(1<<63)+offset,0x3fff,1<<63)+'\n')
        guard.save(job/'MANIFEST.json',dict(format='fpatan-gzip-v2',status='FROZEN_DISCOVERY_UNOPENED',rows=12,
            source_pins={n:guard.digest(job/n) for n in ('capture.c','protocol.py','compressed_guard.py')},
            expected_signature='00050654',expected_microcode='0x1',files={'inputs.txt.gz':guard.digest(job/'inputs.txt.gz')}))
        guard.save(job/'HISTORY.json',dict(status='NO_PRIOR_FPATAN_FOUND',hardware_executed=False))
        return job
    read=Path.read_text
    def read_cpu(path,*args,**kwargs):return 'microcode : 0x1\n' if str(path)=='/proc/cpuinfo' else read(path,*args,**kwargs)
    with patch.object(guard.os,'sched_setaffinity',create=True),patch.object(guard.os,'sched_getaffinity',return_value={0},create=True),patch.object(Path,'read_text',read_cpu):
        first=make_job('success',123);guard.run(base,first)
        complete=json.loads((first/'COMPLETE.json').read_text())
        raw=gzip.decompress((first/'hardware.txt.gz').read_bytes())
        assert hashlib.sha256(raw).hexdigest()==complete['hardware_sha256']
        assert len(raw.splitlines())==12
        try:guard.run(base,first)
        except RuntimeError:pass
        else:raise AssertionError('Completed job replay accepted')
        second=make_job('failed',456)
        with patch.dict(guard.os.environ,{'FPATAN_TEST_FAIL':'1'}):
            try:guard.run(base,second)
            except RuntimeError:pass
            else:raise AssertionError('Failed child committed')
        assert (second/'STARTED.json').exists() and not (second/'COMPLETE.json').exists()
        assert len(gzip.decompress((second/'hardware.txt.gz').read_bytes()).splitlines())==12
        try:guard.run(base,second)
        except RuntimeError:pass
        else:raise AssertionError('Failed reserved job replay accepted')
    db=sqlite3.connect(base/'ledger.sqlite')
    assert db.execute('SELECT job,state FROM batch_reservations ORDER BY job').fetchall()==[('failed','RESERVED'),('success','OBSERVED')]
    db.close();print('PASS gzip/hash/commit/failure/no-retry synthetic pipeline; NO HARDWARE')
    print('Synthetic artifacts preserved at',base)


if __name__=='__main__':main()
