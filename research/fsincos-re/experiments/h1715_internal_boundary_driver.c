/* H1715 software-only compound-boundary proposal driver. */
static uint64_t h1715_rng=UINT64_C(0x1715c0111dea11ce);
static uint64_t h1715_random(void)
{
    h1715_rng^=h1715_rng<<13;h1715_rng^=h1715_rng>>7;h1715_rng^=h1715_rng<<17;
    return h1715_rng;
}
typedef struct {uint32_t score,first,second,final;uint16_t se;uint64_t sig;} h1715_best;
static h1715_best h1715_bests[37][3][2][2];

int main(int argc,char **argv)
{
    assert(argc==2);uint64_t count=strtoull(argv[1],NULL,10);
    for(unsigned i=0;i<sizeof(h1715_bests)/sizeof(h1715_best);i++)
        ((h1715_best *)h1715_bests)[i].score=UINT32_MAX;
    for(uint64_t i=0;i<count;i++) {
        int stratum=i%37;uint16_t se;uint64_t sig=h1715_random();
        if(stratum<30) {se=(uint16_t)(16383-32+stratum);sig|=UINT64_C(1)<<63;}
        else {
            int cell=stratum-30;
            se=(uint16_t)(cell<4 ? 0x3ffd : 0x3ffe);
            uint64_t lower=UINT64_C(0x8000000000000000)+(uint64_t)(cell<4 ? cell : cell-4)*(UINT64_C(1)<<61);
            uint64_t width=cell==6 ? UINT64_C(0x090fdaa22168c234) : UINT64_C(1)<<61;
            sig=lower+sig%width;
        }
        for(int instruction=0;instruction<3;instruction++) {
            h1715_first=h1715_second=h1715_final=UINT32_MAX;h1715_rn_events=0;
            x80_t in={se,sig},s,c;
            fsincos_status_t status=instruction==2 ? fsincos_ref(in,&s,&c,SF_RN) :
                general_standalone_ref(in,instruction,&s,SF_RN);
            assert(status==FSINCOS_OK && h1715_final!=UINT32_MAX);
            uint32_t score[]={h1715_second,h1715_first>h1715_final ? h1715_first : h1715_final};
            for(int category=0;category<2;category++) {
                h1715_best value={score[category],h1715_first,h1715_second,h1715_final,se,sig};
                for(int rank=0;rank<2;rank++) {
                    h1715_best *old=&h1715_bests[stratum][instruction][category][rank];
                    if(value.score<old->score) {h1715_best swap=*old;*old=value;value=swap;}
                }
            }
        }
        if((i+1)%100000==0) {fprintf(stderr,"SCAN %llu\n",(unsigned long long)(i+1));fflush(stderr);}
    }
    unsigned proposals=0;
    for(int b=0;b<37;b++)for(int instruction=0;instruction<3;instruction++)for(int c=0;c<2;c++)for(int r=0;r<2;r++) {
        h1715_best v=h1715_bests[b][instruction][c][r];
        /* Very small binades may have fewer than two nonidentity RN stages.
         * A missing compound event is recorded by omission, not a witness. */
        if(!v.sig) continue;
        printf("%04x %016llx %d %d %d %u %u %u %u\n",v.se,(unsigned long long)v.sig,
            b,instruction,c,v.score,v.first,v.second,v.final);proposals++;
    }
    fprintf(stderr,"DONE operands=%llu proposals=%u\n",(unsigned long long)count,proposals);
    return 0;
}
