/* H1724: software-only differential challenge, never a production selector.
 * The first panel scans around a known regression; the second samples the
 * top polynomial binades independently. Existing operands must be filtered
 * by the usual local/private/remote freshness checks before any capture.
 */
#define main h1724_original_main
#include "../src/fsincos_skylake.c"
#undef main
#define G_H1710_MATERIALIZE 1
#include "h1710_paired_program.h"
static uint64_t h1724_rng=UINT64_C(0x1724fa11751c93e1);
static uint64_t random64(void)
{
    h1724_rng^=h1724_rng<<13;h1724_rng^=h1724_rng>>7;h1724_rng^=h1724_rng<<17;
    return h1724_rng;
}
int main(int argc,char **argv)
{
    assert(argc==2);uint64_t n=strtoull(argv[1],NULL,10),differences=0;
    for(uint64_t i=0;i<n;i++) {
        uint16_t se=0x3ffc;uint64_t sig;
        if(i<(UINT64_C(1)<<22))sig=UINT64_C(0xe79000000c3e46e7)+i-(UINT64_C(1)<<21);
        else {sig=random64()|UINT64_C(0x8000000000000000);se-=(i%8==0);}
        sf_t x=sf_from_parts(0,se,sig),z=ZERO;wv_t r=wv_from_rc(&x,&z);
        for(int m=0;m<2;m++) {
            sf_rc_t rc=m ? SF_RZ : SF_RN;x80_t a[2],b[2];int ac[2],bc[2];
            general_paired_polynomial(r,0,0,rc,a,ac);h1710_polynomial(r,0,0,rc,b,bc);
            if(a[0].se!=b[0].se || a[0].sig!=b[0].sig || a[1].se!=b[1].se || a[1].sig!=b[1].sig || ac[1]!=bc[1]) {
                printf("%04x %016llx %s %04x:%016llx %04x:%016llx %04x:%016llx %04x:%016llx\n",
                    se,(unsigned long long)sig,m ? "rz" : "rn",a[0].se,(unsigned long long)a[0].sig,
                    a[1].se,(unsigned long long)a[1].sig,b[0].se,(unsigned long long)b[0].sig,b[1].se,(unsigned long long)b[1].sig);
                differences++;
            }
        }
        if((i+1)%1000000==0){fprintf(stderr,"SCAN %llu differences=%llu\n",(unsigned long long)(i+1),(unsigned long long)differences);fflush(stderr);}
    }
    fprintf(stderr,"DONE software_inputs=%llu differences=%llu\n",(unsigned long long)n,(unsigned long long)differences);
}
