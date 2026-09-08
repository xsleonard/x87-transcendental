/* Analysis-only adversarial input generator for the existing R1263 b1 gate.
 *
 * Unlike H1470's d0d0 hard-3x attachment surface, this uses a b1-equality
 * interval common to BOTH merge conventions and samples both fourth-product
 * binades.  At side=1, B=2^(rsh-16), v=floor(2^16/3)=21845.  For
 * R=v*B+u with B/2 <= u < ceil(2*B/3), both truncated 3R forms equal
 * 2^rsh exactly.  The window comes from integer arithmetic, not labels.
 *
 * Positive-Horner plateaus use H491's RN64 proxy.  Every external preimage
 * must be checked against current-source arithmetic and endpoints.  The
 * sampled plateau set is not exhaustive and a proxy mismatch is not a chip
 * result.  No x87 instruction executes in this generator.
 */
#define H1469_NO_MAIN 1
#include "h1469_r1382_targeted_wrap.c"

static const u128 WORD_FIRST = (u128)1 << 66;
static const u128 WORD_LAST = ((u128)1 << 67) - 1;

static u128 proxy_positive(u128 word, int exponent)
{
    fpv fourth = {0, exponent, word};
    fpv positive = chain(fourth, C6_6, C6_4, C6_2);
    if (positive.sign || positive.e2 != -68) abort();
    return positive.sig;
}

static void plateau(u128 sample, int exponent, u128 positive,
                    u128 *first, u128 *last)
{
    u128 lo = WORD_FIRST, hi = sample;
    while (lo < hi) {
        u128 mid = lo + ((hi-lo)>>1);
        if (proxy_positive(mid, exponent) < positive) lo = mid+1;
        else hi = mid;
    }
    *first = lo;
    lo = sample; hi = WORD_LAST+1;
    while (lo < hi) {
        u128 mid = lo + ((hi-lo)>>1);
        if (mid <= WORD_LAST && proxy_positive(mid, exponent) <= positive) lo = mid+1;
        else hi = mid;
    }
    *last = lo-1;
}

static u128 floor_sum(u128 n, u128 m, u128 a, u128 b)
{
    u128 answer = 0;
    for (;;) {
        if (a >= m) { answer += (n-1)*n*(a/m)/2; a %= m; }
        if (b >= m) { answer += n*(b/m); b %= m; }
        u128 top = a*n+b;
        if (top < m) return answer;
        n = top/m; b = top%m;
        u128 old = m; m = a; a = old;
    }
}

static u128 residue(u128 word, u128 positive, unsigned shift)
{
    u256 p = mul128(word, positive);
    u128 low = ((u128)p.w[1]<<64) | p.w[0];
    return low & (((u128)1<<shift)-1);
}

static u128 count_less(u128 a, u128 first, u128 last, unsigned shift, u128 limit)
{
    if (first > last || !limit) return 0;
    u128 n=last-first+1, m=(u128)1<<shift;
    if (limit >= m) return n;
    if (n >= ((u128)1<<60)) abort(); /* explicit arithmetic-width guard */
    u128 b=residue(first,a,shift);
    return n-(floor_sum(n,m,a,b+m-limit)-floor_sum(n,m,a,b));
}

static void window(unsigned shift, u128 *low, u128 *high)
{
    u128 block=(u128)1<<(shift-16);
    *low=21845*block+block/2;
    *high=21845*block+(2*block+2)/3-1;
}

static u128 hit_count(u128 a, u128 first, u128 last, unsigned shift)
{
    u128 low,high; window(shift,&low,&high);
    return count_less(a,first,last,shift,high+1)-count_less(a,first,last,shift,low);
}

static u128 first_hit(u128 a, u128 first, u128 last, unsigned shift)
{
    if (!hit_count(a,first,last,shift)) return last+1;
    u128 lo=first,hi=last;
    while (lo<hi) {
        u128 mid=lo+((hi-lo)>>1);
        if (hit_count(a,first,mid,shift)) hi=mid; else lo=mid+1;
    }
    return lo;
}

static u128 square_shifted(u128 square, unsigned shift)
{
    u256 product=mul128(square,square);
    /* square is 67 bits and the retained result is at most 68 bits here. */
    u128 lower=((u128)product.w[1]<<64)|product.w[0];
    return (lower>>shift)|((u128)product.w[2]<<(128-shift));
}

static int invert_fourth(u128 fourth, unsigned shift, u128 *square)
{
    u128 lo=WORD_FIRST,hi=WORD_LAST;
    while(lo<hi) {
        u128 mid=lo+((hi-lo)>>1);
        if(square_shifted(mid,shift)<fourth)lo=mid+1;else hi=mid;
    }
    if(square_shifted(lo,shift)!=fourth)return 0;
    *square=lo; return 1;
}

static int test_all(void)
{
    uint64_t state=UINT64_C(0x1576f00dcafe1234);
    for(unsigned test=0;test<400;++test) {
        unsigned shift=63+(test&1);
        u128 a=rng_next(&state)|1, first=WORD_FIRST+rng_next(&state);
        u128 lo,hi;window(shift,&lo,&hi);
        /* Deliberately include nonempty ranges; random narrow windows alone
         * can make an all-zero counter look correct at this event density. */
        if(test%4==0) { a=1; first=WORD_FIRST+lo-20; }
        if(test%4==1) { a=1; first=WORD_FIRST+hi-20; }
        u128 last=first+100+(rng_next(&state)%900);
        u128 count=0,expected=last+1;
        for(u128 x=first;x<=last;++x) {
            u128 r=residue(x,a,shift);
            if(r>=lo&&r<=hi) { if(!count)expected=x; ++count; }
        }
        if(count!=hit_count(a,first,last,shift)||expected!=first_hit(a,first,last,shift))return 1;
        u128 block=(u128)1<<(shift-16);
        for(u128 r=lo;r<=hi;r+=hi-lo?hi-lo:1) {
            u128 split=3*r-(2*r%block)-(r%block);
            u128 merged=3*r-(3*r%block);
            if(split!=((u128)1<<shift)||merged!=split)return 1;
            if(r==hi)break;
        }
    }
    for(unsigned s=66;s<=67;++s)for(unsigned j=0;j<100;++j) {
        u128 q=WORD_FIRST+((u128)(rng_next(&state)&3)<<64)+rng_next(&state);
        u128 f=square_shifted(q,s),back=0;
        if(f<WORD_FIRST||f>WORD_LAST)continue;
        if(!invert_fourth(f,s,&back)||back!=q)return 1;
    }
    puts("SELFTEST: ok");return 0;
}

int main(int argc,char **argv)
{
    if(argc==2&&!strcmp(argv[1],"--selftest"))return test_all();
    if(argc!=4) { fprintf(stderr,"usage: SAMPLES SEED MAX_EXTERNALS\n");return 2; }
    uint64_t samples=strtoull(argv[1],0,0),state=strtoull(argv[2],0,0),max=strtoull(argv[3],0,0);
    if(!samples||!state||!max)return 2;
    uint64_t hits=0,inverses=0,externals=0;
    puts("operand\ts4\tfourth\tpositive_proxy\trsh\trdisc_proxy\titeration");
    for(uint64_t i=0;i<samples;++i) {
        unsigned s4=66+(i&1);
        int exponent=-142+(int)s4;
        u128 sample=WORD_FIRST+((u128)(rng_next(&state)&3)<<64)+rng_next(&state);
        u128 positive=proxy_positive(sample,exponent),first,last;
        plateau(sample,exponent,positive,&first,&last);
        for(unsigned shift=63;shift<=64;++shift) {
            u128 f=first_hit(positive,first,last,shift);
            while(f<=last) {
                ++hits;
                u256 product=mul128(f,positive);
                if((unsigned)(bitlen256(&product)-67)==shift) {
                    u128 square;uint64_t external;
                    if(invert_fourth(f,s4,&square)) {
                        ++inverses;
                        if(external_preimage(square,&external)) {
                            printf("3ffc %016" PRIx64 "\t%u\t",external,s4); print_u128_hex(f);
                            putchar('\t');print_u128_hex(positive);printf("\t%u\t",shift);
                            print_u128_hex(residue(f,positive,shift));printf("\t%" PRIu64 "\n",i);
                            if(++externals>=max)goto done;
                        }
                    }
                }
                if(f==last)break;
                f=first_hit(positive,f+1,last,shift);
            }
        }
    }
done:
    fprintf(stderr,"samples_limit=%" PRIu64 " raw_hits=%" PRIu64 " square_preimages=%" PRIu64 " external_rows=%" PRIu64 "\n",samples,hits,inverses,externals);
    return 0;
}
