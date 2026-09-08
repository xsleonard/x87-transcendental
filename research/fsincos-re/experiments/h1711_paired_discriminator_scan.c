/* H1711 software-only search. Included after the pinned H1710 program.
 * These are proposal operands, never fitted branches in the candidate.
 * Compare internal factors first so ordinary agreement needs no final store.
 */
static uint64_t h1711_rng = UINT64_C(0x1711710cafef00d);
static uint64_t h1711_random(void)
{
    h1711_rng ^= h1711_rng << 13;
    h1711_rng ^= h1711_rng >> 7;
    h1711_rng ^= h1711_rng << 17;
    return h1711_rng;
}

static int h1711_same(wv_t a, wv_t b)
{
    return a.sign == b.sign && a.e2 == b.e2 && a.sig == b.sig;
}

static wv_t h1711_step(wv_t p, wv_t square, const p5c_t *c, int cut)
{
    return cut ? h1630_add(p5_wv_mul_round(p, square, 67, P5_ROUND_CHOP),
        h1630_literal(c), 64, P5_ROUND_RN) : h1710_fma_rn64(p, square, c);
}

static unsigned h1711_check(uint16_t se, uint64_t sig)
{
    static const p5c_t *const sine[] = {&P5S6_1, &P5S6_2, &P5S6_3,
        &P5S6_4, &P5S6_5, &P5S6_6};
    static const p5c_t *const cosine[] = {&P5C6_1, &P5C6_2, &P5C6_3,
        &P5C6_4, &P5C6_5, &P5C6_6};
    wv_t r = {0, (int)se - 16383 - 63, sig, 0};
    wv_t square = p5_wv_mul_round(r, r, 67, P5_ROUND_CHOP);
    wv_t p[3], q[2];
    p[0] = p[2] = h1630_literal(sine[5]);
    q[0] = q[1] = h1630_literal(cosine[5]);
    for (int i = 4; i >= 1; --i) {
        p[0] = h1711_step(p[0], square, sine[i], 0);
        p[2] = h1711_step(p[2], square, sine[i], 1);
        q[0] = h1711_step(q[0], square, cosine[i], 0);
        q[1] = h1711_step(q[1], square, cosine[i], 1);
    }
    p[1] = h1711_step(p[0], square, sine[0], 1);
    p[0] = h1711_step(p[0], square, sine[0], 0);
    p[2] = h1711_step(p[2], square, sine[0], 1);
    for (int i = 0; i < 2; ++i) q[i] = h1711_step(q[i], square, cosine[0], 1);
    unsigned changed = (!h1711_same(p[0], p[1])) |
        ((!h1711_same(p[1], p[2]) || !h1711_same(q[0], q[1])) << 1);
    if (!changed) return 0;
    wv_t st[3], ct[2];
    for (int i = 0; i < 3; ++i)
        st[i] = p5_wv_mul_round(p5_wv_mul_round(p[i], square, 64, P5_ROUND_RN),
            r, 67, P5_ROUND_CHOP);
    for (int i = 0; i < 2; ++i) ct[i] = p5_wv_mul_round(q[i], square, 67, P5_ROUND_CHOP);
    unsigned result = 0;
    /* RN and RZ cover positive direct directed endpoints; signed/quadrant
     * transfers are independently replayed in the proposal builder. C1 is
     * compared on both internal lanes for possible odd-quadrant transport. */
    for (int mode = 0; mode < 2; ++mode) {
        sf_rc_t rc = mode ? SF_RZ : SF_RN;
        for (int lane = 0; lane < 2; ++lane) {
            x80_t value[3]; int c1[3];
            for (int i = 0; i < 3; ++i) {
                wv_t lead = lane ? (wv_t){0, 0, 1, 0} : r;
                sf_t v = h1710_final(lead, lane ? ct[i == 2] : st[i], 0, rc, &c1[i]);
                sf_to_x87(&v, &value[i].se, &value[i].sig);
            }
            for (int i = 0; i < 2; ++i)
                if (value[i].se != value[i+1].se || value[i].sig != value[i+1].sig || c1[i] != c1[i+1])
                    result |= 1u << i;
        }
    }
    return result;
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    uint64_t count = strtoull(argv[1], NULL, 10), totals[4] = {0,0,0,0};
    const uint64_t anchors[] = {UINT64_C(0xc060000000d78237), UINT64_C(0xb400000004ea29f8)};
    for (uint64_t i = 0; i < count; ++i) {
        uint16_t se; uint64_t sig;
        if (i < 32768) {
            se = 0x3ffc; sig = anchors[i / 16384] + (i % 16384) - 8192;
        } else {
            uint64_t v = h1711_random();
            se = (i % 8) ? 0x3ffc : (uint16_t)(0x3ffc - ((v >> 59) % 30));
            sig = h1711_random() | (UINT64_C(1) << 63);
        }
        unsigned mask = h1711_check(se, sig); totals[mask]++;
        if (mask) printf("%04x %016llx %u\n", se, (unsigned long long)sig, mask);
        if ((i+1) % 1000000 == 0) {
            fprintf(stderr, "SEARCH %llu %llu %llu %llu\n", (unsigned long long)(i+1),
                (unsigned long long)totals[1], (unsigned long long)totals[2], (unsigned long long)totals[3]);
            fflush(stderr); fflush(stdout);
        }
    }
    fprintf(stderr, "DONE %llu %llu %llu %llu\n", (unsigned long long)count,
        (unsigned long long)totals[1], (unsigned long long)totals[2], (unsigned long long)totals[3]);
    return 0;
}
