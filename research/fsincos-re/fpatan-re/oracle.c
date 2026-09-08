/* Mathematical atan2 oracle for LOCAL diagnostics, not silicon emulation.
 * Encloses atan2 with MPFR directed bounds before rounding to raw80.
 * Nonconvergent enclosure is UNKNOWN, never silently used as truth.
 * The current discovery input accepts finite nonzero valid encodings only.
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <mpfr.h>
typedef struct { unsigned se; uint64_t sig; } raw80;
static void load(mpfr_t v,unsigned se,unsigned long long sig)
{
    mpfr_set_uj(v,sig,MPFR_RNDN);
    mpfr_mul_2si(v,v,((se&0x7fff)?(int)(se&0x7fff):1)-16383-63,MPFR_RNDN);
    if(se&0x8000) mpfr_neg(v,v,MPFR_RNDN);
}
static raw80 encode(mpfr_t v,mpfr_rnd_t mode)
{
    raw80 r={0,0}; int sign=mpfr_signbit(v);
    if(mpfr_zero_p(v)) {r.se=(unsigned)sign<<15;return r;}
    long e=mpfr_get_exp(v)-1; if(e < -16382) e=-16382;
    mpfr_t t; mpfr_init2(t,mpfr_get_prec(v));
    mpfr_mul_2si(t,v,63-e,MPFR_RNDN);
    mpz_t z; mpz_init(z); mpfr_get_z(z,t,mode); mpz_abs(z,z);
    if(mpz_sizeinbase(z,2)>64) {mpz_fdiv_q_2exp(z,z,1);e++;}
    r.sig=mpz_get_ui(z); r.se=((unsigned)sign<<15)|(r.sig<(UINT64_C(1)<<63)?0:(unsigned)(e+16383));
    mpz_clear(z);mpfr_clear(t);return r;
}
int main(void)
{
    char line[256],id[64],rc[4],extra;unsigned pc,ys,xs;unsigned long long ym,xm;
    mpfr_t y,x,lo,hi;mpfr_inits2(192,y,x,lo,hi,(mpfr_ptr)0);
    while(fgets(line,sizeof(line),stdin)) {
        if(sscanf(line,"%63s %3s %u %x %llx %x %llx %c",id,rc,&pc,&ys,&ym,&xs,&xm,&extra)!=7) return 2;
        if((ys&0x7fff)==0x7fff || (xs&0x7fff)==0x7fff || !ym || !xm) return 2;
        mpfr_rnd_t mode;
        if(!strcmp(rc,"rn")) mode=MPFR_RNDN;else if(!strcmp(rc,"rd"))mode=MPFR_RNDD;
        else if(!strcmp(rc,"ru"))mode=MPFR_RNDU;else if(!strcmp(rc,"rz"))mode=MPFR_RNDZ;else return 2;
        load(y,ys,ym);load(x,xs,xm);raw80 a={0,0},b={0,0};int certified=0;
        for(unsigned precision=192;precision<=49152;precision*=2) {
            mpfr_set_prec(lo,precision);mpfr_set_prec(hi,precision);
            mpfr_atan2(lo,y,x,MPFR_RNDD);mpfr_atan2(hi,y,x,MPFR_RNDU);
            a=encode(lo,mode);b=encode(hi,mode);
            if(a.se==b.se && a.sig==b.sig) {certified=1;break;}
        }
        printf("%s %04x %016llx %s\n",id,a.se,(unsigned long long)a.sig,certified?"CERTIFIED":"UNKNOWN");
    }
    mpfr_clears(y,x,lo,hi,(mpfr_ptr)0);return ferror(stdin)||fflush(stdout)?3:0;
}
