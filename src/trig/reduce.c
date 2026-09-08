/* Reduce finite normalized x when PI_BY_4 <= |x| < 2^63, using the
 * stored PI_BY_4 threshold. Write
 *     |x| = sig*2^(e-63),  -1 <= e <= 62,
 *     M = 0x3243f6a8885a308d3,  M66 = M*2^-65.
 * N is the nearest integer to |x|/M66. The signed remainder is
 *     t = x - sign(x)*N*M66,
 * where sign(x) is +1 or -1.
 *
 * Integer division and subtraction compute this remainder exactly for
 * the stored M66. Using a closer approximation to pi/2 would change it.
 * Round t to nearest/even at 64 significant bits for r, and keep the
 * difference in c, so r+c = t exactly. The H1627-H1629 analysis showed
 * that t is a multiple of 2^-65 with |t| < M66/2. The kernels that follow
 * use this bound on the remainder's size and spacing.
 */
/* Centered reduction by the fixed 66-bit pi/2 constant. */
#include "internal/numeric.h"

static const uint64_t SKY_M66_LO = UINT64_C(0x243f6a8885a308d3);
typedef struct {
    uint64_t l0, l1, l2;
} u192;

/*
 * form the centered quotient by literal exact
 * division by the 66-bit reduction constant.  The complete operation replay
 * selects this over the older reciprocal seed at rare large arguments.
 */
uint64_t x87t_internal_reduce_quotient(uint64_t sig, int32_t e)
{
    /* For -1 <= e <= 62, the shift e+2 is in [1,64] and the dividend
     * fits in 128 bits. M is odd, so 2*remainder cannot equal M. There is
     * no halfway case when choosing the nearest quotient. */
    u128 dividend = (u128)sig << (e + 2);
    u128 divisor = ((u128)3 << 64) | SKY_M66_LO;
    u128 quotient = dividend / divisor;
    u128 remainder = dividend % divisor;
    if ((remainder << 1) > divisor)
        quotient++;
    return (uint64_t)quotient;
}

/* N is the nonnegative quotient for |x|. The shorthand below assumes
 * positive x; for negative x the subtraction is x - (-N)*M66. The exact
 * remainder has magnitude <= floor(M/2)*2^-65, so its integer magnitude
 * at scale 2^-65 fits in 65 bits. */
/* r + c = x - N*M66 exactly; returns via out params */
void x87t_internal_reduce_remainder(const sf_t *x, uint64_t N, sf_t *r, sf_t *c)
{
    /* A = |x| * 2^65 = sig << (e+2)   (exact; e >= -1 here) */
    int k = (int)x->exp + 2; /* 1..64 */
    u192 A = {0, 0, 0};
    if (k == 64) {
        A.l1 = x->sig;
    } else {
        A.l0 = x->sig << k;
        A.l1 = x->sig >> (64 - k);
    }
    /* B = N * M66_INT = N*lo + (3N << 64) */
    u128 t = (u128)N * SKY_M66_LO;
    u128 u = (u128)N * 3;
    u192 B;
    B.l0 = (uint64_t)t;
    B.l1 = (uint64_t)(t >> 64);
    B.l2 = 0;
    u128 mid = (u128)B.l1 + (uint64_t)u;
    B.l1 = (uint64_t)mid;
    B.l2 = (uint64_t)(u >> 64) + (uint64_t)(mid >> 64);
    /* signed diff d = A - B (3-limb) */
    int dneg;
    u192 D;
    int a_ge_b = (A.l2 != B.l2) ? (A.l2 > B.l2) : (A.l1 != B.l1) ? (A.l1 > B.l1) : (A.l0 >= B.l0);
    const u192 *hi = a_ge_b ? &A : &B, *lo = a_ge_b ? &B : &A;
    dneg = !a_ge_b;
    uint64_t borrow = 0;
    D.l0 = hi->l0 - lo->l0;
    borrow = hi->l0 < lo->l0;
    D.l1 = hi->l1 - lo->l1 - borrow;
    borrow = (hi->l1 < lo->l1) || (hi->l1 == lo->l1 && borrow);
    D.l2 = hi->l2 - lo->l2 - borrow;
    dneg ^= x->sign; /* apply x's sign */
    /* |d| < 2^65 (r <= ~pi/4 * 2^65): l2 must be 0, l1 in {0,1} */
    /* This guard catches a violated precondition: N must be the nearest
     * quotient returned by reduce_quotient for this x. */
    if (D.l2 != 0 || D.l1 > 1) {
        *r = x87t_internal_sf_qnan();
        *c = x87t_internal_sf_qnan();
        return;
    }
    if (D.l1 == 0 && D.l0 == 0) {
        *r = x87t_internal_sf_zero(dneg);
        *c = x87t_internal_sf_zero(dneg);
        return;
    }
    /* Only |t| >= 1/2 needs splitting. If the low bit of the 65-bit
     * magnitude is set, t is halfway between two 64-bit values. Round r
     * to the even one and set c to the difference, 0 or +/-2^-65. Keeping
     * c preserves the exact remainder for table evaluation. */
    if (D.l1) { /* 65 significant bits: round */
        int g = (int)(D.l0 & 1);
        uint64_t kept = ((uint64_t)1 << 63) | (D.l0 >> 1);
        int64_t resid = g;     /* d - trunc(d)/1  in 2^-65 units */
        int32_t rexp = -1;     /* msb at 2^64 * 2^-65 = 2^-1 */
        if (g && (kept & 1)) { /* RN-even: round up */
            kept += 1;
            resid = -1;
            if (kept == 0) {
                kept = (uint64_t)1 << 63;
                rexp += 1;
            }
        }
        r->cls = SF_FIN;
        r->sign = (uint8_t)dneg;
        r->exp = rexp;
        r->sig = kept;
        if (resid == 0)
            *c = x87t_internal_sf_zero(dneg);
        else {
            /* residual: d - r = resid * 2^-65 in the magnitude frame */
            c->cls = SF_FIN;
            c->sign = (uint8_t)(((resid < 0) ? 1 : 0) ^ dneg);
            c->exp = -65;
            c->sig = (uint64_t)1 << 63;
        }
    } else { /* <= 64 bits: exact */
        uint64_t v = D.l0;
        int b = 63;
        while (!(v >> b))
            b--;
        r->cls = SF_FIN;
        r->sign = (uint8_t)dneg;
        r->exp = b - 65;
        r->sig = v << (63 - b);
        *c = x87t_internal_sf_zero(dneg);
    }
}

/* Rebuild the exact wide reduced argument |r+c| from (r, c).
 * By construction of the M66 reducer, c != 0 only when |r| >= 0.5 (the
 * 65th significand bit), and then c is exactly +-1 unit of 2^-65. */
/* The returned value includes the sign of r+c; the magnitude bars above
 * describe only sig. Save the sign before clearing it for a magnitude-only
 * calculation. Pass either the reducer's r,c pair or normalized r with c=0.
 * This helper relies on that relationship between r and c. */
wv_t x87t_internal_reduced_to_wide(const sf_t *r, const sf_t *c)
{
    wv_t w = {0};
    w.sign = r->sign;
    if (c->sig == 0) {
        w.sig = (u128)r->sig;
        w.e2 = r->exp - 63;
        return w;
    }
    u128 m = ((u128)r->sig) << 1; /* r.exp == -1 here; scale 2^-65 */
    if (c->sign == r->sign)
        m += 1;
    else
        m -= 1;
    w.sig = m;
    w.e2 = -65;
    return w;
}
