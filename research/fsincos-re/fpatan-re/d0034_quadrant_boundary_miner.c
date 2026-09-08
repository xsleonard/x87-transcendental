/* Software-only adversarial search through the unchanged numerical C.
 * Mine each restored quadrant independently. The ordered endpoint is
 * (positive raw result, 1-C1), so RN C1-only transitions are included.
 * Bisection preserves a local predicate bracket; global monotonicity is
 * neither required nor claimed. All nine neighboring raw operands survive
 * for independent verification, including any local reversals.
 */
#define FPATAN_NO_MAIN
#include "fpatan_candidate.c"

typedef struct {
    raw80 value;
    int c1;
} endpoint;

static uint64_t mining_state = UINT64_C(0xd03420260906c1c1);

static uint64_t random_word(void)
{
    uint64_t z = (mining_state += UINT64_C(0x9e3779b97f4a7c15));
    z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
    return z ^ (z >> 31);
}

static endpoint evaluate(const fpatan_context *ctx, raw80 a, raw80 b, unsigned quadrant, enum mode rc)
{
    raw80 y = quadrant < 2 ? a : b;
    raw80 x = quadrant < 2 ? b : a;
    if (quadrant & 1)
        x.se |= 0x8000;
    endpoint answer;
    unsigned flags;
    if (fpatan_raw80(ctx, y, x, rc, &answer.value, &answer.c1, &flags))
        abort();
    if (answer.value.se & 0x8000 || (answer.value.se & 0x7fff) == 0x7fff || flags != 32)
        abort();
    return answer;
}

static int compare(endpoint a, endpoint b)
{
    if (a.value.se != b.value.se)
        return a.value.se > b.value.se ? 1 : -1;
    if (a.value.sig != b.value.sig)
        return a.value.sig > b.value.sig ? 1 : -1;
    return b.c1 - a.c1;
}

static raw80 neighbor(raw80 a, int offset)
{
    while (offset < 0) {
        if (a.sig == (UINT64_C(1) << 63)) {
            a.se--;
            a.sig = UINT64_MAX;
        } else {
            a.sig--;
        }
        offset++;
    }
    while (offset > 0) {
        if (a.sig == UINT64_MAX) {
            a.se++;
            a.sig = UINT64_C(1) << 63;
        } else {
            a.sig++;
        }
        offset--;
    }
    if (!a.se || a.se >= 0x7fff)
        abort();
    return a;
}

int main(void)
{
    fpatan_context ctx;
    context_init(&ctx);
    mpq_t ratio, temporary, bvalue;
    mpq_inits(ratio, temporary, bvalue, NULL);
    unsigned seeds = 0, rows = 0, flat_low = 0, unbracketed_high = 0;
    const uint64_t first = UINT64_C(1) << 63;
    const unsigned exponents[] = {5, 6, 8, 12, 20, 33, 39, 40, 41, 60, 62, 63, 64, 65, 66, 70};
    for (unsigned i = 0; i < 4096; i++) {
        unsigned quadrant = i % 4;
        unsigned family = (i / 4) % 2;
        enum mode rc = (i / 8) % 2 ? RD : RN;
        unsigned within = i / 16;
        int direction = quadrant == 0 || quadrant == 3 ? 1 : -1;
        raw80 b = {0x3fff, random_word() | first}, a;
        if (!family) {
            unsigned difference = exponents[within % (sizeof(exponents) / sizeof(exponents[0]))];
            a = (raw80){(uint16_t)(0x3fff - difference), random_word() | first};
        } else {
            unsigned cell = 2 + within % 31;
            mpq_set_ui(ratio, 2 * cell - 1, 64);
            uint64_t fraction = random_word();
            mpz_import(mpq_numref(temporary), 1, 1, sizeof(fraction), 0, 0, &fraction);
            mpz_set_ui(mpq_denref(temporary), 1);
            mpq_div_2exp(temporary, temporary, cell == 32 ? 70 : 69);
            mpq_add(ratio, ratio, temporary);
            decode(bvalue, b);
            mpq_mul(temporary, ratio, bvalue);
            int ignored;
            a = encode(temporary, RN, &ignored);
        }
        endpoint target = evaluate(&ctx, a, b, quadrant, rc);
        uint64_t lo = first, hi = a.se == b.se ? b.sig : UINT64_MAX;
        if (a.se > b.se || a.sig < lo || a.sig > hi)
            abort();
        endpoint left = evaluate(&ctx, (raw80){a.se, lo}, b, quadrant, rc);
        endpoint right = evaluate(&ctx, (raw80){a.se, hi}, b, quadrant, rc);
        if (direction * compare(left, target) >= 0) {
            flat_low++;
            continue;
        }
        if (direction * compare(right, target) < 0) {
            unbracketed_high++;
            continue;
        }
        while (hi - lo > 1) {
            uint64_t middle = lo + ((hi - lo) >> 1);
            endpoint value = evaluate(&ctx, (raw80){a.se, middle}, b, quadrant, rc);
            if (direction * compare(value, target) >= 0)
                hi = middle;
            else
                lo = middle;
        }
        raw80 crossing = {a.se, hi};
        left = evaluate(&ctx, neighbor(crossing, -1), b, quadrant, rc);
        right = evaluate(&ctx, crossing, b, quadrant, rc);
        if (direction * compare(left, target) >= 0 || direction * compare(right, target) < 0)
            abort();
        for (int offset = -4; offset <= 4; offset++) {
            raw80 adjacent = neighbor(crossing, offset);
            endpoint value = evaluate(&ctx, adjacent, b, quadrant, rc);
            printf("%u %u %u %s %d %04x %016" PRIx64 " %04x %016" PRIx64
                   " %04x %016" PRIx64 " %d\n", i, family, quadrant,
                   rc == RN ? "rn" : "rd", offset, adjacent.se, adjacent.sig,
                   b.se, b.sig, value.value.se, value.value.sig, value.c1);
            rows++;
        }
        seeds++;
    }
    fprintf(stderr, "{\"attempts\":4096,\"seeds\":%u,\"rows\":%u,\"flat_low\":%u,"
                    "\"unbracketed_high\":%u,\"hardware_executed\":false}\n",
            seeds, rows, flat_low, unbracketed_high);
    mpq_clears(ratio, temporary, bvalue, NULL);
    context_clear(&ctx);
    return ferror(stdout) ? 1 : 0;
}
