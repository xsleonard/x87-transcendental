/* Analysis-only operation-role schedules. Never a deliverable selector.
 * Reuses the fixed candidate's exact arithmetic and architectural special
 * cases. Named global schedules are tested over every saved corpus row.
 * No native FPATAN or host transcendental function is executed.
 */
#define FPATAN_NO_MAIN
#include "fpatan_candidate.c"

static void short_constants(fpatan_context *ctx)
{
    const char *sigs[]={"555555555555535f0","6666666664208b016",
                        "492491e0653ac37b8","71b83f4133889b2f0"};
    const int scales[]={-68,-69,-69,-70};
    for(int i=0;i<4;i++){
        mpq_set_ui(ctx->rom[114+i],0,1);
        if(mpz_set_str(mpq_numref(ctx->rom[114+i]),sigs[i],16))abort();
        scale2(ctx->rom[114+i],ctx->rom[114+i],scales[i]);
        if(!(i&1))mpq_neg(ctx->rom[114+i],ctx->rom[114+i]);
    }
}

static int audit_finite(const fpatan_context *ctx,raw80 iy,raw80 ix,enum mode rc,
                        int policy,raw80 *out,int *c1,int *tiny)
{
    if(policy==0)return fpatan_candidate(ctx,iy,ix,rc,out,c1,tiny);
    mpq_t y,x,r,z,square,h,tail,angle,t,u,c,read;
    mpq_inits(y,x,r,z,square,h,tail,angle,t,u,c,read,NULL);
    decode(y,iy);decode(x,ix);mpq_abs(y,y);mpq_abs(x,x);
    int swap=mpq_cmp(y,x)>0;if(swap)mpq_swap(y,x);
    mpq_div(r,y,x);int n=0;
    if(qexp(r)<-40){rounded(angle,r,67,CHOP);}
    else{
        if(mpq_cmp_ui(r,3,64)<0){rounded(z,r,67,policy==6?RN:CHOP);}
        else{
            mpq_mul_2exp(t,r,5);mpq_set_ui(u,1,2);mpq_add(t,t,u);
            mpz_t index;mpz_init(index);
            mpz_fdiv_q(index,mpq_numref(t),mpq_denref(t));n=(int)mpz_get_ui(index);mpz_clear(index);
            if(n<1||n>32)abort();
            mpq_set_ui(c,(unsigned)n,32);mpq_canonicalize(c);
            /* Complete small-index products, matching the baseline. */
            mpq_mul(t,c,x);mpq_sub(t,y,t);rounded(t,t,67,CHOP);
            mpq_mul(u,c,y);mpq_add(u,x,u);rounded(u,u,67,CHOP);
            mpq_div(z,t,u);rounded(z,z,67,CHOP);
        }
        mpq_mul(square,z,z);rounded(square,square,67,CHOP);
        /* Public ROM has a four-term set and a six-term set. This branch
         * tests the natural short-table / long-direct role distinction.
         */
        int low=n?114:118,high=n?117:123;
        mpq_set(h,ctx->rom[high]);
        for(int k=high-1;k>=low;k--){
            mpq_mul(t,square,h);rounded(t,t,67,CHOP);
            mpq_add(h,ctx->rom[k],t);
            if(policy==5 && k==low)rounded(h,h,67,CHOP);
            else rounded(h,h,64,RN);
        }
        mpq_mul(t,square,h);
        rounded(t,t,(policy==4||policy>=7)?64:67,policy==8?RN:CHOP);
        mpq_set(read,z);
        if(policy==2 || policy==3)rounded(read,read,64,policy==2?RN:CHOP);
        if(policy>=7)rounded(read,read,64,policy==9?RN:CHOP);
        mpq_mul(tail,t,read);rounded(tail,tail,67,CHOP);
        mpq_add(angle,z,tail);
        if(n){rounded(angle,angle,67,CHOP);mpq_add(angle,angle,ctx->rom[124+n]);}
    }
    if(swap || (ix.se&0x8000))rounded(angle,angle,67,CHOP);
    if(swap){
        if(ix.se&0x8000)mpq_add(angle,ctx->rom[20],angle);
        else mpq_sub(angle,ctx->rom[20],angle);
    }else if(ix.se&0x8000)mpq_sub(angle,ctx->rom[19],angle);
    if(iy.se&0x8000)mpq_neg(angle,angle);
    *tiny=mpq_sgn(angle) && qexp(angle)<-16382;
    *out=encode(angle,rc,c1);
    mpq_clears(y,x,r,z,square,h,tail,angle,t,u,c,read,NULL);return 0;
}

static int audit_raw(const fpatan_context *ctx,raw80 y,raw80 x,enum mode rc,
                     int policy,raw80 *out,int *c1,unsigned *flags)
{
    enum operand_class ky=classify(y),kx=classify(x);
    int fy=ky==NORMAL || ky==DENORMAL || ky==PSEUDO;
    int fx=kx==NORMAL || kx==DENORMAL || kx==PSEUDO;
    if(!(fx&&fy))return fpatan_raw80(ctx,y,x,rc,out,c1,flags);
    int tiny=0,status=audit_finite(ctx,y,x,rc,policy,out,c1,&tiny);
    *flags=32U|(tiny?16U:0U)|((ky!=NORMAL||kx!=NORMAL)?2U:0U);
    return status;
}

int main(int argc,char **argv)
{
    /* 0 baseline; 1 short table; 2 RN64 tail-z read; 3 CHOP64 tail-z read;
     * 4 CHOP64 first tail product; 5 CHOP67 last Horner add;
     * 6 RN67 direct divider. Policies 2--6 also use the short table set.
     * D0009 follow-up: 7 both final-tail reads CHOP64; 8 first RN64/z CHOP64;
     * 9 first CHOP64/z RN64. These remain analysis-only coupled hypotheses.
     */
    if(argc!=2 || strlen(argv[1])!=1 || argv[1][0]<'0'||argv[1][0]>'9')return 2;
    int policy=argv[1][0]-'0';fpatan_context ctx;context_init(&ctx);short_constants(&ctx);
    char line[256],id[64],mode[4],extra;unsigned pc,ys,xs;uint64_t ym,xm;
    while(fgets(line,sizeof(line),stdin)){
        if(sscanf(line,"%63s %3s %u %x %" SCNx64 " %x %" SCNx64 " %c",id,mode,&pc,&ys,&ym,&xs,&xm,&extra)!=7 ||
           ys>65535||xs>65535||(pc!=24&&pc!=53&&pc!=64))return 2;
        enum mode rc;
        if(!strcmp(mode,"rn"))rc=RN;else if(!strcmp(mode,"rd"))rc=RD;
        else if(!strcmp(mode,"ru"))rc=RU;else if(!strcmp(mode,"rz"))rc=RZ;else return 2;
        raw80 y={(uint16_t)ys,ym},x={(uint16_t)xs,xm},out;int c1=0;unsigned flags=0;
        if(audit_raw(&ctx,y,x,rc,policy,&out,&c1,&flags))return 3;
        printf("%s %04x %016" PRIx64 " %d %02x 00\n",id,out.se,out.sig,c1,flags);
    }
    context_clear(&ctx);return ferror(stdin)||fflush(stdout)?3:0;
}
