"""Unpromoted V7: V6 kernel, nearest lower-cell ties, index-driven dispatch."""
from d0010_causal_intervals import restore
from d0023_index_hypotheses import index
from graph_v6 import kernel
from model import F, cut, pow2, value


def prevalue(ys, ym, xs, xm, trace=None, index_rule='lower'):
    y, x = abs(value(ys, ym)), abs(value(xs, xm))
    if not y or not x:
        raise ValueError('finite nonzero graph only')
    swap = y > x
    if swap:
        y, x = x, y
    ratio = y / x
    t = dict(swap=swap, ratio=ratio, n=0)
    if ratio < pow2(-40):
        z = cut(ratio, 'chop67')
        t.update(kind='tiny', z=z)
        k = z
    else:
        selected = index(y, x, index_rule)
        t['index_before_dispatch'] = selected
        if selected < 2:
            t['kind'] = 'direct'
            z = cut(ratio, 'chop67')
        else:
            assert 2 <= selected <= 32
            t.update(kind='table', n=selected)
            c = F(selected, 32)
            numerator = cut(y - c * x, 'chop67')
            denominator = cut(x + c * y, 'chop67')
            z = cut(numerator / denominator, 'chop67')
        t['z'] = z
        k = kernel(z, bool(t['n']), t)
    result = restore(k, t, (ys, ym, xs, xm))
    t['result'] = result
    if trace is not None:
        trace.update(t)
    return result
