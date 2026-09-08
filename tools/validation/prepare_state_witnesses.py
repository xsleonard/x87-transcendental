"""Select portable emulator witnesses from retained public hardware evidence.

Full-state captures retain all measured registers. Older numerical captures
are labeled separately: their results/flags are measured, while stack movement
and preservation are expectations from the instruction contract.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT/'research/fsincos-re'
sys.path.insert(0,str(ROOT/'tests/regression'))
from replay import cases as numerical_cases


def u16(data,at):return int.from_bytes(data[at:at+2],'little')
def raw_class(raw):
    se,sig=(int(v,16) if isinstance(v,str) else v for v in raw)
    e=se&32767
    return ('zero' if not e and not sig else 'denormal' if not e and sig<1<<63 else
            'pseudo' if not e else 'unsupported' if sig<1<<63 else
            'infinity' if e==32767 and sig==1<<63 else
            ('qnan' if sig&(1<<62) else 'snan') if e==32767 else 'normal')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'tests/data/bochs-state-witnesses.json')
    parser.add_argument('--full-h1656',action='store_true')
    args=parser.parse_args();output=args.output
    rows=[];sources=[]
    def record_source(path,raw):
        source=dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest())
        sources.append(source);return source['path']
    def full_state(f,prefix):
        data=bytearray(512)
        struct.pack_into('<HH',data,0,int(f[prefix+'_cw'],16),int(f[prefix+'_sw'],16))
        data[4]=int(f[prefix+'_ftw'],16);struct.pack_into('<I',data,24,0x1f80)
        for index in range(8):
            se,sig=(int(v,16) for v in f[prefix+'_r'+str(index)].split(':'))
            struct.pack_into('<QH',data,32+16*index,sig,se)
        return data.hex()
    seen=set()
    for name,prefix in [('transfer-tests/h1656/hardware-output/state-output.txt','h1656'),
                         ('tmp/ledger33/current/h1401_single_shot/raw-state-output.txt','h1401')]:
        path=RESEARCH/name;raw=path.read_bytes();origin=record_source(path,raw)
        for line in raw.decode().splitlines():
            f=dict(t.lower().split('=') for t in line.split())
            after='a' if f.get('a_valid','1')=='1' else 'f'
            sw=int(f[after+'_sw'],16);before=int(f['b_sw'],16)
            occupied=bool(int(f['b_ftw'],16)&(1<<((before>>11)&7)))
            key=(f['insn'],sw&63,int(f.get('fault_at',0)),bool(sw&0x400),bool(before&63),occupied)
            if prefix=='h1656' and key in seen and not args.full_h1656:continue
            seen.add(key)
            rows.append(dict(id=prefix+'-'+f['case'],op=f['insn'],before=full_state(f,'b'),
                after=full_state(f,after),cc_mask=0x400 if sw&0x400 else 0x600,
                fault_at=int(f.get('fault_at',0)),source=origin,source_id=f['case'],
                evidence='hardware full state'))
    def numerical(row,ident,origin):
        op,rc,pc,x,y,want,pushed,c1,c2,flags=row
        before=bytearray(512)
        cw=0x7f|{24:0,53:0x200,64:0x300}[pc]|(('rn','rd','ru','rz').index(rc)<<10)
        struct.pack_into('<HH',before,0,cw,0x3000);before[4]=0xc0
        struct.pack_into('<I',before,24,0x1f80)
        for index in range(8):struct.pack_into('<QH',before,32+16*index,0x987654321abcdef0+index,0x4001)
        for index,raw in enumerate((x,y)):
            if raw:struct.pack_into('<QH',before,32+16*index,int(raw[1],16),int(raw[0],16))
        after=bytearray(before)
        if want is not None:
            if op in ('fpatan','fyl2x','fyl2xp1'):
                for index in range(7):after[32+16*index:48+16*index]=before[48+16*index:64+16*index]
                after[144:160]=before[32:48]
                struct.pack_into('<QH',after,32,want[1],want[0]);after[4]=0x80;top=7
            elif op in ('fsincos','fptan'):
                for index in range(7,0,-1):after[32+16*index:48+16*index]=before[16+16*index:32+16*index]
                struct.pack_into('<QH',after,32,pushed[1],pushed[0])
                struct.pack_into('<QH',after,48,want[1],want[0]);after[4]=0xe0;top=5
            else:
                struct.pack_into('<QH',after,32,want[1],want[0]);top=6
        else:top=6
        struct.pack_into('<H',after,2,(top<<11)|flags|((c1 or 0)<<9)|((c2 or 0)<<10))
        return dict(id=ident,op=op,before=before.hex(),after=after.hex(),
                    cc_mask=0x400 if want is None else 0x600 if op in ('fsin','fcos','fsincos','fptan') else 0x200,
                    fault_at=0,source=origin,source_id=ident,
                    evidence='hardware results and flags; specified stack writeback and preservation')
    for op,name in [('fptan','fptan/verification-expansion-fptan-v1-xeon'),('f2xm1','f2xm1/f0001')]:
        path=RESEARCH/'tmp/verification-expansion'/name/'hardware.txt.gz'
        raw=gzip.decompress(path.read_bytes())
        receipt=json.loads(path.with_name('COMPLETE.json').read_text())
        assert hashlib.sha256(raw).hexdigest()==receipt['hardware_sha256']
        origin=record_source(path,raw);seen=set()
        for line in raw.decode().splitlines():
            f=line.split();sw=int(f[7],16);c2=(sw>>10)&1 if op=='fptan' else None
            key=(f[1],f[2],raw_class(f[3:5]),int(f[3],16)>>15,sw&0x63f)
            if key in seen:continue
            seen.add(key)
            want=tuple(int(v,16) for v in f[9:11]);push=tuple(int(v,16) for v in f[11:13]) if op=='fptan' else None
            row=(op,f[1],int(f[2]),f[3:5],[],None if c2 else want,push,(sw>>9)&1,c2,sw&63)
            rows.append(numerical(row,op+'-'+f[0],origin))
    for name in ('smoke-witnesses.json','log-witnesses.txt'):
        path=ROOT/'tests/data'/name
        record_source(path,path.read_bytes())
    bank,_=numerical_cases();seen=set()
    for index,row in enumerate(bank):
        op,rc,pc,x,y,want,push,c1,c2,flags=row
        if op not in ('fpatan','fyl2x','fyl2xp1'):continue
        key=(op,rc,pc,raw_class(x),raw_class(y),flags,c1)
        if key in seen:continue
        seen.add(key)
        rows.append(numerical(row,f'binary-{index}','tests/data/smoke-witnesses.json + log-witnesses.txt'))
    counts=Counter(c['op'] for c in rows)
    output.write_text(json.dumps(dict(description=__doc__,sources=sources,counts=counts,cases=rows),indent=2)+'\n')
    print('Selected',len(rows),'state witnesses:',dict(counts))


if __name__=='__main__':main()
