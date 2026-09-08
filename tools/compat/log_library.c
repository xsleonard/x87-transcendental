/* Compatibility adapter over the canonical x87trans library. */
#include "log_library.h"
#include "x87trans/x87trans.h"
#include <stdlib.h>
struct x87_log {
    x87t_context *core;
};
x87_log *x87_log_create(void)
{
    x87_log *p = malloc(sizeof(*p));
    if (!p)
        return NULL;
    p->core = x87t_create();
    if (!p->core) {
        free(p);
        return NULL;
    }
    return p;
}
void x87_log_destroy(x87_log *p)
{
    if (p) {
        x87t_destroy(p->core);
        free(p);
    }
}
x87_log_error x87_log_evaluate(const x87_log *p,
                               x87_log_instruction op,
                               x87_log_value y,
                               x87_log_value x,
                               x87_log_round rc,
                               unsigned pc,
                               x87_log_result *out)
{
    if (!p || !out || op < X87_FYL2X || op > X87_FYL2XP1)
        return X87_LOG_BAD_ARGUMENT;
    x87t_control control = {(x87t_round)rc, pc, 63};
    x87t_result result;
    x87t_error error = (op == X87_FYL2X ? x87t_fyl2x : x87t_fyl2xp1)(
        p->core, (x87t_raw80){y.se, y.sig}, (x87t_raw80){x.se, x.sig}, &control, &result);
    if (error == X87T_OUTSIDE_SCOPE)
        return X87_LOG_OUTSIDE_SCOPE;
    if (error)
        return X87_LOG_BAD_ARGUMENT;
    *out = (x87_log_result){{result.primary.se, result.primary.sig},
                            (uint8_t)!!(result.cc & X87T_C1),
                            result.exceptions};
    return X87_LOG_OK;
}
