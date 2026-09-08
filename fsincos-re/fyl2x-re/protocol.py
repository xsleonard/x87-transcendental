"""Public logarithm capture protocol. No model, warmups or implicit probes."""
import hashlib
import re

MODES = ('rn', 'rd', 'ru', 'rz')
OPS = ('fyl2x', 'fyl2xp1')


def case_key(op, rc, pc, ys, ym, xs, xm):
    return f'{op}-v1-masked-clear-depth2:{rc}:{pc}:{ys:04x}:{ym:016x}:{xs:04x}:{xm:016x}'


def make_line(op, rc, pc, ys, ym, xs, xm):
    ident = hashlib.sha256(case_key(op, rc, pc, ys, ym, xs, xm).encode()).hexdigest()[:40]
    return f'{ident} {op} {rc} {pc} {ys:04x} {ym:016x} {xs:04x} {xm:016x}'


def parse_line(line):
    t = line.split()
    if len(t) != 8 or t[1] not in OPS or t[2] not in MODES or t[3] not in ('24', '53', '64'):
        raise ValueError('invalid logarithm protocol/control')
    if not all(re.fullmatch('[0-9a-f]{'+str(n)+'}', v) for n,v in zip((4,16,4,16), t[4:])):
        raise ValueError('invalid raw80 encoding')
    fields = (t[1], t[2], int(t[3]), *(int(s,16) for s in t[4:]))
    if make_line(*fields) != line.strip():
        raise ValueError('noncanonical case identity')
    return case_key(*fields)


def validate_inputs(text):
    lines = text.splitlines()
    keys = [parse_line(line) for line in lines]
    if not lines or len(keys) != len(set(keys)):
        raise ValueError('empty/repeated capture tuple')
    return lines, keys


def validate_output(line, expected):
    t = line.split(); p = expected.split()
    if len(t) != 13 or t[:8] != p:
        raise ValueError('input/result identity mismatch')
    if not all(re.fullmatch('[0-9a-f]{'+str(n)+'}', v) for n,v in zip((4,4,4,4,16), t[8:])):
        raise ValueError('malformed hardware output')
    cw, before, after, se, sig = (int(s,16) for s in t[8:])
    want = 0x7f | {24:0,53:0x200,64:0x300}[int(p[3])] | (MODES.index(p[2]) << 10)
    if cw != want or ((before >> 11) & 7) != 6 or ((after >> 11) & 7) != 7:
        raise ValueError('control word or stack-pop mismatch')
    return dict(se=se, sig=sig, sw=after, before=before, C1=(after >> 9) & 1)
