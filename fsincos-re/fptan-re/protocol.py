"""Public one-input, two-output FPTAN capture protocol; no predictions."""
import hashlib
import re

MODES = ('rn', 'rd', 'ru', 'rz')


def key(rc, pc, se, sig):
    return f'fptan-v1-masked-clear-depth1:{rc}:{pc}:{se:04x}:{sig:016x}'


def make_line(rc, pc, se, sig):
    ident = hashlib.sha256(key(rc, pc, se, sig).encode()).hexdigest()[:40]
    return f'{ident} {rc} {pc} {se:04x} {sig:016x}'


def parse(line):
    fields = line.split()
    if len(fields) != 5 or fields[1] not in MODES or fields[2] not in ('24', '53', '64'):
        raise ValueError('Bad FPTAN input fields/control')
    if not re.fullmatch('[0-9a-f]{4}', fields[3]) or not re.fullmatch('[0-9a-f]{16}', fields[4]):
        raise ValueError('Bad raw80 input')
    rc, pc, se, sig = fields[1], int(fields[2]), int(fields[3], 16), int(fields[4], 16)
    if make_line(rc, pc, se, sig) != line.strip():
        raise ValueError('Input identity mismatch')
    return key(rc, pc, se, sig)


def validate_output(line, expected):
    fields = line.split()
    request = expected.split()
    if len(fields) != 13 or fields[:5] != request:
        raise ValueError('Capture mapping/length mismatch')
    for token, size in zip(fields[5:], (4, 4, 4, 4, 4, 16, 4, 16), strict=True):
        if not re.fullmatch('[0-9a-f]{' + str(size) + '}', token):
            raise ValueError('Bad captured raw field')
    cw, before, after, end, se, sig, ps, pm = (int(v, 16) for v in fields[5:])
    wanted = 0x7f | {24: 0, 53: 0x200, 64: 0x300}[int(request[2])] | MODES.index(request[1]) << 10
    c2 = (after >> 10) & 1
    if cw != wanted or ((before >> 11) & 7) != 7 or ((after >> 11) & 7) != (7 if c2 else 6) or ((end >> 11) & 7) != 0:
        raise ValueError('CW/TOP/stack-balance mismatch')
    return dict(se=se, sig=sig, pushed_se=ps, pushed_sig=pm,
                C1=(after >> 9) & 1, C2=c2, before=before, after=after, end=end)
