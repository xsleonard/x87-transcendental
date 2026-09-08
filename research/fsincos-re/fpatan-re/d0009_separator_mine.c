/* Pure software, label-free search for externally representable pairs that
 * distinguish frozen arithmetic schedules. No native FPATAN is present.
 * All candidates are compared in RN including C1; selected pairs will be
 * captured in all four RC modes after the independent history audit.
 */
#define main schedule_audit_main
#include "d0008_schedule_audit.c"
#undef main

static uint64_t state=UINT64_C(0x46504154414e4439);
static uint64_t next_word(void)
{
    state^=state>>12;state^=state<<25;state^=state>>27;
    return state*UINT64_C(2685821657736338717);
}

int main(int argc,char **argv)
{
    if(argc!=2)return 2;
    char *end;uint64_t count=strtoull(argv[1],&end,10);if(*end||!count)return 2;
    fpatan_context ctx;context_init(&ctx);short_constants(&ctx);
    uint64_t kept=0;
    for(uint64_t i=0;i<count;i++){
        raw80 x={0x3fff,next_word()|(UINT64_C(1)<<63)};
        /* Half the bank covers table cells, half direct significands.
         * Direct samples deliberately emphasize the larger non-tiny ratios
         * where differing tail reads can reach the final rounding boundary.
         */
        raw80 y={(uint16_t)(i&1?0x3ffa - (i%3):0x3ffe - (i%4)),next_word()|(UINT64_C(1)<<63)};
        raw80 ref;int ref_c1,tiny;unsigned mask=0;
        if(audit_finite(&ctx,y,x,RN,3,&ref,&ref_c1,&tiny))abort();
        for(int p=0;p<=5;p++)if(p!=3){
            raw80 out;int c1;
            if(audit_finite(&ctx,y,x,RN,p,&out,&c1,&tiny))abort();
            if(out.se!=ref.se||out.sig!=ref.sig||c1!=ref_c1)mask|=1U<<p;
        }
        if(mask){
            printf("%04x %016" PRIx64 " %04x %016" PRIx64 " %02x\n",y.se,y.sig,x.se,x.sig,mask);kept++;
            if(fflush(stdout))return 3;
        }
        if((i+1)%UINT64_C(262144)==0)fprintf(stderr,"scanned=%" PRIu64 " separators=%" PRIu64 "\n",i+1,kept);
    }
    fprintf(stderr,"COMPLETE scanned=%" PRIu64 " separators=%" PRIu64 "\n",count,kept);
    context_clear(&ctx);return fflush(stdout)?3:0;
}
