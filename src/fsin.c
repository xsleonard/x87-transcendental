/* Standalone fsin entry; shared kernels retain the selected phase. */
#include "internal/numeric.h"
x87t_error
x87t_fsin(const x87t_context *context, x87t_raw80 x, const x87t_control *control, x87t_result *out)
{
    x87t_error error = validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    result_begin(&result, X87T_REPLACE_ST0);
    numerical_metadata meta = {0};
    if (standalone_evaluate(x, 0, &result.primary, (sf_rc_t)control->rounding, &meta) ==
        FSINCOS_C2) {
        result_range(&result);
    } else {
        result.cc_known = X87T_C2 | (meta.c1_known ? X87T_C1 : 0);
        result.cc = meta.c1 ? X87T_C1 : 0;
    }
    *out = result;
    return X87T_OK;
}
