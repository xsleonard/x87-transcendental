"""Synthetic duplicate/reservation tests. Never execute hardware."""
import gzip
from pathlib import Path
import sqlite3
import tempfile
from protocol import make_line,parse_line
from compressed_guard import reserve,digest,schema


def main():
    base=Path(tempfile.mkdtemp(prefix='fpatan-ledger-test-'));context='synthetic'
    rows=[make_line('rn',64,0x3fff,(1<<63)+i,0x3fff,1<<63) for i in range(1,8)]
    db=sqlite3.connect(base/'ledger.sqlite');schema(db)
    db.execute('INSERT INTO reservations VALUES(?,?,?,?)',(context,parse_line(rows[0]),'legacy','OBSERVED'));db.commit();db.close()
    def job(name,lines):
        p=base/name;p.mkdir()
        with gzip.open(p/'inputs.txt.gz','wt') as f:f.write('\n'.join(lines)+'\n')
        return p
    def reject(p,count):
        try:reserve(base,p,context,digest(p/'inputs.txt.gz'),count)
        except (RuntimeError,ValueError,FileNotFoundError):return
        raise AssertionError('Unsafe reservation accepted')
    reject(job('duplicate-legacy',[rows[0]]),1)
    reject(job('duplicate-within-batch',[rows[1],rows[1]]),2)
    good=job('first',[rows[1],rows[2]])
    reserve(base,good,context,digest(good/'inputs.txt.gz'),2)
    reject(good,2);reject(job('duplicate-batch',[rows[2],rows[3]]),2)
    second=job('second',[rows[3]])
    reserve(base,second,context,digest(second/'inputs.txt.gz'),1)
    db=sqlite3.connect(base/'ledger.sqlite')
    try:db.execute('INSERT INTO reservations VALUES(?,?,?,?)',(context,parse_line(rows[4]),'old-guard','RESERVED'))
    except sqlite3.IntegrityError:db.rollback()
    else:raise AssertionError('Legacy guard bypass accepted')
    assert db.execute('SELECT count(*) FROM reservations').fetchone()[0]==1
    assert db.execute('SELECT sum(rows) FROM batch_reservations').fetchone()[0]==3
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
    print('PASS legacy/batch/restart/intrabatch duplicate checks and legacy-guard lockout; no hardware')
    print('Synthetic artifacts preserved at',base)


if __name__=='__main__':main()
