/* Invert four RN64 polynomial additions on the retained-square lattice.
 * This is software-only analysis. Exact external preimages and endpoint
 * effects are established independently by the Python driver, not assumed.
 */
#define FPATAN_NO_MAIN
#include "fpatan_candidate.c"

static uint64_t rng_state = UINT64_C(0xd04120260906ae31);

static uint64_t random_word(void)
{
    uint64_t x = (rng_state += UINT64_C(0x9e3779b97f4a7c15));
    x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}

static void multiply67(mpq_t out, const mpq_t a, const mpq_t b)
{
    mpq_mul(out, a, b);
    rounded(out, out, 67, CHOP);
}

static void prevalue(const fpatan_context *ctx, unsigned node, int e, uint64_t m, mpq_t out)
{
    mpq_t square, fourth, term, odd, even;
    mpq_inits(square, fourth, term, odd, even, NULL);
    decode(square, (raw80){(uint16_t)(16383 + e), m});
    multiply67(fourth, square, square);
    if (node < 3) {
        const unsigned constants_index[] = {121, 120, 115};
        unsigned coefficient = constants_index[node];
        multiply67(term, fourth, ctx->rom[coefficient + 2]);
        mpq_add(out, ctx->rom[coefficient], term);
    } else {
        multiply67(term, fourth, ctx->rom[116]);
        mpq_add(even, ctx->rom[114], term);
        rounded(even, even, 67, CHOP);
        multiply67(term, fourth, ctx->rom[117]);
        mpq_add(odd, ctx->rom[115], term);
        rounded(odd, odd, 64, RN);
        multiply67(term, square, odd);
        mpq_add(out, term, even);
    }
    mpq_clears(square, fourth, term, odd, even, NULL);
}

int main(void)
{
    fpatan_context ctx;
    context_init(&ctx);
    /* Synthetic software smoke check; this calls the GMP model, not x87. */
    raw80 one = {0x3fff, UINT64_C(1) << 63}, output;
    int c1;
    unsigned flags;
    if (fpatan_raw80(&ctx, one, one, RN, &output, &c1, &flags) ||
        output.se != 0x3ffe || output.sig != UINT64_C(0xc90fdaa22168c235) ||
        c1 != 1 || flags != 32)
        abort();
    mpq_t value, scaled, target;
    mpq_inits(value, scaled, target, NULL);
    mpz_t whole;
    mpz_init(whole);
    for (unsigned node = 0; node < 4; node++) {
        unsigned bracketed = 0, ties = 0;
        int direction = node == 1 ? -1 : 1;
        for (unsigned search = 0; search < 8192; search++) {
            if (search % 1024 == 0)
                fprintf(stderr, "PROGRESS node=%u searches=%u exact_ties=%u\n", node, search, ties);
            int e = node < 2 ? -14 + (int)(search % 6) : -20 + (int)(search % 8);
            uint64_t low = UINT64_C(1) << 63;
            uint64_t high = e == -9 ? UINT64_C(9) << 60 : UINT64_MAX;
            uint64_t sample = low + random_word() % (high - low);
            prevalue(&ctx, node, e, sample, value);
            int step = qexp(value) - 63;
            mpq_abs(scaled, value);
            scale2(scaled, scaled, -step);
            mpz_fdiv_q(whole, mpq_numref(scaled), mpq_denref(scaled));
            mpz_mul_2exp(whole, whole, 1);
            mpz_add_ui(whole, whole, 1);
            mpq_set_z(target, whole);
            scale2(target, target, step - 1);
            if (mpq_sgn(value) < 0)
                mpq_neg(target, target);
            prevalue(&ctx, node, e, low, value);
            if (direction * mpq_cmp(value, target) >= 0)
                continue;
            prevalue(&ctx, node, e, high, value);
            if (direction * mpq_cmp(value, target) < 0)
                continue;
            bracketed++;
            while (high - low > 1) {
                uint64_t middle = low + ((high - low) >> 1);
                prevalue(&ctx, node, e, middle, value);
                if (direction * mpq_cmp(value, target) >= 0)
                    high = middle;
                else
                    low = middle;
            }
            prevalue(&ctx, node, e, high, value);
            if (mpq_cmp(value, target))
                continue;
            ties++;
            printf("%u %u %d %016" PRIx64 "\n", node, search, e, high);
        }
        fprintf(stderr, "{\"node\":%u,\"searches\":8192,\"bracketed\":%u,\"exact_ties\":%u}\n",
                node, bracketed, ties);
    }
    mpz_clear(whole);
    mpq_clears(value, scaled, target, NULL);
    context_clear(&ctx);
    return ferror(stdout) ? 1 : 0;
}
