#!/usr/bin/env python3
"""Construct a frozen, finite remaining-case plan without reading new labels.

Public ambiguity, possible generator history, and private occurrences are
conservative holds, not passes. Private details stay in memory locally; only
aggregate counts are published. The selected operand/mask stream contains
public corpus inputs only and is not a private-ledger export.
"""
import argparse
import collections
import csv
import gzip
import json
import re
import sqlite3
import struct
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from h1725_full_campaign import BASE, ROOT, HOSTS, CORPUS, save, bit, suite
from h1721_policy2_challenge import possible_old_generator


def private_signatures():
    """Overapproximate all previously audited representations by significand.

    Any 8-byte window covers every supported packed/padded 80-bit struct;
    UTF8, both UTF16 views, PDF text, hexadecimal and exact decimal values
    are checked. File names, content, hashes and memberships never leave
    this function. No private source is evaluated as an implementation.
    """
    result=set();counts=collections.Counter()
    for path in (ROOT/'supplemental').rglob('*'):
        if not path.is_file():continue
        raw=path.read_bytes();counts['files']+=1;counts['bytes']+=len(raw)
        for pos in range(max(0,len(raw)-7)):
            word=raw[pos:pos+8]
            result.add(int.from_bytes(word,'little'));result.add(int.from_bytes(word,'big'))
        views=[]
        if raw.startswith(b'%PDF'):
            p=subprocess.run(['pdftotext','-layout',str(path),'-'],capture_output=True)
            if p.returncode or p.stderr:raise RuntimeError('Private extraction incomplete; no capture clearance')
            views.append(p.stdout.decode('utf8'));counts['pdf_texts']+=1
        else:
            views.append(raw.decode('latin1'))
            for encoding in ('utf-16-le','utf-16-be'):
                try:views.append(raw.decode(encoding))
                except UnicodeError:pass
        for text in views:
            for m in re.finditer(r'[0-9a-fA-F]{16,}',text):
                word=m[0]
                for i in range(len(word)-15):result.add(int(word[i:i+16],16))
            for m in re.finditer(r'(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![\w.])',text):
                token=m[0]
                e=re.search(r'[eE]([-+]?\d+)$',token)
                mantissa=token[:e.start()] if e else token
                digits=mantissa.lstrip('+-').replace('.','').lstrip('0')
                if not digits:result.add(0);continue
                if e and len(e[1].lstrip('+-0'))>len(str(len(mantissa)+5001)):
                    # Even every mantissa character cannot offset such an
                    # exponent into raw80 range, including decimal zero padding.
                    counts['decimal_values_outside_raw80_range']+=1;continue
                exponent=int(e[1]) if e else 0
                places=len(mantissa.rsplit('.',1)[1]) if '.' in mantissa else 0
                trailing=len(digits)-len(digits.rstrip('0'));digits=digits.rstrip('0')
                exponent=exponent-places+trailing
                order=len(digits)+exponent
                if order>5000 or order < -5000:
                    counts['decimal_values_outside_raw80_range']+=1;continue
                # Every exact finite raw80 decimal has fewer than 20,000
                # significant digits after zero trimming (2^-16445 is the
                # smallest nonzero raw80 value). Longer coefficients cannot
                # equal one of the corpus's finite encodings exactly.
                if len(digits)>20000:
                    counts['decimal_values_not_exact_raw80']+=1;continue
                if hasattr(sys,'set_int_max_str_digits'):sys.set_int_max_str_digits(30000)
                token=digits+'e'+str(exponent)
                q=abs(Fraction(token));n,d=q.numerator,q.denominator
                if d&(d-1):continue
                if not n:result.add(0);continue
                n>>=(n&-n).bit_length()-1
                if n.bit_length()<=64:result.add(n<<(64-n.bit_length()))
                if q.denominator==1 and q.numerator<(1<<64):result.add(q.numerator)
    assert counts['files']>0
    return result,dict(counts)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',choices=HOSTS,required=True)
    a=p.parse_args();host=a.host;out=BASE/host
    log=(out/'public-history.log').read_text().splitlines()
    assert json.loads(log[-1])['status']=='PUBLIC_HISTORY_EXPORT_COMPLETE'
    dbpath=out/'possible-history.sqlite'
    assert not dbpath.exists()
    history=sqlite3.connect(dbpath);history.execute('PRAGMA journal_mode=OFF')
    history.execute('PRAGMA synchronous=OFF');history.execute('PRAGMA cache_size=-262144')
    history.execute('CREATE TABLE possible(op TEXT PRIMARY KEY) WITHOUT ROWID')
    batch=[];rows=0
    with gzip.open(out/'public-history-possible-inputs.txt.gz','rt') as f:
        for line in f:
            op=line.strip();assert re.fullmatch('[0-9a-f]{4} [0-9a-f]{16}',op)
            batch.append((op,));rows+=1
            if len(batch)==100000:
                history.executemany('INSERT OR IGNORE INTO possible VALUES(?)',batch);history.commit();batch=[]
                if rows%1000000==0:print(host,'public history occurrences indexed',rows,flush=True)
    if batch:history.executemany('INSERT OR IGNORE INTO possible VALUES(?)',batch)
    history.commit()
    # A sorted merge avoids hundreds of millions of random SQLite lookups.
    pub=iter(history.execute('SELECT op FROM possible ORDER BY op'));public=next(pub,(None,))[0]
    known={}
    prior=sqlite3.connect('file:'+str(out/'prior-ledger-0.sqlite')+'?mode=ro',uri=True)
    for case, in prior.execute('SELECT case_id FROM reservations'):
        insn,mode,pc,op=suite.decode_case(case)
        if pc==64:known[op]=known.get(op,0)|bit(insn,mode)
    prior.close()
    print(host,'auditing supplemental history locally',flush=True)
    private,private_counts=private_signatures()
    cfg=json.loads((out/'legacy-source-exclusions.json').read_text())
    source_masks={int(k):v for k,v in cfg['source_masks'].items()}
    aliases=json.loads((out/'alias-audit.json').read_text())
    assert aliases['status']=='PUBLIC_INPUT_ALIAS_AUDIT_COMPLETE'
    # An extra copy may have been used with an unmapped instruction/mode.
    # Until its provenance is resolved, hold its whole source group.
    alias_hashes={r['sha256'] for r in aliases['aliases']}
    for src in json.loads((ROOT/'corpus-suite/corpus-v1/sources.json').read_text()):
        hashes={src.get('sha256')}|{e.get('sha256') for e in src.get('evidence',[])}
        if hashes&alias_hashes:source_masks[src['index']]=4095
    manifest=suite.verify_dataset(ROOT/'corpus-suite/corpus-v1')
    assert manifest['corpus_id']==CORPUS
    def canonical_operands():
        previous=None
        with gzip.open(ROOT/'corpus-suite/corpus-v1/operands.tsv.gz','rt') as src:
            reader=csv.DictReader(src,delimiter='\t')
            assert reader.fieldnames==['se','sig','profiles','sources']
            for row in reader:
                op=row['se']+' '+row['sig']
                assert re.fullmatch('[0-9a-f]{4} [0-9a-f]{16}',op)
                assert previous is None or previous<op
                previous=op
                yield op,int(row['sources'],16)
    counts=collections.Counter();cache={}
    selected=out/'selected.bin'
    with selected.open('xb') as f:
        for ordinal,(op,sources) in enumerate(canonical_operands()):
            se,sig=map(lambda s:int(s,16),op.split())
            if sources not in cache:
                mask=0
                for idx,m in source_masks.items():
                    if sources&(1<<idx):mask|=m
                cache[sources]=mask
            old=cache[sources]|known.get(op,0);counts['prior_excluded_cases']+=old.bit_count()
            available=4095^old
            while public is not None and public<op:public=next(pub,(None,))[0]
            hold=public==op or sig in private
            # Earlier binary64 generator runs covered FSIN, at unknown seeds
            # too. Reserve that whole subset rather than guessing prefixes.
            if sig&2047==0:
                counts['binary64_domain_hold_cases']+=(available&15).bit_count();available&=4080
            ef=se&0x7fff
            if not (0<ef<0x7fff and sig>>63) or (ef==0x3fff and sig==1<<63):
                hold=True
            elif possible_old_generator(op):hold=True
            if hold:
                counts['ambiguous_or_generated_hold_cases']+=available.bit_count();available=0
            if available:
                f.write(struct.pack('<QHQH',ordinal,se,sig,available))
                counts['selected_operands']+=1;counts['selected_cases']+=available.bit_count()
            counts['operands']+=1
            if counts['operands']%1000000==0:print(host,dict(counts),flush=True)
    assert counts['operands']==42289770
    assert suite.digest(ROOT/'corpus-suite/corpus-v1/operands.tsv.gz')==manifest['files']['operands.tsv.gz']
    assert sum(counts[k] for k in ('prior_excluded_cases','binary64_domain_hold_cases','ambiguous_or_generated_hold_cases','selected_cases'))==507477240
    save(out/'SELECTION.json',dict(status='FROZEN_SELECTION_NEEDS_RUNNER_PREFLIGHT',
        corpus_id=CORPUS,counts=dict(counts),selected_sha256=suite.digest(selected),record_format='<QHQH ordinal,se,sig,12bit_mask',
        source_hash=suite.digest(Path(__file__)),private_audit_counts=private_counts,
        private_details_published=False,hardware_execution='none',
        public_history_sha256=suite.digest(out/'public-history-possible-inputs.txt.gz'),
        limits='Conservative visible-history audit. Held cases are not passed or fresh; unavailable records and unknown raw80 generator seeds remain explicit limitations.'))
    print(host,'SELECTION COMPLETE',dict(counts),flush=True)


if __name__=='__main__':main()
