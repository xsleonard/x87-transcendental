"""Analysis-only multiplier input formats, not fitted operand selectors.

The same role-specific reads apply to every direct/table polynomial. A
target-exact schedule still needs complete-corpus and fresh validation.
Neither the fixed C candidate nor any saved prediction is modified.
"""
import dataclasses
import itertools
import json
from pathlib import Path

from graph_v3 import prevalue
from graph_v4 import PROGRAM
from model import F, ROM, cut, encode, exponent, pow2, value
from prepare import save

BASE = Path(__file__).resolve().parents[1] / 'tmp/fpatan-re'


@dataclasses.dataclass(frozen=True)
class Ports:
    square_left: str = 'exact'
    square_right: str = 'exact'
    horner_square: str = 'exact'
    horner_state: str = 'exact'
    tail_square: str = 'exact'
    tail_horner: str = 'exact'
    tail_product: str = 'exact'
    tail_z: str = 'exact'


def kernel(z, p=Ports()):
    square = cut(cut(z, p.square_left) * cut(z, p.square_right), 'chop67')
    h = ROM[123]
    for a in (ROM[i] for i in range(122, 117, -1)):
        h = cut(a + cut(cut(square, p.horner_square) *
                        cut(h, p.horner_state), 'chop67'), 'rn64')
    product = cut(cut(square, p.tail_square) * cut(h, p.tail_horner), 'chop67')
    tail = cut(cut(product, p.tail_product) * cut(z, p.tail_z), 'chop67')
    return z + tail


def restore(k, t, ys, xs):
    angle = cut(k, 'chop67') + ROM[124+t['n']] if t['n'] else k
    intermediate = cut(angle, 'chop67') if t['swap'] or xs & 32768 else angle
    if t['swap']:
        result = ROM[20] + (intermediate if xs & 32768 else -intermediate)
    elif xs & 32768:
        result = ROM[19] - intermediate
    else:
        result = intermediate
    return -result if ys & 32768 else result


def prepare_targets():
    data = json.loads((BASE / 'd0008-frontier.json').read_text())
    out = []
    for pair in data['pairs']:
        raw = pair['raw']; trace = {}
        baseline = prevalue(*raw, PROGRAM, trace)
        k = kernel(trace['z'])
        assert restore(k, trace, raw[0], raw[2]) == baseline
        units = k / pow2(exponent(k) - 66)
        fraction = units - units.numerator // units.denominator
        out.append((raw, pair['rows'], trace, str(fraction)))
    return out


def score(p, data):
    om = cm = 0; pairs = []
    for raw, rows, t, fraction in data:
        before = restore(kernel(t['z'], p), t, raw[0], raw[2])
        a = b = 0
        for row in rows:
            se, sig = encode(before, row['rc'])
            c1 = int(abs(value(se, sig)) > abs(before))
            a += (se, sig) != (row['se'], row['sig'])
            b += c1 != row['C1']
        pairs.append(dict(output_misses=a, C1_misses=b))
        om += a; cm += b
    return dict(ports=dataclasses.asdict(p), output_misses=om, C1_misses=cm, pairs=pairs)


def main():
    data = prepare_targets(); results = []
    # Both inputs to the square may be formatted, but their exchange is
    # arithmetically identical, so enumerate unordered square-read pairs.
    reads = ('exact', 'rn64', 'chop64')
    square_pairs = tuple(itertools.combinations_with_replacement(reads, 2))
    for square, rest in itertools.product(square_pairs, itertools.product(reads, repeat=6)):
        results.append(score(Ports(*square, *rest), data))
    results.sort(key=lambda r: r['output_misses'] + r['C1_misses'])
    survivors = [r for r in results if not (r['output_misses'] or r['C1_misses'])]
    print('programs', len(results), 'target-exact', len(survivors), flush=True)
    for r in results[:12]: print(r, flush=True)
    save(BASE / 'd0008-operand-format-audit.json', dict(
        status='TARGET_SCREEN_ONLY_NOT_VALIDATED', hardware_executed=False,
        baseline=score(Ports(), data), results=results, survivors=survivors,
        frontier=[dict(raw=raw, kernel_fraction67=f) for raw, rows, t, f in data]))


if __name__ == '__main__':
    main()
