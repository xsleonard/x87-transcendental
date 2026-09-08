/* Local software-only transition mining. No native FPATAN or host atan.
 * Search the unchanged V7 model for adjacent external significands whose
 * RN or RD output crosses a selected encoded value. Retain both sides and
 * neighbors. This is input selection, not a claim of global monotonicity.
 */
#define FPATAN_NO_MAIN
#include "fpatan_candidate_v7.c"

static uint64_t mining_state=UINT64_C(0xd02620260905a7a7);
static uint64_t random_word(void)
{
    uint64_t z=(mining_state+=UINT64_C(0x9e3779b97f4a7c15));
    z=(z^(z>>30))*UINT64_C(0xbf58476d1ce4e5b9);
    z=(z^(z>>27))*UINT64_C(0x94d049bb133111eb);
    return z^(z>>31);
}

static raw80 evaluate(const fpatan_context *ctx,raw80 y,raw80 x,enum mode rc)
{
    raw80 out;int c1;unsigned flags;
    if(fpatan_raw80(ctx,y,x,rc,&out,&c1,&flags))abort();
    if(out.se&0x8000 || (out.se&0x7fff)==0x7fff || flags!=32)abort();
    return out;
}

static int compare(raw80 a,raw80 b)
{
    if(a.se!=b.se)return a.se>b.se?1:-1;
    return a.sig>b.sig?1:a.sig<b.sig?-1:0;
}

int main(void)
{
    fpatan_context ctx;context_init(&ctx);
    mpq_t r,t,xvalue;mpq_inits(r,t,xvalue,NULL);
    unsigned seeds=0,rows=0,skipped=0;
    const uint64_t first=UINT64_C(1)<<63;
    for(unsigned i=0;i<2048;i++){
        raw80 x={0x3fff,random_word()|first},y;
        unsigned family=i&1;
        enum mode rc=(i&2)?RD:RN;
        if(!family){
            unsigned difference=5+(unsigned)(random_word()%38);
            y=(raw80){(uint16_t)(0x3fff-difference),random_word()|first};
        }else{
            unsigned n=2+(i/2)%31;
            mpq_set_ui(r,2*n-1,64);
            uint64_t random=random_word();
            mpz_import(mpq_numref(t),1,1,sizeof(random),0,0,&random);
            mpz_set_ui(mpq_denref(t),1);mpq_div_2exp(t,t,n==32?70:69);
            mpq_add(r,r,t);decode(xvalue,x);mpq_mul(t,r,xvalue);
            int c1;y=encode(t,RN,&c1);
        }
        raw80 target=evaluate(&ctx,y,x,rc);
        uint64_t lo=first,hi=UINT64_MAX;
        if(compare(evaluate(&ctx,(raw80){y.se,lo},x,rc),target)>=0){skipped++;continue;}
        if(compare(evaluate(&ctx,(raw80){y.se,hi},x,rc),target)<0)abort();
        while(lo<hi){
            uint64_t mid=lo+((hi-lo)>>1);
            if(compare(evaluate(&ctx,(raw80){y.se,mid},x,rc),target)>=0)hi=mid;
            else lo=mid+1;
        }
        if(lo<=first+2 || lo>=UINT64_MAX-2){skipped++;continue;}
        raw80 below=evaluate(&ctx,(raw80){y.se,lo-1},x,rc);
        raw80 above=evaluate(&ctx,(raw80){y.se,lo},x,rc);
        if(compare(below,target)>=0 || compare(above,target)<0)abort();
        for(int delta=-2;delta<=2;delta++){
            uint64_t significand=delta<0?lo-(unsigned)(-delta):lo+(unsigned)delta;
            printf("%u %u %s %d %04x %016" PRIx64 " %04x %016" PRIx64 "\n",
                i,family,rc==RN?"rn":"rd",delta,y.se,significand,x.se,x.sig);
            rows++;
        }
        seeds++;
    }
    fprintf(stderr,"{\"seeds\":%u,\"rows\":%u,\"skipped\":%u,\"hardware_executed\":false}\n",seeds,rows,skipped);
    mpq_clears(r,t,xvalue,NULL);context_clear(&ctx);
    return ferror(stdout)?1:0;
}
