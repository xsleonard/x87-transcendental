/* Analysis-only exact neighborhoods of the four R1263 defining controls.
 * Enumerate positive-Horner coefficient plateaus, not captured labels.
 * The b1 window is the union of exact merged and unmerged equality windows;
 * b2 equality is possible only in the merged convention. Every external
 * candidate must pass independent current-source trace/endpoint validation.
 * H1576 is immutable evidence; its floor-sum construction is generalized here.
 */
#define H1469_NO_MAIN 1
#include "h1469_r1382_targeted_wrap.c"

static const u128 F_FIRST=(u128)1<<66;
static const u128 F_LAST=((u128)1<<67)-1;

static u128 positive_at(u128 f)
{
    fpv fourth={0,-75,f};
    fpv p=chain(fourth,C6_6,C6_4,C6_2);
    if(p.sign||p.e2!=-68)abort();
    return p.sig;
}

static void boundaries(u128 sample,u128 *first,u128 *last)
{
    u128 p=positive_at(sample),lo=F_FIRST,hi=sample;
    while(lo<hi) {
        u128 m=lo+((hi-lo)>>1);
        if(positive_at(m)<p)lo=m+1;else hi=m;
    }
    *first=lo;lo=sample;hi=F_LAST+1;
    while(lo<hi) {
        u128 m=lo+((hi-lo)>>1);
        if(m<=F_LAST&&positive_at(m)<=p)lo=m+1;else hi=m;
    }
    *last=lo-1;
}

static u128 floors(u128 n,u128 m,u128 a,u128 b)
{
    u128 result=0;
    for(;;) {
        if(a>=m){result+=(n-1)*n*(a/m)/2;a%=m;}
        if(b>=m){result+=n*(b/m);b%=m;}
        u128 top=a*n+b;
        if(top<m)return result;
        n=top/m;b=top%m;u128 old=m;m=a;a=old;
    }
}

static u128 prod_residue(u128 f,u128 p,unsigned shift)
{
    u256 v=mul128(f,p);
    return (((u128)v.w[1]<<64)|v.w[0])&(((u128)1<<shift)-1);
}

static u128 count_below(u128 a,u128 first,u128 last,unsigned shift,u128 limit)
{
    if(first>last||!limit)return 0;
    u128 n=last-first+1,m=(u128)1<<shift;
    if(limit>=m)return n;
    if(n>=((u128)1<<60))abort(); /* keep floor sums within u128 */
    u128 b=prod_residue(first,a,shift);
    return n-(floors(n,m,a,b+m-limit)-floors(n,m,a,b));
}

static void eq_window(unsigned shift,unsigned tap,u128 *lo,u128 *hi)
{
    u128 b=(u128)1<<(shift-16),target=(u128)1<<(16+tap-1);
    u128 v=target/3;
    /* b1: union [ceil(B/3),B); b2: merged [ceil(2B/3),B). */
    *lo=v*b+((target%3)*b+2)/3;
    *hi=v*b+b-1;
}

static u128 count_window(u128 a,u128 first,u128 last,unsigned shift,unsigned tap)
{
    u128 lo,hi;eq_window(shift,tap,&lo,&hi);
    return count_below(a,first,last,shift,hi+1)-count_below(a,first,last,shift,lo);
}

static u128 next_hit(u128 a,u128 first,u128 last,unsigned shift,unsigned tap)
{
    if(!count_window(a,first,last,shift,tap))return last+1;
    u128 lo=first,hi=last;
    while(lo<hi){u128 m=lo+((hi-lo)>>1);if(count_window(a,first,m,shift,tap))hi=m;else lo=m+1;}
    return lo;
}

static u128 fourth_of(u128 q)
{
    u256 p=mul128(q,q);
    return ((((u128)p.w[1]<<64)|p.w[0])>>67)|((u128)p.w[2]<<61);
}

static int invert(u128 fourth,uint64_t *external)
{
    u128 lo=F_FIRST,hi=F_LAST;
    while(lo<hi){u128 m=lo+((hi-lo)>>1);if(fourth_of(m)<fourth)lo=m+1;else hi=m;}
    return fourth_of(lo)==fourth&&external_preimage(lo,external);
}

static const uint64_t anchors[4]={UINT64_C(0xde4000000ec121bd),UINT64_C(0xe7400000015584c1),
                                UINT64_C(0xf9e0000000a5925b),UINT64_C(0xfcc0000003541b35)};

static int selftest_control(void)
{
    uint64_t state=UINT64_C(0x1583a4093822299f);
    for(unsigned j=0;j<400;++j) {
        unsigned tap=1+(j&1),shift=62+tap;
        u128 a=rng_next(&state)|1,lo,hi;eq_window(shift,tap,&lo,&hi);
        u128 first=F_FIRST+rng_next(&state);
        if(j%4==0){a=1;first=F_FIRST+lo-20;}
        if(j%4==1){a=1;first=F_FIRST+hi-20;}
        u128 last=first+100+rng_next(&state)%900,count=0,expected=last+1;
        for(u128 f=first;f<=last;++f){u128 r=prod_residue(f,a,shift);if(r>=lo&&r<=hi){if(!count)expected=f;++count;}}
        if(count!=count_window(a,first,last,shift,tap)||expected!=next_hit(a,first,last,shift,tap))return 1;
        u128 b=(u128)1<<(shift-16),target=(u128)1<<(shift+tap-1);
        for(u128 r=lo-2;r<=lo+2;++r) {
            int valid=(3*r-(3*r%b)==target)||(3*r-(2*r%b)-(r%b)==target);
            if(valid!=(r>=lo&&r<=hi))return 1;
        }
        for(u128 r=hi-2;r<=hi+2;++r) {
            int valid=(3*r-(3*r%b)==target)||(3*r-(2*r%b)-(r%b)==target);
            if(valid!=(r>=lo&&r<=hi))return 1;
        }
    }
    for(unsigned j=0;j<4;++j) {
        u128 q=(u128)anchors[j]*anchors[j]>>61;
        u128 f=fourth_of(q);uint64_t recovered=0;
        if(!invert(f,&recovered)||recovered!=anchors[j])return 1;
        unsigned tap=1+j/2,shift=62+tap;
        u128 lo,hi;eq_window(shift,tap,&lo,&hi);
        u128 r=prod_residue(f,positive_at(f),shift);
        if(r<lo||r>hi)return 1;
    }
    puts("SELFTEST: ok");return 0;
}

static uint64_t rows=0,hits=0,plateaus=0;
static void emit_plateau(unsigned anchor,int offset,u128 first,u128 last)
{
    unsigned tap=1+anchor/2,shift=62+tap;
    u128 p=positive_at(first);++plateaus;
    for(u128 f=next_hit(p,first,last,shift,tap);f<=last;f=next_hit(p,f+1,last,shift,tap)) {
        ++hits;uint64_t external=0;
        u256 product=mul128(f,p);
        if((unsigned)(bitlen256(&product)-67)==shift&&invert(f,&external)) {
            printf("3ffc %016" PRIx64 "\t%u\t%d\t%u\t67\t",external,anchor,offset,tap);
            print_u128_hex(f);putchar('\t');print_u128_hex(p);printf("\t%u\t",shift);
            print_u128_hex(prod_residue(f,p,shift));putchar('\n');++rows;
        }
        if(f==last)break;
    }
}

int main(int argc,char **argv)
{
    if(argc==2&&!strcmp(argv[1],"--selftest"))return selftest_control();
    if(argc!=2){fprintf(stderr,"usage: PLATEAU_RADIUS\n");return 2;}
    unsigned radius=(unsigned)strtoul(argv[1],0,0);
    if(radius>1000000)return 2;
    puts("operand\tanchor\tplateau_offset\ttap\ts4\tfourth\tpositive_proxy\trsh\trdisc_proxy");
    for(unsigned j=0;j<4;++j) {
        u128 q=(u128)anchors[j]*anchors[j]>>61,first,last;
        boundaries(fourth_of(q),&first,&last);emit_plateau(j,0,first,last);
        u128 left=first,right=last;
        for(unsigned k=1;k<=radius;++k) {
            if(left>F_FIRST){boundaries(left-1,&first,&last);emit_plateau(j,-(int)k,first,last);left=first;}
            if(right<F_LAST){boundaries(right+1,&first,&last);emit_plateau(j,(int)k,first,last);right=last;}
        }
    }
    fprintf(stderr,"plateau_radius=%u plateaus=%" PRIu64 " modular_hits=%" PRIu64 " external_rows=%" PRIu64 "\n",radius,plateaus,hits,rows);
    return 0;
}
