/* V7 ANALYSIS-ONLY, NOT PROMOTED. Global nearest/lower-tie index candidate.
 * D0022 rejected V6's upper-cell tie at ratio 19/64. This uses one general
 * index rule, with index < 2 taking the direct branch, including at 3/64.
 * A fresh frozen midpoint challenge is required before accepting this rule.
 * The V6/V4 history below is retained, not a claim of V7 validation.
 */
/* V6 ANALYSIS-ONLY, NOT PROMOTED. D0021 Goldmont-shaped split polynomial.
 * Self-contained local C candidate. No algorithm-selection flags or ledger.
 * The inherited V4 history below describes the baseline, not V6 validation.
 * Full saved-corpus and prospective acceptance are separate requirements.
 */
/* Analysis-only C FPATAN candidate, NOT promoted or claimed complete.
 * Exact rational arithmetic uses GMP; no host atan, FPATAN, float or double.
 * Public P5 ROM constants are from Ken Shirriff's physical decode (2025).
 * Finite graph_v4.PROGRAM passed the fresh D0004 campaign. Architectural
 * values/C1 passed D0005/6; DE for pseudo-denormals passed D0006. Tininess
 * before final rounding is D0006's discovery correction for exception flags.
 * Broad fresh adversarial verification and final delivery are still pending.
 * Build: cc -O2 -std=c11 -Wall -Wextra -Werror fpatan_candidate.c -lgmp
 * Input uses the local public two-operand protocol. Output fields are
 * id, result_se, result_significand, C1, exception_flags, pre_load_flags.
 * PC is accepted as metadata, not an internal precision selection switch.
 */
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <gmp.h>

enum mode { RN=0, RD=1, RU=2, RZ=3, CHOP=4 };
typedef struct { uint16_t se; uint64_t sig; } raw80;
typedef struct { mpq_t rom[157]; } fpatan_context;
static const struct { int index,sign,scale; const char *sig; } constants[] = {
{19, 0, -65, "6487ed5110b4611a6"},
    {20, 0, -66, "6487ed5110b4611a6"},
    {114, 1, -68, "555555555555535f0"},
    {115, 0, -69, "6666666664208b016"},
    {116, 1, -69, "492491e0653ac37b8"},
    {117, 0, -70, "71b83f4133889b2f0"},
    {118, 1, -68, "55555555555555543"},
    {119, 0, -69, "66666666666616b73"},
    {120, 1, -69, "4924924920fca4493"},
    {121, 0, -70, "71c71c4be6f662c91"},
    {122, 1, -70, "5d16e0bde0b12eee8"},
    {123, 0, -70, "4e403be3e3c725aa0"},
    {125, 0, -72, "7ff556eea5d892a14"},
    {126, 0, -71, "7fd56edcb3f7a71b6"},
    {127, 0, -70, "5fb860980bc43a305"},
    {128, 0, -70, "7f56ea6ab0bdb7196"},
    {129, 0, -69, "4f5bbba31989b161a"},
    {130, 0, -69, "5ee5ed2f396c089a4"},
    {131, 0, -69, "6e435d4a498288118"},
    {132, 0, -69, "7d6dd7e4b203758ab"},
    {133, 0, -68, "462fd68c2fc5e0986"},
    {134, 0, -68, "4d89dcdc1faf2f34e"},
    {135, 0, -68, "54c2b6654735276d5"},
    {136, 0, -68, "5bd86507937bc239c"},
    {137, 0, -68, "62c934e5286c95b6d"},
    {138, 0, -68, "6993bb0f308ff2db2"},
    {139, 0, -68, "7036d3253b27be33e"},
    {140, 0, -68, "76b19c1586ed3da2b"},
    {141, 0, -68, "7d03742d50505f2e3"},
    {142, 0, -67, "4195fa536cc33f152"},
    {143, 0, -67, "4495766fef4aa3da8"},
    {144, 0, -67, "47802eaf7bfacfcdb"},
    {145, 0, -67, "4a563964c238c37b1"},
    {146, 0, -67, "4d17c07338deed102"},
    {147, 0, -67, "4fc4fee27a5bd0f68"},
    {148, 0, -67, "525e3e8c9a7b84921"},
    {149, 0, -67, "54e3d5ee24187ae45"},
    {150, 0, -67, "5756261c5a6c60401"},
    {151, 0, -67, "59b598e48f821b48b"},
    {152, 0, -67, "5c029f15e118cf39e"},
    {153, 0, -67, "5e3daef574c579407"},
    {154, 0, -67, "606742dc562933204"},
    {155, 0, -67, "627fd7fd5fc7deaa4"},
    {156, 0, -67, "6487ed5110b4611a6"},
};

/* All scaling here is exact; exponent fields are never host FP exponents. */
static void scale2(mpq_t out,const mpq_t in,int scale)
{
    if(scale>=0) mpq_mul_2exp(out,in,(unsigned)scale);
    else mpq_div_2exp(out,in,(unsigned)-scale);
}
static int qexp(const mpq_t in)
{
    mpz_t n,d;mpz_inits(n,d,NULL);mpz_abs(n,mpq_numref(in));mpz_set(d,mpq_denref(in));
    int e=(int)mpz_sizeinbase(n,2)-(int)mpz_sizeinbase(d,2);
    if(e>=0) mpz_mul_2exp(d,d,(unsigned)e);else mpz_mul_2exp(n,n,(unsigned)-e);
    if(mpz_cmp(n,d)<0)e--;
    mpz_clears(n,d,NULL);return e;
}
static int increment(const mpz_t q,const mpz_t r,const mpz_t d,int negative,enum mode mode)
{
    if(!mpz_sgn(r))return 0;
    if(mode==RD)return negative;
    if(mode==RU)return !negative;
    if(mode!=RN)return 0;
    mpz_t twice;mpz_init(twice);mpz_mul_2exp(twice,r,1);
    int cmp=mpz_cmp(twice,d);mpz_clear(twice);
    return cmp>0 || (cmp==0 && mpz_odd_p(q));
}
static void at_step(mpq_t out,const mpq_t in,int scale,enum mode mode)
{
    int negative=mpq_sgn(in)<0;
    mpz_t n,d,q,r;mpz_inits(n,d,q,r,NULL);
    mpz_abs(n,mpq_numref(in));mpz_set(d,mpq_denref(in));
    if(scale<0)mpz_mul_2exp(n,n,(unsigned)-scale);else mpz_mul_2exp(d,d,(unsigned)scale);
    mpz_fdiv_qr(q,r,n,d);
    if(increment(q,r,d,negative,mode))mpz_add_ui(q,q,1);
    if(negative)mpz_neg(q,q);
    mpq_set_z(out,q);scale2(out,out,scale);
    mpz_clears(n,d,q,r,NULL);
}
static void rounded(mpq_t out,const mpq_t in,int bits,enum mode mode)
{
    if(!mpq_sgn(in)){mpq_set_ui(out,0,1);return;}
    at_step(out,in,qexp(in)-bits+1,mode);
}
static void decode(mpq_t out,raw80 in)
{
    mpz_import(mpq_numref(out),1,1,sizeof(in.sig),0,0,&in.sig);
    mpz_set_ui(mpq_denref(out),1);
    scale2(out,out,((in.se&0x7fff)?(in.se&0x7fff):1)-16383-63);
    if(in.se&0x8000)mpq_neg(out,out);
}
static raw80 encode(const mpq_t in,enum mode mode,int *c1)
{
    raw80 out={0,0};int sign=mpq_sgn(in)<0;mpq_t q,a,b;
    mpq_inits(q,a,b,NULL);
    int e=mpq_sgn(in)?qexp(in):-16382;if(e<-16382)e=-16382;
    at_step(q,in,e-63,mode);mpq_abs(a,q);mpq_abs(b,in);*c1=mpq_cmp(a,b)>0;
    if(mpq_sgn(q)){
        e=qexp(q);if(e<-16382)e=-16382;
        scale2(a,a,63-e);
        if(mpz_cmp_ui(mpq_denref(a),1))abort();
        if(mpz_sizeinbase(mpq_numref(a),2)>64)abort();
        size_t count=0;mpz_export(&out.sig,&count,1,sizeof(out.sig),0,0,mpq_numref(a));
        if(count>1)abort();
    }
    out.se=(uint16_t)((sign<<15)|(out.sig<(UINT64_C(1)<<63)?0:e+16383));
    mpq_clears(q,a,b,NULL);return out;
}
static void context_init(fpatan_context *ctx)
{
    for(int i=0;i<157;i++)mpq_init(ctx->rom[i]);
    for(size_t i=0;i<sizeof(constants)/sizeof(constants[0]);i++){
        int k=constants[i].index;
        if(mpz_set_str(mpq_numref(ctx->rom[k]),constants[i].sig,16))abort();
        if(constants[i].sign)mpq_neg(ctx->rom[k],ctx->rom[k]);
        scale2(ctx->rom[k],ctx->rom[k],constants[i].scale);
    }
}
static void context_clear(fpatan_context *ctx)
{
    for(int i=0;i<157;i++)mpq_clear(ctx->rom[i]);
}

/* A single global numerical graph, no operand ledger or fitted exceptions.
 * Nonzero finite normal/subnormal values only until the specials campaign.
 */
static int fpatan_candidate(const fpatan_context *ctx,raw80 iy,raw80 ix,enum mode rc,raw80 *out,int *c1,int *tiny)
{
    if(!iy.sig || !ix.sig || (iy.se&0x7fff)==0x7fff || (ix.se&0x7fff)==0x7fff ||
       ((iy.se&0x7fff)&&!(iy.sig>>63)) || ((ix.se&0x7fff)&&!(ix.sig>>63)))return 2;
    mpq_t y,x,r,z,square,h,tail,angle,t,u,c,v,odd,even;
    mpq_inits(y,x,r,z,square,h,tail,angle,t,u,c,v,odd,even,NULL);
    decode(y,iy);decode(x,ix);mpq_abs(y,y);mpq_abs(x,x);
    int swap=mpq_cmp(y,x)>0;if(swap)mpq_swap(y,x);
    mpq_div(r,y,x);int n=0;
    if(qexp(r)<-40){
        rounded(angle,r,67,CHOP);
    }else{
        if(mpq_cmp_ui(r,3,64)<=0){
            rounded(z,r,67,CHOP);
        }else{
            /* Nearest table index with ties to the lower cell; hypothesis V7. */
            mpq_mul_2exp(t,r,5);mpq_set_ui(u,1,2);mpq_sub(t,t,u);
            mpz_t index;mpz_init(index);
            mpz_cdiv_q(index,mpq_numref(t),mpq_denref(t));n=(int)mpz_get_ui(index);mpz_clear(index);
            if(n<1||n>32)abort();
            mpq_set_ui(c,(unsigned)n,32);mpq_canonicalize(c);
            /* These small-integer products are COMPLETE before subtraction. */
            mpq_mul(t,c,x);mpq_sub(t,y,t);rounded(t,t,67,CHOP);
            mpq_mul(u,c,y);mpq_add(u,x,u);rounded(u,u,67,CHOP);
            mpq_div(z,t,u);rounded(z,z,67,CHOP);
        }
        /* D0021: source-guided interleaved Goldmont-shaped operation roles.
         * Special square is X67/Y64 RN64; ordinary products are CHOP67.
         * 0x649-shaped sums are RN64, 0x6c9-shaped sums are CHOP67.
         * These numerical meanings on Skylake remain a candidate, not a
         * decoded assertion about Goldmont's hidden arithmetic semantics.
         */
        rounded(t,z,64,CHOP);mpq_mul(square,z,t);rounded(square,square,64,RN);
        mpq_mul(v,square,square);rounded(v,v,67,CHOP);
        if(n){
            mpq_mul(t,v,ctx->rom[116]);rounded(t,t,67,CHOP);
            mpq_add(even,ctx->rom[114],t);rounded(even,even,67,CHOP);
            mpq_mul(t,v,ctx->rom[117]);rounded(t,t,67,CHOP);
            mpq_add(odd,ctx->rom[115],t);rounded(odd,odd,64,RN);
        }else{
            mpq_mul(t,v,ctx->rom[123]);rounded(t,t,67,CHOP);
            mpq_add(odd,ctx->rom[121],t);rounded(odd,odd,64,RN);
            mpq_mul(t,v,ctx->rom[122]);rounded(t,t,67,CHOP);
            mpq_add(even,ctx->rom[120],t);rounded(even,even,64,RN);
            mpq_mul(t,v,odd);rounded(t,t,67,CHOP);
            mpq_add(odd,ctx->rom[119],t);rounded(odd,odd,67,CHOP);
            mpq_mul(t,v,even);rounded(t,t,67,CHOP);
            mpq_add(even,ctx->rom[118],t);rounded(even,even,67,CHOP);
        }
        mpq_mul(t,square,odd);rounded(t,t,67,CHOP);
        mpq_add(h,t,even);rounded(h,h,64,RN);
        mpq_mul(t,z,square);rounded(t,t,67,CHOP);
        mpq_mul(tail,t,h);rounded(tail,tail,67,CHOP);
        mpq_add(angle,z,tail);
        /* The table kernel is intermediate, not the final architectural add. */
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
    mpq_clears(y,x,r,z,square,h,tail,angle,t,u,c,v,odd,even,NULL);return 0;
}
enum operand_class { ZERO,NORMAL,DENORMAL,PSEUDO,INFINITY_VALUE,QNAN,SNAN,UNSUPPORTED };
static enum operand_class classify(raw80 v)
{
    unsigned e=v.se&0x7fff;
    if(!e){if(!v.sig)return ZERO;return v.sig>>63?PSEUDO:DENORMAL;}
    if(!(v.sig>>63))return UNSUPPORTED;
    if(e!=0x7fff)return NORMAL;
    if(v.sig==(UINT64_C(1)<<63))return INFINITY_VALUE;
    return v.sig&(UINT64_C(1)<<62)?QNAN:SNAN;
}

/* Masked instruction contract: valid two-deep stack, all exception latches
 * clear before loading the two raw80 operands. FLD80 does not quiet or reject
 * them; FPATAN handles unsupported encodings and signals denormal assistance.
 * This models numerical values and defined arithmetic flags, not hidden FPU
 * pointers, arbitrary restore histories, or undefined condition bits.
 */
static int fpatan_raw80(const fpatan_context *ctx,raw80 y,raw80 x,enum mode rc,
                       raw80 *out,int *c1,unsigned *exceptions)
{
    enum operand_class ky=classify(y),kx=classify(x);*c1=0;*exceptions=0;
    if(ky==UNSUPPORTED || kx==UNSUPPORTED){
        *out=(raw80){0xffff,UINT64_C(0xc000000000000000)};*exceptions=1;return 0;
    }
    int ny=ky==QNAN || ky==SNAN,nx=kx==QNAN || kx==SNAN;
    if(ny || nx){
        raw80 pick;
        if(!ny)pick=x;else if(!nx)pick=y;
        else if(ky==QNAN && kx==SNAN)pick=y;
        else if(kx==QNAN && ky==SNAN)pick=x;
        else pick=y.sig>x.sig || (y.sig==x.sig && y.se<x.se)?y:x;
        pick.sig|=UINT64_C(1)<<62;*out=pick;*exceptions=(ky==SNAN || kx==SNAN);return 0;
    }
    /* Both exponent-zero nonzero classes request the denormal assist.
     * A pseudo-denormal's numerical value still uses effective exponent 1.
     */
    if(ky==DENORMAL || ky==PSEUDO || kx==DENORMAL || kx==PSEUDO)*exceptions=2;
    int special=ky==ZERO || kx==ZERO || ky==INFINITY_VALUE || kx==INFINITY_VALUE;
    if(!special){
        int tiny=0,status=fpatan_candidate(ctx,y,x,rc,out,c1,&tiny);if(status)return status;
        /* Tininess is detected on the retained angle before final rounding,
         * even when directed rounding produces the minimum normal result.
         */
        *exceptions|=32;if(tiny)*exceptions|=16;return 0;
    }
    mpq_t angle;mpq_init(angle);int sx=(x.se>>15),sy=(y.se>>15);
    if(ky==ZERO || kx==INFINITY_VALUE){
        if(ky==INFINITY_VALUE){
            mpq_div_2exp(angle,ctx->rom[20],1);
            if(sx){mpq_t three;mpq_init(three);mpq_set_ui(three,3,1);mpq_mul(angle,angle,three);mpq_clear(three);}
        }else if(sx)mpq_set(angle,ctx->rom[19]);
    }else mpq_set(angle,ctx->rom[20]);
    if(mpq_sgn(angle)){
        if(sy)mpq_neg(angle,angle);
        *out=encode(angle,rc,c1);*exceptions|=32;
    }else *out=(raw80){(uint16_t)(sy<<15),0};
    mpq_clear(angle);return 0;
}

#ifndef FPATAN_NO_MAIN
static void selftest(fpatan_context *ctx)
{
    raw80 zero={0,0},one={0x3fff,UINT64_C(1)<<63},out;int c1;unsigned flags;
    if(fpatan_raw80(ctx,zero,one,RN,&out,&c1,&flags) || out.se || out.sig || c1 || flags)abort();
    raw80 sn={0x7fff,(UINT64_C(1)<<63)|5},qn={0x7fff,(UINT64_C(3)<<62)|2};
    if(fpatan_raw80(ctx,sn,qn,RN,&out,&c1,&flags) || out.se!=qn.se || out.sig!=qn.sig || c1 || flags!=1)abort();
    raw80 pseudo={0,UINT64_C(1)<<63};
    if(fpatan_raw80(ctx,zero,pseudo,RN,&out,&c1,&flags) || out.se || out.sig || flags!=2)abort();
    puts("PASS C candidate arithmetic/architecture synthetic selftest; no hardware");
}

int main(int argc,char **argv)
{
    fpatan_context ctx;context_init(&ctx);
    if(argc==2 && !strcmp(argv[1],"--selftest")){selftest(&ctx);context_clear(&ctx);return 0;}
    if(argc!=1){context_clear(&ctx);return 2;}
    char line[256],id[64],mode[4],extra;unsigned pc,ys,xs;uint64_t ym,xm;
    while(fgets(line,sizeof(line),stdin)){
        if(sscanf(line,"%63s %3s %u %x %" SCNx64 " %x %" SCNx64 " %c",id,mode,&pc,&ys,&ym,&xs,&xm,&extra)!=7 ||
           ys>65535 || xs>65535 || (pc!=24&&pc!=53&&pc!=64))return 2;
        enum mode rc;
        if(!strcmp(mode,"rn"))rc=RN;else if(!strcmp(mode,"rd"))rc=RD;
        else if(!strcmp(mode,"ru"))rc=RU;else if(!strcmp(mode,"rz"))rc=RZ;else return 2;
        raw80 y={(uint16_t)ys,ym},x={(uint16_t)xs,xm},result;int c1=0;unsigned flags=0;
        int status=fpatan_raw80(&ctx,y,x,rc,&result,&c1,&flags);
        if(status)printf("%s UNSUPPORTED\n",id);
        else printf("%s %04x %016" PRIx64 " %d %02x 00\n",id,result.se,result.sig,c1,flags);
    }
    context_clear(&ctx);return ferror(stdin)||fflush(stdout)?3:0;
}
#endif
