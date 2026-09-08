/* H1627 analysis-only extensions of the unchanged H1618 candidate.
 * The outer operation-class dispatcher still chooses polynomial vs table
 * vs tiny paths. Both hypotheses are fixed before reading audit results.
 */
#include <assert.h>
#ifndef H1627_ALL_PORTS
#define H1627_ALL_PORTS 0
#endif
static unsigned long long h1627_row;
static int h1627_c1;

static wv_t h1627_product(wv_t x, wv_t y, int bits, p5_round_t mode)
{
    if (H1627_ALL_PORTS) {
        /* The original natural-port formulation also cuts the first square
         * inputs when a reduced residual has more than64 significant bits.
         * These are global multiply-port rules, not input-specific gates. */
        wv_t one = { 0, 0, 1, 0 };
        x = p5_wv_mul_round(x, one, 67, P5_ROUND_CHOP);
        y = p5_wv_mul_round(y, one, 64, P5_ROUND_CHOP);
    }
    return p5_wv_mul_round(x, y, bits, mode);
}

static sf_t h1627_final(u256 before, int32_t scale, int neg, sf_rc_t rc)
{
    sf_t result = acc_round64_rc(before, scale, neg, rc);
    assert(!(before.hi >> 127));
    assert(result.cls == SF_FIN && result.sig);
    assert(result.exp - 63 >= scale && result.exp - 63 - scale < 256);
    u256 stored = { 0, 0 };
    acc_add_product(&stored, 0, result.sig, 1, result.exp - 63, scale);
    h1627_c1 = stored.hi > before.hi
        || (stored.hi == before.hi && stored.lo > before.lo);
    return result;
}

#define p5_wv_mul_round h1627_product
#define acc_round64_rc h1627_final
#define h1618_cosine_scope h1627_original_scope
#define h1618_cosine h1627_implementation
#include "h1618_asymmetric_cosine.h"
#undef h1618_cosine
#undef h1618_cosine_scope
#undef acc_round64_rc
#undef p5_wv_mul_round

static int h1618_cosine_scope(wv_t magnitude)
{
    /* Widen only this analysis build's scope. Domain selection remains in
     * the original dispatcher; no table/tiny/sine-polynomial override. */
    return magnitude.sig && !magnitude.sign;
}

static sf_t h1618_cosine(wv_t magnitude, int neg_out, sf_rc_t rc)
{
    assert(magnitude.sig && !magnitude.sign);
    int width = u128_width(magnitude.sig);
    u128 odd = magnitude.sig;
    while (!(odd & 1)) odd >>= 1;
    h1627_c1 = -1;
    sf_t result = h1627_implementation(magnitude, neg_out, rc);
    assert(h1627_c1 == 0 || h1627_c1 == 1);
    fprintf(stderr, "%llu %d %d %d %d %d " DIWF "\n",
        h1627_row - 1, magnitude.e2 + width - 1, u128_width(odd),
        h1627_original_scope(magnitude), neg_out, h1627_c1, DIW(magnitude));
    return result;
}
