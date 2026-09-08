/* H1720: passive, software-only ranking of individual policy-2 cuts.
 * Slot numbers are execution-order identities, not fitted selectors. The
 * promoted source is copied for instrumentation and is never edited here.
 * Ranking keys truncate distances to 32 fractional bits; they are proposal
 * heuristics, not claims of exact ties or of silicon implementation details. */
static uint32_t h1720_score[28];
static unsigned h1720_rn, h1720_chop, h1720_final;
static void h1720_internal(u256 a, int bits, p5_round_t mode)
{
    unsigned slot;
    if (bits==64 && mode==P5_ROUND_RN) slot=h1720_rn++;
    else if (bits==67 && mode==P5_ROUND_CHOP) slot=11+h1720_chop++;
    else return;
    assert(slot<24);
    int discarded; uint32_t f=h1715_fraction(a,bits,&discarded);
    if (!discarded) return;
    uint32_t half=UINT32_C(1)<<31;
    h1720_score[slot]=mode==P5_ROUND_RN ? (f>half ? f-half : half-f) :
        (f<half ? f : UINT32_MAX-f);
}
static void h1720_endpoint(u256 a)
{
    unsigned slot=24+2*h1720_final++; assert(slot<28);
    int discarded; uint32_t f=h1715_fraction(a,64,&discarded);
    if (!discarded) return;
    uint32_t half=UINT32_C(1)<<31;
    h1720_score[slot]=f>half ? f-half : half-f;
    h1720_score[slot+1]=f<half ? f : UINT32_MAX-f;
}
