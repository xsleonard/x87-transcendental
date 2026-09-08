/* Exact software search for endpoint-visible changes at the four D0041
 * RN64 additions. This reuses the frozen target expression, not its sample
 * schedule. No native FPATAN, hardware labels, or production changes.
 */
#define main d0041_frozen_miner_main
#include "d0041_inner_tie_miner.c"
#undef main

typedef struct {
    raw80 raw;
    int c1;
} tie_endpoint;

static int opposite_half(mpq_t out, const mpq_t value)
{
    int negative = mpq_sgn(value) < 0;
    mpq_t scaled;
    mpq_init(scaled);
    mpq_abs(scaled, value);
    int step = qexp(value) - 63;
    scale2(scaled, scaled, -step);
    mpz_t whole, remainder;
    mpz_inits(whole, remainder, NULL);
    mpz_fdiv_qr(whole, remainder, mpq_numref(scaled), mpq_denref(scaled));
    mpz_mul_2exp(remainder, remainder, 1);
    if (mpz_cmp(remainder, mpq_denref(scaled)))
        abort();
    int parity = mpz_odd_p(whole);
    if (!parity)
        mpz_add_ui(whole, whole, 1);
    mpq_set_z(out, whole);
    scale2(out, out, step);
    if (negative)
        mpq_neg(out, out);
    mpz_clears(whole, remainder, NULL);
    mpq_clear(scaled);
    return parity;
}

static void correction(const fpatan_context *ctx, unsigned node, int altered,
                       const mpq_t u, mpq_t out)
{
    mpq_t v, temporary, odd, even;
    mpq_inits(v, temporary, odd, even, NULL);
    multiply67(v, u, u);
    if (node >= 2) {
        multiply67(temporary, v, ctx->rom[116]);
        mpq_add(even, ctx->rom[114], temporary);
        rounded(even, even, 67, CHOP);
        multiply67(temporary, v, ctx->rom[117]);
        mpq_add(odd, ctx->rom[115], temporary);
        if (node == 2 && altered)
            opposite_half(odd, odd);
        else
            rounded(odd, odd, 64, RN);
    } else {
        multiply67(temporary, v, ctx->rom[123]);
        mpq_add(odd, ctx->rom[121], temporary);
        if (node == 0 && altered)
            opposite_half(odd, odd);
        else
            rounded(odd, odd, 64, RN);
        multiply67(temporary, v, ctx->rom[122]);
        mpq_add(even, ctx->rom[120], temporary);
        if (node == 1 && altered)
            opposite_half(even, even);
        else
            rounded(even, even, 64, RN);
        multiply67(temporary, v, odd);
        mpq_add(odd, ctx->rom[119], temporary);
        rounded(odd, odd, 67, CHOP);
        multiply67(temporary, v, even);
        mpq_add(even, ctx->rom[118], temporary);
        rounded(even, even, 67, CHOP);
    }
    multiply67(temporary, u, odd);
    mpq_add(out, temporary, even);
    if (node == 3 && altered)
        opposite_half(out, out);
    else
        rounded(out, out, 64, RN);
    mpq_clears(v, temporary, odd, even, NULL);
}

static void endpoints(const fpatan_context *ctx, const mpq_t angle,
                      tie_endpoint values[16])
{
    mpq_t cut, restored_angle;
    mpq_inits(cut, restored_angle, NULL);
    rounded(cut, angle, 67, CHOP);
    for (unsigned quadrant = 0; quadrant < 4; quadrant++) {
        if (!quadrant)
            mpq_set(restored_angle, angle);
        else if (quadrant == 1)
            mpq_sub(restored_angle, ctx->rom[19], cut);
        else if (quadrant == 2)
            mpq_sub(restored_angle, ctx->rom[20], cut);
        else
            mpq_add(restored_angle, ctx->rom[20], cut);
        for (unsigned mode = 0; mode < 4; mode++) {
            unsigned index = 4 * quadrant + mode;
            values[index].raw = encode(restored_angle, (enum mode)mode, &values[index].c1);
        }
    }
    mpq_clears(cut, restored_angle, NULL);
}

static unsigned endpoint_mask(const fpatan_context *ctx, const mpq_t a, const mpq_t b)
{
    tie_endpoint first[16], second[16];
    endpoints(ctx, a, first);
    endpoints(ctx, b, second);
    unsigned mask = 0;
    for (unsigned i = 0; i < 16; i++) {
        if (first[i].raw.se != second[i].raw.se || first[i].raw.sig != second[i].raw.sig ||
            first[i].c1 != second[i].c1)
            mask |= 1u << i;
    }
    return mask;
}

static int valid_cell(unsigned cell, const mpq_t z)
{
    /* This inverse-ratio test only proposes a cell. The Python lift must
     * still prove the real, separately cut external reduction equals z. */
    mpq_t c, ratio, denominator, temporary;
    mpq_inits(c, ratio, denominator, temporary, NULL);
    mpq_set_ui(c, cell, 32);
    mpq_add(ratio, c, z);
    mpq_mul(denominator, c, z);
    mpq_set_ui(temporary, 1, 1);
    mpq_sub(denominator, temporary, denominator);
    mpq_div(ratio, ratio, denominator);
    mpq_set_ui(temporary, 2 * cell - 1, 64);
    int good = mpq_cmp(ratio, temporary) > 0 && mpq_cmp_ui(ratio, 1, 1) <= 0;
    mpq_set_ui(temporary, 2 * cell + 1, 64);
    good = good && mpq_cmp(ratio, temporary) <= 0;
    mpq_clears(c, ratio, denominator, temporary, NULL);
    return good;
}

int main(int argc, char **argv)
{
    if (argc != 4) {
        fprintf(stderr, "usage: miner NODE SEARCHES SQUARE_EXPONENT\n");
        return 2;
    }
    unsigned node = (unsigned)strtoul(argv[1], NULL, 10);
    unsigned searches = (unsigned)strtoul(argv[2], NULL, 10);
    int e = atoi(argv[3]);
    if (node > 3 || !searches || e < -30 || e > (node < 2 ? -9 : -13))
        return 2;
    rng_state ^= ((uint64_t)node << 48) ^ searches ^ (uint64_t)(-e);
    fpatan_context ctx;
    context_init(&ctx);
    mpq_t pre, target, scaled, u, first_h, second_h, z, narrow, square;
    mpq_t cubic, tail, first_kernel, second_kernel, first_cut, second_cut, a, b;
    mpq_inits(pre, target, scaled, u, first_h, second_h, z, narrow, square,
              cubic, tail, first_kernel, second_kernel, first_cut, second_cut, a, b, NULL);
    mpz_t whole, root, radicand, m;
    mpz_inits(whole, root, radicand, m, NULL);
    uint64_t ties = 0, changed_h = 0, preimages = 0, cut_changes = 0, witnesses = 0;
    for (unsigned search = 0; search < searches; search++) {
        if (search % 4096 == 0)
            fprintf(stderr, "PROGRESS node=%u search=%u ties=%" PRIu64 " H=%" PRIu64
                    " preimages=%" PRIu64 " cuts=%" PRIu64 " witnesses=%" PRIu64 "\n",
                    node, search, ties, changed_h, preimages, cut_changes, witnesses);
        uint64_t low = UINT64_C(1) << 63;
        uint64_t high = e == -9 ? UINT64_C(9) << 60 : UINT64_MAX;
        uint64_t sample = low + random_word() % (high - low);
        prevalue(&ctx, node, e, sample, pre);
        int step = qexp(pre) - 63;
        mpq_abs(scaled, pre);
        scale2(scaled, scaled, -step);
        mpz_fdiv_q(whole, mpq_numref(scaled), mpq_denref(scaled));
        mpz_mul_2exp(whole, whole, 1);
        mpz_add_ui(whole, whole, 1);
        mpq_set_z(target, whole);
        scale2(target, target, step - 1);
        if (mpq_sgn(pre) < 0)
            mpq_neg(target, target);
        int direction = node == 1 ? -1 : 1;
        prevalue(&ctx, node, e, low, pre);
        if (direction * mpq_cmp(pre, target) >= 0)
            continue;
        prevalue(&ctx, node, e, high, pre);
        if (direction * mpq_cmp(pre, target) < 0)
            continue;
        while (high - low > 1) {
            uint64_t middle = low + ((high - low) >> 1);
            prevalue(&ctx, node, e, middle, pre);
            if (direction * mpq_cmp(pre, target) >= 0)
                high = middle;
            else
                low = middle;
        }
        prevalue(&ctx, node, e, high, pre);
        if (mpq_cmp(pre, target))
            continue;
        int parity = opposite_half(scaled, pre);
        decode(u, (raw80){(uint16_t)(16383 + e), high});
        correction(&ctx, node, 0, u, first_h);
        correction(&ctx, node, 1, u, second_h);
        int h_changed = mpq_cmp(first_h, second_h) != 0;
        ties++;
        changed_h += h_changed;
        printf("T %u %u %d %016" PRIx64 " %d %d\n", node, search, e, high, parity, h_changed);
        if (!h_changed)
            continue;
        mpz_import(radicand, 1, 1, sizeof(high), 0, 0, &high);
        mpz_mul_2exp(radicand, radicand, (unsigned)(69 + (e & 1)));
        mpz_sqrt(root, radicand);
        int z_step = (e >= 0 ? e / 2 : (e - 1) / 2) - 66;
        for (int offset = -16; offset <= 16; offset++) {
            if (offset < 0)
                mpz_sub_ui(m, root, (unsigned)-offset);
            else
                mpz_add_ui(m, root, (unsigned)offset);
            if (mpz_sizeinbase(m, 2) != 67)
                continue;
            mpq_set_z(z, m);
            scale2(z, z, z_step);
            if (node < 2 && mpq_cmp_ui(z, 3, 64) > 0)
                continue;
            rounded(narrow, z, 64, CHOP);
            mpq_mul(square, z, narrow);
            rounded(square, square, 64, RN);
            if (mpq_cmp(square, u))
                continue;
            preimages++;
            multiply67(cubic, z, u);
            multiply67(tail, cubic, first_h);
            mpq_add(first_kernel, z, tail);
            multiply67(tail, cubic, second_h);
            mpq_add(second_kernel, z, tail);
            rounded(first_cut, first_kernel, 67, CHOP);
            rounded(second_cut, second_kernel, 67, CHOP);
            int cut_changed = mpq_cmp(first_cut, second_cut) != 0;
            cut_changes += cut_changed;
            gmp_printf("Z %u %u %d %016" PRIx64 " %d %Zx %d %d\n",
                       node, search, e, high, parity, m, z_step, cut_changed);
            if (node >= 2 && !cut_changed)
                continue;
            for (int sign = 1; sign >= (node < 2 ? 1 : -1); sign -= 2) {
                if (sign < 0)
                    mpq_neg(z, z);
                for (unsigned cell = node < 2 ? 0 : 2; cell <= (node < 2 ? 0 : 32); cell++) {
                    if (cell && !valid_cell(cell, z))
                        continue;
                    if (cell) {
                        if (sign > 0) {
                            mpq_add(a, ctx.rom[124 + cell], first_cut);
                            mpq_add(b, ctx.rom[124 + cell], second_cut);
                        } else {
                            mpq_sub(a, ctx.rom[124 + cell], first_cut);
                            mpq_sub(b, ctx.rom[124 + cell], second_cut);
                        }
                    } else {
                        mpq_set(a, first_kernel);
                        mpq_set(b, second_kernel);
                    }
                    unsigned mask = endpoint_mask(&ctx, a, b);
                    witnesses += mask != 0;
                    gmp_printf("W %u %u %d %016" PRIx64 " %d %Zx %d %d %u %04x\n",
                               node, search, e, high, parity, m, z_step, sign, cell, mask);
                }
            }
        }
    }
    fprintf(stderr, "{\"node\":%u,\"searches\":%u,\"square_exponent\":%d,\"ties\":%" PRIu64
            ",\"changed_H\":%" PRIu64 ",\"square_preimages\":%" PRIu64 ",\"cut_changes\":%" PRIu64
            ",\"endpoint_cell_witnesses\":%" PRIu64 "}\n",
            node, searches, e, ties, changed_h, preimages, cut_changes, witnesses);
    mpz_clears(whole, root, radicand, m, NULL);
    mpq_clears(pre, target, scaled, u, first_h, second_h, z, narrow, square,
               cubic, tail, first_kernel, second_kernel, first_cut, second_cut, a, b, NULL);
    context_clear(&ctx);
    return ferror(stdout) ? 1 : 0;
}
