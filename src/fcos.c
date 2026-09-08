/* FCOS computes cos(x) for finite x with |x| < 2^63. At |x| >= 2^63,
 * it sets C2 and leaves ST(0) unchanged. The shared dispatcher handles
 * zero, NaNs, infinity and unsupported encodings separately. The caller
 * checks the stack and delivers any pending exception.
 *
 * cos(x) = sin(x + pi/2), so phase=1 advances the quadrant selection by
 * one without adding pi/2 to x. The reducer uses the stored constant M66
 * in place of pi/2. Depending on the residual, it uses a tiny-result rule,
 * a polynomial or a table. It applies the quadrant sign before rounding
 * to 64 significant bits using guest RC. Each kernel fixes the order of
 * its 67-bit magnitude truncations and 64-bit nearest/even rounding steps.
 * Guest PC24 and PC53 do not change these widths.
 */
/* Standalone fcos entry; shared kernels retain the selected phase. */
#include "internal/numeric.h"
x87t_error
x87t_fcos(const x87t_context *context, x87t_raw80 x, const x87t_control *control, x87t_result *out)
{
    x87t_error error = x87t_internal_validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    x87t_internal_result_begin(&result, X87T_REPLACE_ST0);
    numerical_metadata meta = {0};
    if (x87t_internal_standalone_evaluate(x, 1, &result.primary, (sf_rc_t)control->rounding, &meta) ==
        FSINCOS_C2) {
        x87t_internal_result_range(&result);
    } else {
        result.cc_known = X87T_C2 | (meta.c1_known ? X87T_C1 : 0);
        result.cc = meta.c1 ? X87T_C1 : 0;
    }
    /* Every nonzero finite input in range sets PE, even when the result
     * is exactly 1. Denormals and pseudo-denormals also set DE. FCOS does
     * not set UE. result_finish suppresses writes for unmasked IE or DE,
     * but allows the rounded result to be written for unmasked PE.
     * C1 records a magnitude increment; it does not indicate inexactness. */
    result.exceptions = x87t_internal_trig_flags(x, result.completion == X87T_RANGE_RETURN, 0);
    x87t_internal_result_finish(&result, control);
    *out = result;
    return X87T_OK;
}
