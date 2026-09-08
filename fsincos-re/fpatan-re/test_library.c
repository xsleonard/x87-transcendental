/* Local API/contract regression tests; no native FPATAN or host atan. */
#include "fpatan_library.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    x87_fpatan *ctx=x87_fpatan_create();assert(ctx);
    x87_fpatan_value one={0x3fff,UINT64_C(1)<<63},zero={0,0};
    unsigned pcs[]={24,53,64};
    for(unsigned i=0;i<3;i++)for(unsigned r=0;r<4;r++){
        x87_fpatan_result out;
        assert(x87_fpatan_evaluate(ctx,one,one,(x87_fpatan_round)r,pcs[i],&out)==X87_FPATAN_OK);
        int up=r==X87_FPATAN_RN || r==X87_FPATAN_RU;
        assert(out.value.se==0x3ffe && out.value.sig==UINT64_C(0xc90fdaa22168c234)+(unsigned)up);
        assert(out.c1==up && out.exceptions==32);
        assert(x87_fpatan_evaluate(ctx,zero,one,(x87_fpatan_round)r,pcs[i],&out)==X87_FPATAN_OK);
        assert(!out.value.se && !out.value.sig && !out.c1 && !out.exceptions);
    }
    x87_fpatan_result before={{0x1234,5678},9,10},out=before;
    assert(x87_fpatan_evaluate(NULL,one,one,X87_FPATAN_RN,64,&out)==X87_FPATAN_BAD_ARGUMENT);
    assert(memcmp(&out,&before,sizeof(out))==0);
    assert(x87_fpatan_evaluate(ctx,one,one,(x87_fpatan_round)4,64,&out)==X87_FPATAN_BAD_ARGUMENT);
    assert(x87_fpatan_evaluate(ctx,one,one,X87_FPATAN_RN,25,&out)==X87_FPATAN_BAD_ARGUMENT);
    assert(memcmp(&out,&before,sizeof(out))==0);
    assert(x87_fpatan_evaluate(ctx,one,one,X87_FPATAN_RN,64,NULL)==X87_FPATAN_BAD_ARGUMENT);
    x87_fpatan_value unsupported={1,1};
    assert(x87_fpatan_evaluate(ctx,unsupported,one,X87_FPATAN_RN,64,&out)==X87_FPATAN_OK);
    assert(out.value.se==0xffff && out.value.sig==UINT64_C(0xc000000000000000) && out.exceptions==1);
    /* Original native counterexamples from D0008, D0009 and D0022.
     * These are regression expectations, never lookup entries in the model.
     * Check every rounding mode and PC against the preserved capture values.
     */
    static const struct {
        x87_fpatan_value y,x;
        uint16_t se;
        uint64_t sig[4];
        unsigned char c1[4];
    } regression[]={
        {{0x81fb,UINT64_C(0xefdb5b8261893554)},{0x81fc,UINT64_C(0xe405a042f0f267a9)},0xc000,
         {UINT64_C(0xaa12d89439151ac8),UINT64_C(0xaa12d89439151ac9),UINT64_C(0xaa12d89439151ac8),UINT64_C(0xaa12d89439151ac8)},{0,1,0,0}},
        {{0x7254,UINT64_C(0xd967009cc2d0386c)},{0x725a,UINT64_C(0xfdf8e8fd4375a221)},0x3ff8,
         {UINT64_C(0xdb2000abf7b8e333),UINT64_C(0xdb2000abf7b8e333),UINT64_C(0xdb2000abf7b8e334),UINT64_C(0xdb2000abf7b8e333)},{0,0,1,0}},
        {{0x0f13,UINT64_C(0xfd28b6282f47299d)},{0x0f15,UINT64_C(0xd52fc1d0ff6458f0)},0x3ffd,
         {UINT64_C(0x93c1b902bf7a2df1),UINT64_C(0x93c1b902bf7a2df0),UINT64_C(0x93c1b902bf7a2df1),UINT64_C(0x93c1b902bf7a2df0)},{1,0,1,0}}
    };
    for(unsigned j=0;j<sizeof(regression)/sizeof(regression[0]);j++)
        for(unsigned i=0;i<3;i++)for(unsigned r=0;r<4;r++){
            assert(x87_fpatan_evaluate(ctx,regression[j].y,regression[j].x,(x87_fpatan_round)r,pcs[i],&out)==X87_FPATAN_OK);
            assert(out.value.se==regression[j].se && out.value.sig==regression[j].sig[r]);
            assert(out.c1==regression[j].c1[r] && out.exceptions==32);
        }
    x87_fpatan_destroy(ctx);x87_fpatan_destroy(NULL);
    puts("PASS library API and error contract, all RC/PC; no hardware");return 0;
}
