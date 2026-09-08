/* Compatibility adapter over the canonical x87trans library. */
#include "fpatan_library.h"
#include "x87trans/x87trans.h"
#include <stdlib.h>
struct x87_fpatan {
    x87t_context *core;
};
x87_fpatan *x87_fpatan_create(void)
{
    x87_fpatan *p = malloc(sizeof(*p));
    if (!p)
        return NULL;
    p->core = x87t_create();
    if (!p->core) {
        free(p);
        return NULL;
    }
    return p;
}
void x87_fpatan_destroy(x87_fpatan *p)
{
    if (p) {
        x87t_destroy(p->core);
        free(p);
    }
}
x87_fpatan_error x87_fpatan_evaluate(const x87_fpatan *p,
                                     x87_fpatan_value y,
                                     x87_fpatan_value x,
                                     x87_fpatan_round rc,
                                     unsigned pc,
                                     x87_fpatan_result *out)
{
    if (!p || !out)
        return X87_FPATAN_BAD_ARGUMENT;
    x87t_control control = {(x87t_round)rc, pc, 63};
    x87t_result result;
    if (x87t_fpatan(
            p->core, (x87t_raw80){y.se, y.sig}, (x87t_raw80){x.se, x.sig}, &control, &result))
        return X87_FPATAN_BAD_ARGUMENT;
    *out = (x87_fpatan_result){{result.primary.se, result.primary.sig},
                               (uint8_t)!!(result.cc & X87T_C1),
                               result.exceptions};
    return X87_FPATAN_OK;
}
