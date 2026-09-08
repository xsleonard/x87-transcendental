/* H1720: full-precision direct inputs, stratified by every polynomial binade.
 * No target instruction is executed: all evaluations use the C emulator.
 * Every proposed significand has nonzero low eleven bits, excluding the
 * binary64-representable domain of the earlier seed-based hardware loop. */
static uint64_t h1720_rng=UINT64_C(0x1720d5ca67a11c93);
static uint64_t h1720_random(void)
{
    h1720_rng^=h1720_rng<<13;h1720_rng^=h1720_rng>>7;h1720_rng^=h1720_rng<<17;
    return h1720_rng;
}
typedef struct {uint32_t score; uint64_t sig;} h1720_best;
static h1720_best h1720_bests[30][28];
int main(int argc,char **argv)
{
    assert(argc==2);uint64_t count=strtoull(argv[1],NULL,10);
    for(int b=0;b<30;b++)for(int j=0;j<28;j++)h1720_bests[b][j].score=UINT32_MAX;
    for(uint64_t i=0;i<count;i++) {
        int b=i%30;uint64_t sig=h1720_random()|UINT64_C(0x8000000000000000);
        if(!(sig&2047))sig|=1;
        h1720_rn=h1720_chop=h1720_final=0;
        for(int j=0;j<28;j++)h1720_score[j]=UINT32_MAX;
        x80_t in={(uint16_t)(16383-32+b),sig},s,c;
        assert(fsincos_ref(in,&s,&c,SF_RN)==FSINCOS_OK);
        assert(h1720_rn==11 && h1720_chop==13 && h1720_final==2);
        for(int j=0;j<28;j++)if(h1720_score[j]<h1720_bests[b][j].score)
            h1720_bests[b][j]=(h1720_best){h1720_score[j],sig};
        if((i+1)%1000000==0){fprintf(stderr,"SCAN %llu\n",(unsigned long long)(i+1));fflush(stderr);}
    }
    unsigned n=0;
    for(int b=0;b<30;b++)for(int j=0;j<28;j++)if(h1720_bests[b][j].sig) {
        printf("%04x %016llx %d %d %u\n",16383-32+b,
            (unsigned long long)h1720_bests[b][j].sig,b,j,h1720_bests[b][j].score);n++;
    }
    fprintf(stderr,"DONE software_operands=%llu proposals=%u\n",(unsigned long long)count,n);
}
