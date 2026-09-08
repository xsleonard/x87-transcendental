/* Thin C API over the same single numerical implementation as the CLI.
 * FPATAN_NO_MAIN controls linkage only, never any arithmetic or policy.
 */
#define FPATAN_NO_MAIN
#include "fpatan_candidate.c"
#include "fpatan_library.h"

struct x87_fpatan { fpatan_context arithmetic; };

x87_fpatan *x87_fpatan_create(void)
{
    x87_fpatan *p=malloc(sizeof(*p));
    if(p)context_init(&p->arithmetic);
    return p;
}

void x87_fpatan_destroy(x87_fpatan *p)
{
    if(p){context_clear(&p->arithmetic);free(p);}
}

x87_fpatan_error x87_fpatan_evaluate(const x87_fpatan *p,
    x87_fpatan_value y,x87_fpatan_value x,x87_fpatan_round rounding,
    unsigned pc,x87_fpatan_result *result)
{
    if(!p || !result || rounding<X87_FPATAN_RN || rounding>X87_FPATAN_RZ ||
       (pc!=24 && pc!=53 && pc!=64))return X87_FPATAN_BAD_ARGUMENT;
    raw80 out;int c1=0;unsigned flags=0;
    /* Arithmetic only reads the initialized constants; evaluation temporaries
     * belong to this call, not the shared immutable context.
     */
    int status=fpatan_raw80(&p->arithmetic,
        (raw80){y.se,y.sig},(raw80){x.se,x.sig},(enum mode)rounding,&out,&c1,&flags);
    if(status)return X87_FPATAN_BAD_ARGUMENT;
    *result=(x87_fpatan_result){{out.se,out.sig},(uint8_t)c1,(uint8_t)flags};
    return X87_FPATAN_OK;
}
