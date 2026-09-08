/* H1714 software-only adversarial generator. The builder inserts a passive
 * accumulator probe into a COPY of the promoted source. No arithmetic, ROM,
 * selector, or production source is changed. Hardware labels are never read.
 */
static uint64_t h1714_rng = UINT64_C(0x1714acceda7ab17e);
static uint64_t h1714_random(void)
{
    h1714_rng ^= h1714_rng << 13;
    h1714_rng ^= h1714_rng >> 7;
    h1714_rng ^= h1714_rng << 17;
    return h1714_rng;
}

static int h1714_compare(u256 a, u256 b)
{
    return a.hi != b.hi ? (a.hi > b.hi ? 1 : -1) :
        a.lo != b.lo ? (a.lo > b.lo ? 1 : -1) : 0;
}

static void h1714_eval(x80_t input, int kind)
{
    x80_t sine, cosine;
    h1714_count = 0;
    if (kind < 2) {
        assert(fsincos_ref(input, &sine, &cosine, SF_RZ) == FSINCOS_OK);
        assert(h1714_count == 2);
    } else {
        assert(general_standalone_ref(input, kind - 2, &sine, SF_RZ) == FSINCOS_OK);
        assert(h1714_count == 1);
    }
}

static int h1714_target_compare(x80_t input, int kind, u128 target, int exponent)
{
    h1714_eval(input, kind);
    unsigned lane = kind < 2 ? kind : 0;
    int scale = h1714_scale[lane];
    /* All selected direct polynomial/table leading values are positive.
     * The target scale is above the exact accumulator scale. */
    assert(exponent >= scale && exponent - scale < 192);
    u256 wanted = {0, 0};
    acc_add_product(&wanted, 0, target, 1, exponent, scale);
    return h1714_compare(h1714_pre[lane], wanted);
}

static void h1714_inverse(void)
{
    uint64_t count = 0;
    /* In the low polynomial binades cosine advances much more slowly than
     * the external operand. Bisect two random final rounding thresholds of
     * each type per binade, for BOTH promoted cosine graphs. These are local
     * bracket witnesses, not a claim of global graph monotonicity. */
    for (int e = -32; e <= -3; ++e) for (int kind = 1; kind <= 3; kind += 2)
    for (int half = 0; half <= 1; ++half) for (int seed = 0; seed < 2; ++seed) {
        uint16_t se = (uint16_t)(e + 16383);
        x80_t sample = {se, h1714_random() | (UINT64_C(1) << 63)};
        h1714_eval(sample, kind);
        unsigned lane = kind < 2 ? kind : 0;
        sf_t down = acc_round64_rc(h1714_pre[lane], h1714_scale[lane], 0, SF_RZ);
        u128 target = (u128)down.sig * 2 + half;
        int exponent = down.exp - 64;
        uint64_t lo = UINT64_C(1) << 63, hi = UINT64_MAX;
        if (h1714_target_compare((x80_t){se, lo}, kind, target, exponent) <= 0 ||
            h1714_target_compare((x80_t){se, hi}, kind, target, exponent) >= 0) continue;
        while (hi - lo > 1) {
            uint64_t mid = lo + (hi - lo) / 2;
            if (h1714_target_compare((x80_t){se, mid}, kind, target, exponent) > 0) lo = mid;
            else hi = mid;
        }
        assert(h1714_target_compare((x80_t){se, lo}, kind, target, exponent) > 0);
        assert(h1714_target_compare((x80_t){se, hi}, kind, target, exponent) <= 0);
        for (int side = 0; side < 2; ++side) {
            uint64_t sig = side ? hi : lo;
            printf("%04x %016llx inverse_%s %d %d %016llx %016llx %d\n", se,
                (unsigned long long)sig, half ? "half" : "integer", kind, e,
                (unsigned long long)(target >> 64), (unsigned long long)target, exponent);
            count++;
        }
    }
    fprintf(stderr, "INVERSE proposals=%llu\n", (unsigned long long)count);
}

typedef struct { uint64_t score, sig; uint16_t se; } h1714_best;
static h1714_best h1714_min[2][4][2][2];
static void h1714_rank(x80_t input, int region, int kind)
{
    unsigned lane = kind < 2 ? kind : 0;
    u256 pre = h1714_pre[lane];
    int width = pre.hi ? 128 + u128_width(pre.hi) : u128_width(pre.lo);
    int shift = width - 128;
    u128 normalized;
    if (shift >= 0) normalized = shift == 0 ? pre.lo :
        (pre.hi << (128 - shift)) | (pre.lo >> shift);
    else normalized = pre.lo << -shift;
    uint64_t fraction = (uint64_t)normalized;
    uint64_t half = UINT64_C(1) << 63;
    uint64_t scores[] = {fraction < half ? fraction : UINT64_MAX - fraction,
        fraction > half ? fraction - half : half - fraction};
    for (int boundary = 0; boundary < 2; ++boundary) {
        h1714_best value = {scores[boundary], input.sig, input.se};
        for (int rank = 0; rank < 2; ++rank) {
            h1714_best *old = &h1714_min[region][kind][boundary][rank];
            if (value.score < old->score) { h1714_best swap = *old; *old = value; value = swap; }
        }
    }
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    uint64_t count = strtoull(argv[1], NULL, 10);
    for (unsigned i = 0; i < sizeof(h1714_min)/sizeof(h1714_best); ++i)
        ((h1714_best *)h1714_min)[i].score = UINT64_MAX;
    h1714_inverse();
    for (uint64_t i = 0; i < count; ++i) {
        int region = i & 1;
        x80_t input;
        if (!region) input = (x80_t){0x3ffc, h1714_random() | (UINT64_C(1) << 63)};
        else {
            /* Stratified direct table sampling across both binades, capped
             * below reduction. This is not uniform in the reduced lattice. */
            uint64_t sig = h1714_random();
            input = (x80_t){(uint16_t)(0x3ffd + (sig & 1)),
                h1714_random() | (UINT64_C(1) << 63)};
            if (input.se == 0x3ffe && input.sig >= UINT64_C(0xc90fdaa22168c234))
                input.sig = UINT64_C(0x8000000000000000) +
                    input.sig % UINT64_C(0x490fdaa22168c234);
        }
        h1714_eval(input, 0);
        h1714_rank(input, region, 0); h1714_rank(input, region, 1);
        if (!region) for (int kind = 2; kind < 4; ++kind) {
            h1714_eval(input, kind); h1714_rank(input, region, kind);
        }
        if ((i + 1) % 100000 == 0) {
            fprintf(stderr, "SCAN %llu\n", (unsigned long long)(i + 1)); fflush(stderr);
        }
    }
    for (int region = 0; region < 2; ++region) for (int kind = 0; kind < (region ? 2 : 4); ++kind)
    for (int boundary = 0; boundary < 2; ++boundary) for (int rank = 0; rank < 2; ++rank) {
        h1714_best value = h1714_min[region][kind][boundary][rank];
        assert(value.sig);
        printf("%04x %016llx mined_%s %d %d %016llx\n", value.se,
            (unsigned long long)value.sig, boundary ? "half" : "integer", kind, region,
            (unsigned long long)value.score);
    }
    fprintf(stderr, "DONE software_operands=%llu\n", (unsigned long long)count);
    return 0;
}
