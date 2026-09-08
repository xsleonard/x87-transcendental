"""Global index hypotheses for a fresh midpoint discriminator, not selectors.

Exact nearest ties lower/upper/even/odd compete with explicit reciprocal-
multiply quotient construction. These are complete fixed arithmetic rules;
none recognizes an observed failing operand, ratio or table cell.
"""
from model import F, cut

HYPOTHESES = ('lower', 'upper', 'even', 'odd', 'reciprocal-chop67',
              'reciprocal-rn67', 'reciprocal-rn64')


def index(y, x, rule='lower'):
    assert 0 < y <= x
    ratio = y / x
    tie = rule
    if rule.startswith('reciprocal-'):
        form = rule.split('-', 1)[1]
        ratio = cut(y * cut(1 / x, form), 'chop67')
        tie = 'upper'
    scaled = ratio * 32
    q, rem = divmod(scaled.numerator, scaled.denominator)
    if 2 * rem < scaled.denominator:
        return q
    if 2 * rem > scaled.denominator:
        return q + 1
    if tie == 'lower':
        return q
    if tie == 'upper':
        return q + 1
    if tie == 'even':
        return q + (q & 1)
    if tie == 'odd':
        return q + int(not q & 1)
    raise ValueError(rule)
