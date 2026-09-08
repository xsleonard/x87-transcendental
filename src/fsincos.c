/* FSINCOS preserves its distinct paired polynomial and final cosine C1. */
#include "internal/numeric.h"
x87t_error x87t_fsincos(const x87t_context *context,
                        x87t_raw80 x,
                        const x87t_control *control,
                        x87t_result *out)
{
    x87t_error error = validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    result_begin(&result, X87T_REPLACE_ST0_PUSH);
    numerical_metadata meta = {0};
    if (paired_evaluate(x, &result.primary, &result.pushed, (sf_rc_t)control->rounding, &meta) ==
        FSINCOS_C2) {
        result_range(&result);
    } else {
        result.values |= X87T_PUSHED;
        result.cc_known = X87T_C2 | (meta.c1_known ? X87T_C1 : 0);
        result.cc = meta.c1 ? X87T_C1 : 0;
    }
    *out = result;
    return X87T_OK;
}
