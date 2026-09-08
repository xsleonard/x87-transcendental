/* LOG_NO_MAIN selects linkage only; the CLI and API share one algorithm. */
#define LOG_NO_MAIN
#include "log_model.c"
#include "log_library.h"

struct x87_log { log_context arithmetic; };

x87_log *x87_log_create(void)
{
    x87_log *p=malloc(sizeof(*p));
    if (p) context_init(&p->arithmetic);
    return p;
}

void x87_log_destroy(x87_log *p)
{
    if (p) { context_clear(&p->arithmetic); free(p); }
}

x87_log_error x87_log_evaluate(const x87_log *p,
    x87_log_instruction instruction,x87_log_value y,x87_log_value x,
    x87_log_round rounding,unsigned pc,x87_log_result *result)
{
    if (!p || !result || instruction<X87_FYL2X || instruction>X87_FYL2XP1 ||
        rounding<X87_LOG_RN || rounding>X87_LOG_RZ || (pc!=24 && pc!=53 && pc!=64))
        return X87_LOG_BAD_ARGUMENT;
    raw80 out; int c1; unsigned flags;
    if (log_raw80(&p->arithmetic,instruction,(raw80){y.se,y.sig},(raw80){x.se,x.sig},
                  (enum mode)rounding,&out,&c1,&flags)) return X87_LOG_OUTSIDE_SCOPE;
    *result=(x87_log_result){{out.se,out.sig},(uint8_t)c1,(uint8_t)flags};
    return X87_LOG_OK;
}
