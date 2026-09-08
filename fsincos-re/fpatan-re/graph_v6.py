"""Unpromoted source-guided split-polynomial FPATAN candidate (D0021).

Goldmont supplies independent operation incidence, not Skylake widths or
low ROM bits. Reuse the existing range/quadrant hypothesis, but replace the
Horner kernel with two interleaved chains and per-opcode-class rounding.
"""
from d0010_causal_intervals import restore
from graph_v5 import prevalue as baseline
from model import ROM, cut


def kernel(z, table=False, trace=None):
    mul = lambda a, b: cut(a * b, 'chop67')
    add = lambda a, b: cut(a + b, 'rn64')
    wide = lambda a, b: cut(a + b, 'chop67')
    u = cut(z * cut(z, 'chop64'), 'rn64')
    v = mul(u, u)
    if table:
        even = wide(ROM[114], mul(v, ROM[116]))
        odd = add(ROM[115], mul(v, ROM[117]))
    else:
        odd = wide(ROM[119], mul(v, add(ROM[121], mul(v, ROM[123]))))
        even = wide(ROM[118], mul(v, add(ROM[120], mul(v, ROM[122]))))
    h = add(mul(u, odd), even)
    cube = mul(z, u)
    tail = mul(cube, h)
    if trace is not None:
        trace.update(square=u, fourth=v, odd=odd, even=even, horner=h, cube=cube, tail=tail)
    return z + tail


def prevalue(ys, ym, xs, xm, trace=None):
    t = {}
    previous = baseline(ys, ym, xs, xm, trace=t)
    if t['kind'] == 'tiny':
        result = previous
    else:
        k = kernel(t['z'], t['kind'] == 'table', t)
        t['angle'] = cut(k, 'chop67') + ROM[124+t['n']] if t['n'] else k
        t['intermediate'] = cut(t['angle'], 'chop67') if t['swap'] or xs & 32768 else t['angle']
        result = restore(k, t, (ys, ym, xs, xm))
    t['result'] = result
    if trace is not None:
        trace.update(t)
    return result
