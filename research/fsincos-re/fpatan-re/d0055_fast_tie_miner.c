/* Exact integer-dyadic tie miner, analysis only. No native FPATAN calls.
 * The long kernels stop after an unchanged outer sum: the remaining graph
 * then has identical inputs, so computing it twice would add no evidence.
 * Replay mode always evaluates the full graph to test that early exit.
 */
#define FPATAN_NO_MAIN
#include "fpatan_candidate.c"
#include <assert.h>
#include <limits.h>

typedef struct {
    mpz_t n;
    int step;
} dyadic;

typedef struct {
    mpz_t low_v, high_v;
    uint64_t low_u, high_u, coefficient, first, modulus, count;
    int v_step, coefficient_step, unit, drop;
} inverse_domain;

static dyadic coefficients[157];
static dyadic u, fourth, target, product, inner[2], outer[2];
static dyadic other_inner, other_outer, temporary, h[2];
static mpz_t aligned_a, aligned_b, magnitude, quotient;
static uint64_t random_state;

static void dyadic_init(dyadic *a)
{
    mpz_init2(a->n, 256);
    a->step = 0;
}

static void copy_dyadic(dyadic *out, const dyadic *in)
{
    mpz_set(out->n, in->n);
    out->step = in->step;
}

static void add_dyadic(dyadic *out, const dyadic *a, const dyadic *b)
{
    int step = a->step < b->step ? a->step : b->step;
    mpz_mul_2exp(aligned_a, a->n, (unsigned)(a->step - step));
    mpz_mul_2exp(aligned_b, b->n, (unsigned)(b->step - step));
    mpz_add(out->n, aligned_a, aligned_b);
    out->step = step;
}

static void multiply_dyadic(dyadic *out, const dyadic *a, const dyadic *b)
{
    int step = a->step + b->step;
    mpz_mul(out->n, a->n, b->n);
    out->step = step;
}

static void round_dyadic(dyadic *out, const dyadic *in, int bits,
                         int nearest, int opposite)
{
    int sign = mpz_sgn(in->n);
    assert(sign);
    int step = in->step;
    mpz_abs(magnitude, in->n);
    int shift = (int)mpz_sizeinbase(magnitude, 2) - bits;
    if (shift <= 0) {
        assert(!opposite);
        mpz_mul_2exp(out->n, in->n, (unsigned)-shift);
    } else {
        mpz_fdiv_q_2exp(quotient, magnitude, (unsigned)shift);
        int half_bit = mpz_tstbit(magnitude, (unsigned)shift - 1);
        int lower_zero = mpz_divisible_2exp_p(magnitude, (unsigned)shift - 1);
        int parity = mpz_odd_p(quotient);
        int increment = nearest && half_bit && (!lower_zero || parity);
        if (opposite) {
            assert(nearest && half_bit && lower_zero);
            increment = !parity;
        }
        if (increment)
            mpz_add_ui(quotient, quotient, 1);
        mpz_set(out->n, quotient);
        if (sign < 0)
            mpz_neg(out->n, out->n);
    }
    out->step = step + shift;
}

static void product67(dyadic *out, const dyadic *a, const dyadic *b)
{
    multiply_dyadic(out, a, b);
    round_dyadic(out, out, 67, 0, 0);
}

static int equal_dyadic(const dyadic *a, const dyadic *b)
{
    int step = a->step < b->step ? a->step : b->step;
    mpz_mul_2exp(aligned_a, a->n, (unsigned)(a->step - step));
    mpz_mul_2exp(aligned_b, b->n, (unsigned)(b->step - step));
    return mpz_cmp(aligned_a, aligned_b) == 0;
}

static int target_parity(void)
{
    mpz_abs(magnitude, target.n);
    int shift = (int)mpz_sizeinbase(magnitude, 2) - 64;
    assert(shift > 0 && mpz_tstbit(magnitude, (unsigned)shift - 1));
    assert(mpz_divisible_2exp_p(magnitude, (unsigned)shift - 1));
    return mpz_tstbit(magnitude, (unsigned)shift);
}

static void correction_from(const dyadic *odd, const dyadic *even, dyadic *out)
{
    product67(&temporary, &u, odd);
    add_dyadic(&temporary, &temporary, even);
    round_dyadic(out, &temporary, 64, 1, 0);
}

static int evaluate(unsigned node, int exponent, uint64_t word, int full,
                    int *parity, int *outer_changed)
{
    static const unsigned base[] = {121, 120, 115};
    static const unsigned outer_base[] = {119, 118};
    mpz_set_ui(u.n, word);
    u.step = exponent - 63;
    product67(&fourth, &u, &u);
    product67(&product, &fourth, &coefficients[base[node] + 2]);
    add_dyadic(&target, &coefficients[base[node]], &product);
    *parity = target_parity();
    round_dyadic(&inner[0], &target, 64, 1, 0);
    round_dyadic(&inner[1], &target, 64, 1, 1);
    for (unsigned variant = 0; variant < 2; variant++) {
        if (node == 2) {
            copy_dyadic(&outer[variant], &inner[variant]);
        } else {
            product67(&product, &fourth, &inner[variant]);
            add_dyadic(&temporary, &coefficients[outer_base[node]], &product);
            round_dyadic(&outer[variant], &temporary, 67, 0, 0);
        }
    }
    *outer_changed = !equal_dyadic(&outer[0], &outer[1]);
    if (!full && !*outer_changed)
        return 0;
    if (node == 2) {
        product67(&product, &fourth, &coefficients[116]);
        add_dyadic(&temporary, &coefficients[114], &product);
        round_dyadic(&other_outer, &temporary, 67, 0, 0);
    } else {
        unsigned other = 1 - node;
        product67(&product, &fourth, &coefficients[base[other] + 2]);
        add_dyadic(&temporary, &coefficients[base[other]], &product);
        round_dyadic(&other_inner, &temporary, 64, 1, 0);
        product67(&product, &fourth, &other_inner);
        add_dyadic(&temporary, &coefficients[outer_base[other]], &product);
        round_dyadic(&other_outer, &temporary, 67, 0, 0);
    }
    for (unsigned variant = 0; variant < 2; variant++) {
        if (node == 1)
            correction_from(&other_outer, &outer[variant], &h[variant]);
        else
            correction_from(&outer[variant], &other_outer, &h[variant]);
    }
    return !equal_dyadic(&h[0], &h[1]);
}

static uint64_t next_random(void)
{
    uint64_t x = (random_state += UINT64_C(0x9e3779b97f4a7c15));
    x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}

static void initialize(void)
{
    assert(sizeof(unsigned long) >= sizeof(uint64_t));
    fpatan_context ctx;
    context_init(&ctx);
    for (unsigned i = 0; i < 157; i++) {
        dyadic_init(&coefficients[i]);
        mpz_set(coefficients[i].n, mpq_numref(ctx.rom[i]));
        coefficients[i].step = 1 - (int)mpz_sizeinbase(mpq_denref(ctx.rom[i]), 2);
        assert(mpz_popcount(mpq_denref(ctx.rom[i])) == 1);
    }
    context_clear(&ctx);
    dyadic *all[] = {&u, &fourth, &target, &product, &inner[0], &inner[1],
        &outer[0], &outer[1], &other_inner, &other_outer, &temporary, &h[0], &h[1]};
    for (unsigned i = 0; i < sizeof(all) / sizeof(all[0]); i++)
        dyadic_init(all[i]);
    mpz_inits(aligned_a, aligned_b, magnitude, quotient, NULL);
}

static void cleanup(void)
{
    for (unsigned i = 0; i < 157; i++)
        mpz_clear(coefficients[i].n);
    dyadic *all[] = {&u, &fourth, &target, &product, &inner[0], &inner[1],
        &outer[0], &outer[1], &other_inner, &other_outer, &temporary, &h[0], &h[1]};
    for (unsigned i = 0; i < sizeof(all) / sizeof(all[0]); i++)
        mpz_clear(all[i]->n);
    mpz_clears(aligned_a, aligned_b, magnitude, quotient, NULL);
}

static int replay(unsigned node, int exponent)
{
    uint64_t word;
    while (scanf("%" SCNx64, &word) == 1) {
        int parity, outer_changed;
        int changed = evaluate(node, exponent, word, 1, &parity, &outer_changed);
        gmp_printf("R %016" PRIx64 " %d %d %d %Zx %d %Zx %d %Zx %d\n",
            word, parity, changed, outer_changed, target.n, target.step,
            h[0].n, h[0].step, h[1].n, h[1].step);
    }
    return ferror(stdin) || ferror(stdout);
}

static int search(unsigned node, int exponent, uint64_t searches, const char *path)
{
    FILE *source = fopen(path, "r");
    if (!source)
        return 2;
    unsigned domain_count;
    assert(fscanf(source, "%u", &domain_count) == 1 && domain_count > 0 && domain_count <= 2);
    inverse_domain domains[2];
    for (unsigned i = 0; i < domain_count; i++) {
        inverse_domain *d = &domains[i];
        mpz_inits(d->low_v, d->high_v, NULL);
        assert(gmp_fscanf(source,
            "%" SCNx64 " %" SCNx64 " %Zx %Zx %d %d %" SCNx64 " %d %d %" SCNx64 " %" SCNx64 " %" SCNx64,
            &d->low_u, &d->high_u, d->low_v, d->high_v, &d->v_step, &d->drop,
            &d->coefficient, &d->coefficient_step, &d->unit, &d->first, &d->modulus, &d->count) == 12);
        assert(d->low_u <= d->high_u && d->coefficient && d->count && d->modulus);
        assert((__uint128_t)d->first + (__uint128_t)d->modulus * (d->count - 1) <= UINT64_MAX);
    }
    assert(fclose(source) == 0);
    mpz_t lower, upper, low_v, high_v, low_u, high_u, radicand, root;
    mpz_inits(lower, upper, low_v, high_v, low_u, high_u, radicand, root, NULL);
    random_state = UINT64_C(0xd05520260906ae31) ^ searches ^ ((uint64_t)node << 48) ^ (uint64_t)(-exponent);
    uint64_t ties = 0, outer_changes = 0, h_changes = 0, parities[2] = {0, 0};
    for (uint64_t index = 0; index < searches; index++) {
        inverse_domain *d = &domains[index % domain_count];
        uint64_t term = d->first + d->modulus * (next_random() % d->count);
        int alignment = d->unit - d->v_step - d->coefficient_step;
        int product_step = 63 - __builtin_clzll(term) + d->unit - 66;
        int discard = product_step - d->v_step - d->coefficient_step;
        assert(alignment > 0 && discard >= 0);
        mpz_set_ui(lower, term);
        mpz_mul_2exp(lower, lower, (unsigned)alignment);
        mpz_set_ui(upper, 1);
        mpz_mul_2exp(upper, upper, (unsigned)discard);
        mpz_add(upper, upper, lower);
        mpz_sub_ui(upper, upper, 1);
        mpz_cdiv_q_ui(low_v, lower, d->coefficient);
        mpz_fdiv_q_ui(high_v, upper, d->coefficient);
        if (mpz_cmp(low_v, d->low_v) < 0)
            mpz_set(low_v, d->low_v);
        if (mpz_cmp(high_v, d->high_v) > 0)
            mpz_set(high_v, d->high_v);
        if (mpz_cmp(low_v, high_v) <= 0) {
            mpz_mul_2exp(radicand, low_v, (unsigned)d->drop);
            mpz_sqrt(low_u, radicand);
            mpz_mul(root, low_u, low_u);
            if (mpz_cmp(root, radicand))
                mpz_add_ui(low_u, low_u, 1);
            mpz_add_ui(radicand, high_v, 1);
            mpz_mul_2exp(radicand, radicand, (unsigned)d->drop);
            mpz_sub_ui(radicand, radicand, 1);
            mpz_sqrt(high_u, radicand);
            if (mpz_cmp_ui(low_u, d->low_u) < 0)
                mpz_set_ui(low_u, d->low_u);
            if (mpz_cmp_ui(high_u, d->high_u) > 0)
                mpz_set_ui(high_u, d->high_u);
            if (mpz_cmp(low_u, high_u) <= 0) {
                assert(mpz_fits_ulong_p(low_u) && mpz_fits_ulong_p(high_u));
                uint64_t first = mpz_get_ui(low_u), last = mpz_get_ui(high_u);
                for (uint64_t word = first;; word++) {
                    int parity, outer_changed;
                    int changed = evaluate(node, exponent, word, 0, &parity, &outer_changed);
                    ties++;
                    parities[parity]++;
                    outer_changes += (unsigned)outer_changed;
                    h_changes += (unsigned)changed;
                    printf("T %u %" PRIu64 " %d %016" PRIx64 " %d %d %d\n",
                        node, index, exponent, word, parity, changed, outer_changed);
                    if (word == last)
                        break;
                }
            }
        }
        if ((index & ((UINT64_C(1) << 24) - 1)) == 0) {
            fflush(stdout);
            fprintf(stderr, "PROGRESS targets=%" PRIu64 " ties=%" PRIu64 " outer=%" PRIu64 " H=%" PRIu64 "\n",
                    index + 1, ties, outer_changes, h_changes);
        }
    }
    fprintf(stderr, "{\"target_searches\":%" PRIu64 ",\"tie_occurrences\":%" PRIu64
        ",\"parity0\":%" PRIu64 ",\"parity1\":%" PRIu64 ",\"first_outer_changed\":%" PRIu64
        ",\"H_changed\":%" PRIu64 "}\n", searches, ties, parities[0], parities[1], outer_changes, h_changes);
    mpz_clears(lower, upper, low_v, high_v, low_u, high_u, radicand, root, NULL);
    for (unsigned i = 0; i < domain_count; i++)
        mpz_clears(domains[i].low_v, domains[i].high_v, NULL);
    return ferror(stdout) || ferror(stderr);
}

int main(int argc, char **argv)
{
    if (argc != 4 && argc != 6) {
        fprintf(stderr, "usage: miner replay NODE EXPONENT | miner search NODE EXPONENT COUNT DOMAINS\n");
        return 2;
    }
    unsigned node = (unsigned)strtoul(argv[2], NULL, 10);
    int exponent = atoi(argv[3]);
    assert(node <= 2 && exponent <= (node == 2 ? -13 : -9));
    initialize();
    int result;
    if (argc == 4 && !strcmp(argv[1], "replay"))
        result = replay(node, exponent);
    else if (argc == 6 && !strcmp(argv[1], "search")) {
        uint64_t count = strtoull(argv[4], NULL, 10);
        assert(count);
        result = search(node, exponent, count, argv[5]);
    } else
        result = 2;
    cleanup();
    return result;
}
