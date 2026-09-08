/* Backward construction of exact RN64 halfway cases in the direct kernel's
 * final correction sum. Search its square input u, invert the asymmetric
 * square on the 67-bit lattice, then lift z to genuine external operands.
 * Only software arithmetic runs here. No native FPATAN, labels or host atan.
 */
#define FPATAN_NO_MAIN
#include "fpatan_candidate.c"

typedef struct {
    raw80 value;
    int c1;
} endpoint;

static uint64_t random_state = UINT64_C(0xd03920260906a64a);

static uint64_t random_word(void)
{
    uint64_t z = (random_state += UINT64_C(0x9e3779b97f4a7c15));
    z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
    return z ^ (z >> 31);
}

static void correction_prevalue(const fpatan_context *ctx, const mpq_t square, mpq_t out)
{
    mpq_t fourth, odd, even, temporary;
    mpq_inits(fourth, odd, even, temporary, NULL);
    mpq_mul(fourth, square, square);
    rounded(fourth, fourth, 67, CHOP);
    mpq_mul(temporary, fourth, ctx->rom[123]);
    rounded(temporary, temporary, 67, CHOP);
    mpq_add(odd, ctx->rom[121], temporary);
    rounded(odd, odd, 64, RN);
    mpq_mul(temporary, fourth, ctx->rom[122]);
    rounded(temporary, temporary, 67, CHOP);
    mpq_add(even, ctx->rom[120], temporary);
    rounded(even, even, 64, RN);
    mpq_mul(temporary, fourth, odd);
    rounded(temporary, temporary, 67, CHOP);
    mpq_add(odd, ctx->rom[119], temporary);
    rounded(odd, odd, 67, CHOP);
    mpq_mul(temporary, fourth, even);
    rounded(temporary, temporary, 67, CHOP);
    mpq_add(even, ctx->rom[118], temporary);
    rounded(even, even, 67, CHOP);
    mpq_mul(temporary, square, odd);
    rounded(temporary, temporary, 67, CHOP);
    mpq_add(out, temporary, even);
    mpq_clears(fourth, odd, even, temporary, NULL);
}

static void square_value(mpq_t out, int exponent, uint64_t significand)
{
    decode(out, (raw80){(uint16_t)(16383 + exponent), significand});
}

static void h_at(const fpatan_context *ctx, int exponent, uint64_t m, mpq_t out)
{
    mpq_t u;
    mpq_init(u);
    square_value(u, exponent, m);
    correction_prevalue(ctx, u, out);
    mpq_clear(u);
}

static int lift(const mpq_t z, raw80 *y, raw80 *x)
{
    mpq_t b, desired, a, ratio;
    mpq_inits(b, desired, a, ratio, NULL);
    int found = 0;
    for (unsigned i = 0; i < 64 && !found; i++) {
        *x = (raw80){0x3fff, random_word() | (UINT64_C(1) << 63)};
        decode(b, *x);
        mpq_mul(desired, z, b);
        int ignored;
        raw80 middle = encode(desired, RN, &ignored);
        for (int offset = -1; offset <= 1; offset++) {
            if ((offset < 0 && middle.sig == (UINT64_C(1) << 63)) ||
                (offset > 0 && middle.sig == UINT64_MAX))
                continue;
            *y = middle;
            if (offset < 0)
                y->sig--;
            else if (offset > 0)
                y->sig++;
            decode(a, *y);
            mpq_div(ratio, a, b);
            if (mpq_cmp_ui(ratio, 3, 64) > 0 || qexp(ratio) < -40)
                continue;
            rounded(ratio, ratio, 67, CHOP);
            if (!mpq_cmp(ratio, z)) {
                found = 1;
                break;
            }
        }
    }
    mpq_clears(b, desired, a, ratio, NULL);
    return found;
}

static void endpoint_vector(const fpatan_context *ctx, const mpq_t angle, endpoint out[16])
{
    mpq_t truncated, restored;
    mpq_inits(truncated, restored, NULL);
    rounded(truncated, angle, 67, CHOP);
    for (unsigned q = 0; q < 4; q++) {
        if (q == 0)
            mpq_set(restored, angle);
        else if (q == 1)
            mpq_sub(restored, ctx->rom[19], truncated);
        else if (q == 2)
            mpq_sub(restored, ctx->rom[20], truncated);
        else
            mpq_add(restored, ctx->rom[20], truncated);
        const enum mode modes[] = {RN, RD, RU, CHOP};
        for (unsigned mode = 0; mode < 4; mode++) {
            unsigned index = 4 * q + mode;
            out[index].value = encode(restored, modes[mode], &out[index].c1);
        }
    }
    mpq_clears(truncated, restored, NULL);
}

static unsigned compare_halfway(const fpatan_context *ctx, const mpq_t z,
                                const mpq_t square, const mpq_t h_pre, endpoint fixed[16])
{
    mpq_t h, other_h, cubic, tail, angle, other_angle, scaled;
    mpq_inits(h, other_h, cubic, tail, angle, other_angle, scaled, NULL);
    rounded(h, h_pre, 64, RN);
    int exponent = qexp(h_pre) - 63;
    mpq_abs(scaled, h_pre);
    scale2(scaled, scaled, -exponent);
    mpz_t whole, rem, twice;
    mpz_inits(whole, rem, twice, NULL);
    mpz_fdiv_qr(whole, rem, mpq_numref(scaled), mpq_denref(scaled));
    mpz_mul_2exp(twice, rem, 1);
    if (mpz_cmp(twice, mpq_denref(scaled)))
        abort();
    /* Flip the exact-half decision only: nearest/even versus nearest/odd. */
    if (mpz_even_p(whole))
        mpz_add_ui(whole, whole, 1);
    mpq_set_z(other_h, whole);
    scale2(other_h, other_h, exponent);
    if (mpq_sgn(h_pre) < 0)
        mpq_neg(other_h, other_h);
    if (!mpq_cmp(h, other_h))
        abort();
    mpq_mul(cubic, z, square);
    rounded(cubic, cubic, 67, CHOP);
    mpq_mul(tail, cubic, h);
    rounded(tail, tail, 67, CHOP);
    mpq_add(angle, z, tail);
    mpq_mul(tail, cubic, other_h);
    rounded(tail, tail, 67, CHOP);
    mpq_add(other_angle, z, tail);
    endpoint other[16];
    endpoint_vector(ctx, angle, fixed);
    endpoint_vector(ctx, other_angle, other);
    unsigned mask = 0;
    for (unsigned i = 0; i < 16; i++) {
        if (fixed[i].value.se != other[i].value.se || fixed[i].value.sig != other[i].value.sig ||
            fixed[i].c1 != other[i].c1)
            mask |= 1u << i;
    }
    mpz_clears(whole, rem, twice, NULL);
    mpq_clears(h, other_h, cubic, tail, angle, other_angle, scaled, NULL);
    return mask;
}

int main(void)
{
    fpatan_context ctx;
    context_init(&ctx);
    mpq_t pre, target, scaled, u, z, narrowed, actual_u;
    mpq_inits(pre, target, scaled, u, z, narrowed, actual_u, NULL);
    mpz_t whole, radicand, root, m;
    mpz_inits(whole, radicand, root, m, NULL);
    unsigned bracketed = 0, h_ties = 0, square_preimages = 0, lift_unknown = 0;
    unsigned rows = 0, visible = 0;
    for (unsigned search = 0; search < 65536; search++) {
        if (search % 1024 == 0)
            fprintf(stderr, "PROGRESS searches=%u h_ties=%u lifted=%u visible=%u\n",
                    search, h_ties, rows, visible);
        int e = search & 1 ? -9 : -10;
        uint64_t low = UINT64_C(1) << 63;
        uint64_t high = e == -9 ? UINT64_C(9) << 60 : UINT64_MAX;
        uint64_t sample = low + random_word() % (high - low);
        h_at(&ctx, e, sample, pre);
        int h_scale = qexp(pre) - 63;
        mpq_abs(scaled, pre);
        scale2(scaled, scaled, -h_scale);
        mpz_fdiv_q(whole, mpq_numref(scaled), mpq_denref(scaled));
        mpz_mul_2exp(whole, whole, 1);
        mpz_add_ui(whole, whole, 1);
        mpq_set_z(target, whole);
        scale2(target, target, h_scale - 1);
        mpq_neg(target, target);
        h_at(&ctx, e, low, pre);
        if (mpq_cmp(pre, target) >= 0)
            continue;
        h_at(&ctx, e, high, pre);
        if (mpq_cmp(pre, target) < 0)
            continue;
        bracketed++;
        while (high - low > 1) {
            uint64_t middle = low + ((high - low) >> 1);
            h_at(&ctx, e, middle, pre);
            if (mpq_cmp(pre, target) >= 0)
                high = middle;
            else
                low = middle;
        }
        h_at(&ctx, e, high, pre);
        if (mpq_cmp(pre, target))
            continue;
        h_ties++;
        square_value(u, e, high);
        mpz_import(radicand, 1, 1, sizeof(high), 0, 0, &high);
        mpz_mul_2exp(radicand, radicand, (unsigned)(69 + (e & 1)));
        mpz_sqrt(root, radicand);
        int z_scale = (e == -9 ? -5 : e / 2) - 66;
        for (int delta = -16; delta <= 16; delta++) {
            if (delta < 0)
                mpz_sub_ui(m, root, (unsigned)-delta);
            else
                mpz_add_ui(m, root, (unsigned)delta);
            if (mpz_sizeinbase(m, 2) != 67)
                continue;
            mpq_set_z(z, m);
            scale2(z, z, z_scale);
            if (mpq_cmp_ui(z, 3, 64) > 0)
                continue;
            rounded(narrowed, z, 64, CHOP);
            mpq_mul(actual_u, z, narrowed);
            rounded(actual_u, actual_u, 64, RN);
            if (mpq_cmp(actual_u, u))
                continue;
            square_preimages++;
            endpoint fixed[16];
            unsigned mask = compare_halfway(&ctx, z, u, target, fixed);
            raw80 y, x;
            if (!lift(z, &y, &x)) {
                lift_unknown++;
                continue;
            }
            /* Check every positive restoration and RC through the complete
             * production graph before retaining the lifted external pair. */
            const enum mode modes[] = {RN, RD, RU, CHOP};
            for (unsigned q = 0; q < 4; q++) {
                raw80 iy = q < 2 ? y : x, ix = q < 2 ? x : y;
                if (q & 1)
                    ix.se |= 0x8000;
                for (unsigned mode = 0; mode < 4; mode++) {
                    raw80 output;
                    int c1;
                    unsigned flags;
                    if (fpatan_raw80(&ctx, iy, ix, modes[mode], &output, &c1, &flags))
                        abort();
                    endpoint expected = fixed[4 * q + mode];
                    if (output.se != expected.value.se || output.sig != expected.value.sig ||
                        c1 != expected.c1 || flags != 32)
                        abort();
                }
            }
            gmp_printf("%u %d %016" PRIx64 " %Zx %d %04x %016" PRIx64
                       " %04x %016" PRIx64 " %04x\n", search, e, high, m, z_scale,
                       y.se, y.sig, x.se, x.sig, mask);
            rows++;
            visible += mask != 0;
        }
    }
    fprintf(stderr, "{\"searches\":65536,\"bracketed\":%u,\"h_ties\":%u,"
                    "\"square_preimages\":%u,\"lift_unknown\":%u,\"rows\":%u,"
                    "\"visible\":%u,\"hardware_executed\":false}\n",
            bracketed, h_ties, square_preimages, lift_unknown, rows, visible);
    mpz_clears(whole, radicand, root, m, NULL);
    mpq_clears(pre, target, scaled, u, z, narrowed, actual_u, NULL);
    context_clear(&ctx);
    return ferror(stdout) ? 1 : 0;
}
