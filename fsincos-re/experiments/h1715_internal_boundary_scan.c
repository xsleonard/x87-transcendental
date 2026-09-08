/* H1715: passive probes for compound internal/final rounding challenges.
 * Inserted only in a software copy of the promoted C source. Fixed ranking
 * criteria choose tests, never runtime arithmetic or exception selectors. */
static uint32_t h1715_first, h1715_second, h1715_final;
static unsigned h1715_rn_events;
static uint32_t h1715_fraction(u256 a, int bits, int *discarded)
{
    if (a.hi >> 127) { a.lo=~a.lo+1; a.hi=~a.hi+(a.lo==0); }
    int width=a.hi ? 128+u128_width(a.hi) : u128_width(a.lo);
    int shift=width-bits;
    *discarded=shift>0;
    if (shift<=0) return 0;
    if (shift<32) return (uint32_t)(a.lo & (((u128)1<<shift)-1)) << (32-shift);
    shift-=32;
    u128 word=shift==0 ? a.lo : shift<128 ? (a.lo>>shift)|(a.hi<<(128-shift)) : a.hi>>(shift-128);
    return (uint32_t)word;
}

static void h1715_internal(u256 a, int bits, p5_round_t mode)
{
    if (bits!=64 || mode!=P5_ROUND_RN) return;
    int discarded; uint32_t fraction=h1715_fraction(a,bits,&discarded);
    if (!discarded || fraction==0) return;
    uint32_t half=UINT32_C(1)<<31;
    uint32_t distance=fraction>half ? fraction-half : half-fraction;
    h1715_rn_events++;
    if (distance<h1715_first) {h1715_second=h1715_first;h1715_first=distance;}
    else if (distance<h1715_second) h1715_second=distance;
}

static void h1715_endpoint(u256 a)
{
    int discarded;uint32_t fraction=h1715_fraction(a,64,&discarded);
    if (!discarded) return;
    uint32_t half=UINT32_C(1)<<31;
    uint32_t half_distance=fraction>half ? fraction-half : half-fraction;
    uint32_t endpoint_distance=fraction<half ? fraction : UINT32_MAX-fraction;
    uint32_t distance=half_distance<endpoint_distance ? half_distance : endpoint_distance;
    if (distance<h1715_final) h1715_final=distance;
}
