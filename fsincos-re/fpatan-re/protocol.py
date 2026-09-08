"""Public FPATAN protocol validation; contains no prediction algorithm."""
import hashlib
import re

MODES = ('rn','rd','ru','rz')


def case_key(rc,pc,ys,ym,xs,xm):
    return f'fpatan-v1-masked-clear-depth2:{rc}:{pc}:{ys:04x}:{ym:016x}:{xs:04x}:{xm:016x}'


def make_line(rc,pc,ys,ym,xs,xm):
    key=case_key(rc,pc,ys,ym,xs,xm)
    ident=hashlib.sha256(key.encode()).hexdigest()[:40]
    return f'{ident} {rc} {pc} {ys:04x} {ym:016x} {xs:04x} {xm:016x}'


def parse_line(line):
    t=line.split()
    if len(t)!=7 or t[1] not in MODES or t[2] not in ('24','53','64'):
        raise ValueError('bad FPATAN protocol/control')
    if not all(re.fullmatch('[0-9a-f]{'+str(n)+'}',v) for n,v in zip((4,16,4,16),t[3:])):
        raise ValueError('bad raw80 encodings')
    fields=(t[1],int(t[2]),*(int(s,16) for s in t[3:]))
    if make_line(*fields)!=line.strip(): raise ValueError('noncanonical line/case identity')
    return case_key(*fields)


def validate_inputs(text):
    lines=text.splitlines();keys=[parse_line(s) for s in lines]
    if not lines or len(keys)!=len(set(keys)): raise ValueError('empty/repeated tuple')
    return lines,keys


def validate_output(line,expected):
    t=line.split();p=expected.split()
    if len(t)!=12 or t[:7]!=p: raise ValueError('input/result mapping mismatch')
    if not all(re.fullmatch('[0-9a-f]{'+str(n)+'}',v) for n,v in zip((4,4,4,4,16),t[7:])):
        raise ValueError('malformed hardware result')
    cw,before,after,se,sig=(int(x,16) for x in t[7:])
    want=0x7f|{24:0,53:0x200,64:0x300}[int(p[2])]|(MODES.index(p[1])<<10)
    if cw!=want or ((before>>11)&7)!=6 or ((after>>11)&7)!=7:
        raise ValueError('control word or stack-pop mismatch')
    return dict(se=se,sig=sig,sw=after,before=before,C1=(after>>9)&1)


def selftest():
    good=make_line('rn',64,0x3fff,1<<63,0x3fff,1<<63)
    validate_inputs(good+'\n')
    for bad in (good+'\n'+good,good.replace(' rn ',' xx '),good.replace(' 64 ',' 25 ')):
        try: validate_inputs(bad)
        except ValueError: pass
        else: raise AssertionError('bad request accepted')
    out=good+' 037f 3000 3820 3ffe c90fdaa22168c235'
    validate_output(out,good)
    for bad in (out.replace('037f','027f'),out.replace('3000','3800'),out.replace('3820','3020'),out+' 0'):
        try: validate_output(bad,good)
        except ValueError: pass
        else: raise AssertionError('bad result accepted')
    print('PASS protocol validation; no hardware executed')


if __name__=='__main__': selftest()
