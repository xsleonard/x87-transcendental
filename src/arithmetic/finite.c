#include "internal/finite.h"
#include "internal/numeric.h"
#include <stdlib.h>

/* Exact dyadic arithmetic and rounding primitives. */
enum { WORDS = 5, WINDOW_TOP = 318 };
typedef struct {
    uint64_t word[WORDS];
} magnitude;
typedef struct {
    magnitude integer;
    int scale;
    unsigned negative, tail;
} sum_work;

/* Bounds are part of the arithmetic contract, including in release builds. */
static void require(int condition)
{
    if (!condition)
        abort();
}

static int width(magnitude a)
{
    for (int i = WORDS - 1; i >= 0; --i)
        if (a.word[i])
            return 64 * i + 64 - __builtin_clzll(a.word[i]);
    return 0;
}
static magnitude mag(fv a)
{
    magnitude r = {{a.word[0], a.word[1], a.word[2], a.word[3], 0}};
    return r;
}
static int compare(magnitude a, magnitude b)
{
    for (int i = WORDS - 1; i >= 0; --i)
        if (a.word[i] != b.word[i])
            return a.word[i] > b.word[i] ? 1 : -1;
    return 0;
}
static unsigned bit(magnitude a, int n)
{
    return n >= 0 && n < 64 * WORDS ? (unsigned)((a.word[n / 64] >> (n % 64)) & 1) : 0;
}
static unsigned below(magnitude a, int n)
{
    if (n <= 0)
        return 0;
    if (n >= 64 * WORDS)
        return width(a) != 0;
    for (int i = 0; i < n / 64; ++i)
        if (a.word[i])
            return 1;
    return n % 64 && (a.word[n / 64] & ((UINT64_C(1) << (n % 64)) - 1));
}
static magnitude right(magnitude a, int n)
{
    magnitude r = {{0}};
    require(n >= 0);
    if (n >= 64 * WORDS)
        return r;
    int whole = n / 64, part = n % 64;
    for (int i = 0; i + whole < WORDS; ++i) {
        r.word[i] = a.word[i + whole] >> part;
        if (part && i + whole + 1 < WORDS)
            r.word[i] |= a.word[i + whole + 1] << (64 - part);
    }
    return r;
}
static magnitude left(magnitude a, int n)
{
    magnitude r = {{0}};
    require(n >= 0 && (!width(a) || width(a) + n <= 64 * WORDS));
    if (n >= 64 * WORDS)
        return r;
    int whole = n / 64, part = n % 64;
    for (int i = whole; i < WORDS; ++i) {
        r.word[i] = a.word[i - whole] << part;
        if (part && i > whole)
            r.word[i] |= a.word[i - whole - 1] >> (64 - part);
    }
    return r;
}
static magnitude add(magnitude a, magnitude b)
{
    unsigned carry = 0;
    for (int i = 0; i < WORDS; ++i) {
        u128 s = (u128)a.word[i] + b.word[i] + carry;
        a.word[i] = (uint64_t)s;
        carry = (unsigned)(s >> 64);
    }
    require(!carry);
    return a;
}
static magnitude subtract(magnitude a, magnitude b)
{
    require(compare(a, b) >= 0);
    unsigned borrow = 0;
    for (int i = 0; i < WORDS; ++i) {
        u128 sub = (u128)b.word[i] + borrow;
        borrow = (u128)a.word[i] < sub;
        a.word[i] -= (uint64_t)sub;
    }
    require(!borrow);
    return a;
}
static fv value(magnitude a, int exponent, unsigned negative)
{
    fv r = {{0}, 0, 0};
    if (!width(a))
        return r;
    int zeros = 0;
    while (!a.word[zeros / 64])
        zeros += 64;
    zeros += __builtin_ctzll(a.word[zeros / 64]);
    a = right(a, zeros);
    require(!a.word[4]);
    for (int i = 0; i < 4; ++i)
        r.word[i] = a.word[i];
    r.exponent = exponent + zeros;
    r.negative = !!negative;
    return r;
}
fv x87t_internal_fuint(uint64_t n)
{
    magnitude a = {{n, 0, 0, 0, 0}};
    return value(a, 0, 0);
}
fv x87t_internal_fhex(const char *s, int exponent, unsigned negative)
{
    magnitude a = {{0}};
    for (; *s; ++s) {
        unsigned d = *s >= '0' && *s <= '9' ? (unsigned)(*s - '0') :
                     *s >= 'a' && *s <= 'f' ? (unsigned)(*s - 'a' + 10) :
                     *s >= 'A' && *s <= 'F' ? (unsigned)(*s - 'A' + 10) : 16;
        require(d < 16 && width(a) <= 252);
        a = left(a, 4);
        a.word[0] |= d;
    }
    return value(a, exponent, negative);
}
/* All scaling here is exact; exponent fields are never host FP exponents. */
fv x87t_internal_fscale(fv a, int scale)
{
    if (width(mag(a)))
        a.exponent += scale;
    return a;
}
fv x87t_internal_fneg(fv a)
{
    if (width(mag(a)))
        a.negative ^= 1;
    return a;
}
fv x87t_internal_fabs(fv a)
{
    a.negative = 0;
    return a;
}
int x87t_internal_fsign(fv a)
{
    return width(mag(a)) ? (a.negative ? -1 : 1) : 0;
}
int x87t_internal_fexp(fv a)
{
    int w = width(mag(a));
    /* Preserve the original rational helper's zero convention. */
    return w ? a.exponent + w - 1 : -1;
}
fv x87t_internal_fdecode(raw80 a)
{
    fv r = x87t_internal_fuint(a.sig);
    r = x87t_internal_fscale(r, ((a.se & 0x7fff) ? (a.se & 0x7fff) : 1) - 16383 - 63);
    return a.se & 0x8000 ? x87t_internal_fneg(r) : r;
}
static int abs_compare(fv a, fv b)
{
    int wa = width(mag(a)), wb = width(mag(b));
    if (!wa || !wb)
        return (wa != 0) - (wb != 0);
    int ea = x87t_internal_fexp(a), eb = x87t_internal_fexp(b);
    if (ea != eb)
        return ea > eb ? 1 : -1;
    int base = a.exponent < b.exponent ? a.exponent : b.exponent;
    return compare(left(mag(a), a.exponent - base), left(mag(b), b.exponent - base));
}
int x87t_internal_fcmp(fv a, fv b)
{
    int sa = x87t_internal_fsign(a), sb = x87t_internal_fsign(b);
    if (sa != sb)
        return sa > sb ? 1 : -1;
    return sa < 0 ? -abs_compare(a, b) : abs_compare(a, b);
}
fv x87t_internal_fmul(fv a, fv b)
{
    require(width(mag(a)) <= 128 && width(mag(b)) <= 128);
    u128 aa = ((u128)a.word[1] << 64) | a.word[0];
    u128 bb = ((u128)b.word[1] << 64) | b.word[0];
    u256 p = x87t_internal_u128_mul_full(aa, bb);
    magnitude r = {{(uint64_t)p.lo, (uint64_t)(p.lo >> 64),
                    (uint64_t)p.hi, (uint64_t)(p.hi >> 64), 0}};
    return value(r, a.exponent + b.exponent, a.negative ^ b.negative);
}
static magnitude align(fv a, int scale, unsigned *tail)
{
    int shift = a.exponent - scale;
    *tail = shift < 0 && below(mag(a), -shift);
    return shift < 0 ? right(mag(a), -shift) : left(mag(a), shift);
}
static sum_work sum(fv a, fv b)
{
    /* At least the operand with the larger leading exponent is exact in the
     * window. A discarded tail belongs only to the smaller operand. For a
     * subtraction, borrow one unit and retain the complementary positive
     * tail: this is essential for directed rounding of pi minus tiny angles. */
    if (abs_compare(a, b) < 0) {
        fv t = a;
        a = b;
        b = t;
    }
    sum_work r = {{{0}}, 0, 0, 0};
    if (!x87t_internal_fsign(a))
        return r;
    r.scale = x87t_internal_fexp(a) - WINDOW_TOP;
    r.negative = a.negative;
    unsigned at, bt;
    magnitude am = align(a, r.scale, &at), bm = align(b, r.scale, &bt);
    require(!at);
    r.tail = bt;
    if (a.negative == b.negative) {
        r.integer = add(am, bm);
    } else {
        r.integer = subtract(am, bm);
        if (bt) {
            magnitude one = {{1, 0, 0, 0, 0}};
            r.integer = subtract(r.integer, one);
        }
    }
    require(!r.tail || width(r.integer));
    if (!width(r.integer))
        r.negative = 0;
    return r;
}
static int increment(unsigned odd, unsigned guard, unsigned rest, unsigned negative, enum mode rc)
{
    if (!guard && !rest)
        return 0;
    if (rc == RD)
        return negative;
    if (rc == RU)
        return !negative;
    return rc == RN && guard && (rest || odd);
}
static fv at_step(sum_work a, int scale, enum mode rc, int *c1)
{
    int shift = scale - a.scale;
    if (shift <= 0) {
        require(!a.tail);
        *c1 = 0;
        return value(a.integer, a.scale, a.negative);
    }
    magnitude q = right(a.integer, shift);
    unsigned guard = bit(a.integer, shift - 1);
    unsigned rest = below(a.integer, shift - 1) || a.tail;
    *c1 = increment(bit(q, 0), guard, rest, a.negative, rc);
    if (*c1) {
        magnitude one = {{1, 0, 0, 0, 0}};
        q = add(q, one);
    }
    return value(q, scale, a.negative);
}
fv x87t_internal_fadd(fv a, fv b, int bits, enum mode rc)
{
    require(bits >= 1 && bits <= 128);
    sum_work w = sum(a, b);
    if (!width(w.integer))
        return x87t_internal_fuint(0);
    int ignored;
    return at_step(w, w.scale + width(w.integer) - bits, rc, &ignored);
}
fv x87t_internal_fround(fv a, int bits, enum mode rc)
{
    return x87t_internal_fadd(a, x87t_internal_fuint(0), bits, rc);
}
int x87t_internal_fratio_exp(fv a, fv b)
{
    require(x87t_internal_fsign(a) && x87t_internal_fsign(b));
    int e = x87t_internal_fexp(a) - x87t_internal_fexp(b);
    if (abs_compare(a, x87t_internal_fscale(b, e)) < 0)
        --e;
    return e;
}
fv x87t_internal_fdiv(fv a, fv b, int bits, enum mode rc)
{
    require(bits >= 1 && bits <= 128 && x87t_internal_fsign(b));
    require(width(mag(a)) <= 128 && width(mag(b)) <= 128);
    if (!x87t_internal_fsign(a))
        return a;
    int e = x87t_internal_fratio_exp(a, b);
    int shift = a.exponent - b.exponent - e;
    magnitude n = mag(a), d = mag(b), q = {{1, 0, 0, 0, 0}};
    if (shift >= 0)
        n = left(n, shift);
    else
        d = left(d, -shift);
    /* n/d is in [1,2). Long division retains the exact remainder; it never
     * constructs a large power-of-two denominator or rounds a reciprocal. */
    magnitude rem = subtract(n, d);
    for (int i = 1; i < bits; ++i) {
        rem = left(rem, 1);
        q = left(q, 1);
        if (compare(rem, d) >= 0) {
            rem = subtract(rem, d);
            q.word[0] |= 1;
        }
    }
    int cmp = compare(left(rem, 1), d);
    unsigned negative = a.negative ^ b.negative;
    /* Translate the exact remainder into guard/rest: a half sets only guard;
     * a smaller nonzero remainder sets only rest; a larger one sets both. */
    if (increment(bit(q, 0), cmp >= 0, cmp != 0 && width(rem), negative, rc)) {
        magnitude one = {{1, 0, 0, 0, 0}};
        q = add(q, one);
    }
    return value(q, e - bits + 1, negative);
}
uint64_t x87t_internal_ffloor(fv a)
{
    require(!a.negative && x87t_internal_fexp(a) < 64);
    magnitude q = a.exponent < 0 ? right(mag(a), -a.exponent) : left(mag(a), a.exponent);
    return q.word[0];
}
static raw80 encode(sum_work w, enum mode rc, int *c1)
{
    raw80 out = {0, 0};
    int e = width(w.integer) ? w.scale + width(w.integer) - 1 : -16382;
    if (e < -16382)
        e = -16382;
    /* A zero work item has an arbitrary scale; no quantization is needed. */
    if (!width(w.integer)) {
        *c1 = 0;
        return out;
    }
    fv q = at_step(w, e - 63, rc, c1);
    if (x87t_internal_fsign(q) && x87t_internal_fexp(q) > 16383) {
        int inf = rc == RN || (rc == RD && w.negative) || (rc == RU && !w.negative);
        out.se = (uint16_t)((w.negative << 15) | (inf ? 0x7fff : 0x7ffe));
        out.sig = inf ? (UINT64_C(1) << 63) : UINT64_MAX;
        *c1 = inf;
        return out;
    }
    if (x87t_internal_fsign(q)) {
        e = x87t_internal_fexp(q);
        if (e < -16382)
            e = -16382;
        int shift = q.exponent + 63 - e;
        require(shift >= 0 && width(mag(q)) + shift <= 64);
        out.sig = left(mag(q), shift).word[0];
    }
    out.se = (uint16_t)((w.negative << 15) |
                       (out.sig < (UINT64_C(1) << 63) ? 0 : e + 16383));
    return out;
}
raw80 x87t_internal_fencode(fv a, enum mode rc, int *c1)
{
    return encode(sum(a, x87t_internal_fuint(0)), rc, c1);
}
raw80 x87t_internal_fencode_sum(fv a, fv b, enum mode rc, unsigned masks, int *c1, int *tiny)
{
    sum_work w = sum(a, b);
    *tiny = width(w.integer) && w.scale + width(w.integer) - 1 < -16382;
    if (*tiny && !(masks & X87T_UE))
        w.scale += 24576;
    return encode(w, rc, c1);
}
