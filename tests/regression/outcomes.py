"""Replay retained architectural state through the arithmetic outcome API.

Pending exceptions and empty/full stacks belong to the emulator and are tested
by the Bochs guest runner. This replay feeds only valid arithmetic prestates.
"""
from collections import Counter
import gzip
import json
from pathlib import Path
import subprocess
import sys

DATA=Path(__file__).resolve().parents[1]/'data/bochs-state-witnesses.json'
TRIG={'fsin','fcos','fsincos','fptan'}
PAIRED={'fsincos','fptan'}
BINARY={'fpatan','fyl2x','fyl2xp1'}


def u16(data,at):return int.from_bytes(data[at:at+2],'little')
def operand(data,index):
    at=32+index*16
    return f'{u16(data,at+8):04x} {int.from_bytes(data[at:at+8],"little"):016x}'


def prepare(cases):
    rows=[];inputs=[];counts=Counter()
    for case in cases:
        before=bytes.fromhex(case['before']);cw=u16(before,0);sw=u16(before,2);top=(sw>>11)&7
        if sw&~cw&63:
            counts['pending_emulator_cases']+=1;continue
        if not before[4]&(1<<top) or (case['op'] in BINARY and not before[4]&(1<<((top+1)&7))):
            counts['stack_emulator_cases']+=1;continue
        if case['op'] in PAIRED and before[4]&(1<<((top-1)&7)):
            counts['stack_emulator_cases']+=1;continue
        pc=(24,0,53,64)[(cw>>8)&3]
        inputs.append(f"{len(rows)} {case['op']} {('rn','rd','ru','rz')[(cw>>10)&3]} {pc} {cw&63:02x} {operand(before,0)} {operand(before,1)}")
        rows.append(case)
    return rows,inputs,counts


def check(rows,results,counts):
    assert len(results)==len(rows)
    for index,(case,line) in enumerate(zip(rows,results)):
        f=line.split();assert len(f)==14 and f[0]==str(index) and f[1]=='0',(case['id'],line)
        before=bytes.fromhex(case['before']);after=bytes.fromhex(case['after'])
        cw=u16(before,0);sw=u16(after,2);flags=int(f[10],16)
        assert int(f[11],16)==63
        assert (u16(before,2)|flags)&63==sw&63,(case['id'],'flags',line)
        first=sw&~cw&63;first=first&-first
        assert int(f[13],16)==first,(case['id'],'first exception',line)
        early=first in (1,2,4)
        range_return=case['op'] in TRIG and bool(sw&0x400)
        completion=2 if early else 3 if first else 1 if range_return else 0
        assert int(f[2])==completion,(case['id'],'completion',line)
        required=0x400 if range_return else 0x600 if case['op'] in TRIG else 0x200
        assert int(f[9],16)&required==required,(case['id'],'missing metadata',line)
        assert (int(f[8],16)^sw)&required==0,(case['id'],'condition codes',line)
        if early or range_return:
            assert f[3]=='0' and f[12]=='0',(case['id'],'suppressed write',line)
        else:
            paired=case['op'] in PAIRED
            assert ' '.join(f[4:6])==operand(after,int(paired)),(case['id'],'primary',line)
            if paired:assert ' '.join(f[6:8])==operand(after,0),(case['id'],'pushed',line)
            destination=2 if paired else 3 if case['op'] in BINARY else 1
            assert int(f[12])==destination and int(f[3])==(3 if paired else 1)
        counts[case['op']]+=1
    return counts


def main():
    data=Path(sys.argv[2]) if len(sys.argv)>2 else DATA
    raw=gzip.decompress(data.read_bytes()) if data.suffix=='.gz' else data.read_bytes()
    rows,inputs,counts=prepare(json.loads(raw)['cases'])
    process=subprocess.run([sys.argv[1]],input='\n'.join(inputs)+'\n',text=True,capture_output=True,check=True)
    check(rows,process.stdout.splitlines(),counts)
    print(json.dumps(dict(status='PASS',counts=counts,native_hardware_executed=False)))


if __name__=='__main__':main()
