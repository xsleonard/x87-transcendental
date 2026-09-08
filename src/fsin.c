/* FSIN computes sin(x) for finite x with |x| < 2^63. At |x| >= 2^63,
 * it sets C2 and leaves ST(0) unchanged. The shared dispatcher handles
 * zero, NaNs, infinity and unsupported encodings separately. The caller
 * checks the stack and delivers any pending exception.
 *
 * Writing x = k*pi/2 + t reduces sin(x) to +/-sin(t) or +/-cos(t), chosen
 * by k modulo 4. The reducer uses the stored constant M66 in place of pi/2.
 * Depending on |t|, it uses a tiny-result rule, a polynomial or a table.
 * It applies the quadrant sign before rounding the result to 64 significant
 * bits using guest RC. Each kernel fixes the order of its 67-bit magnitude
 * truncations and 64-bit nearest/even rounding steps. Guest PC24 and PC53
 * do not change these widths.
 */
/* Standalone fsin entry; shared kernels retain the selected phase. */
#include "internal/numeric.h"
x87t_error
x87t_fsin(const x87t_context *context, x87t_raw80 x, const x87t_control *control, x87t_result *out)
{
    x87t_error error = x87t_internal_validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    x87t_internal_result_begin(&result, X87T_REPLACE_ST0);
    numerical_metadata meta = {0};
    if (x87t_internal_standalone_evaluate(x, 0, &result.primary, (sf_rc_t)control->rounding, &meta) ==
        FSINCOS_C2) {
        x87t_internal_result_range(&result);
    } else {
        result.cc_known = X87T_C2 | (meta.c1_known ? X87T_C1 : 0);
        result.cc = meta.c1 ? X87T_C1 : 0;
    }
    /* trig_flags sets PE for every nonzero finite input in range, even if
     * the final rounding discards no bits. Denormals and pseudo-denormals
     * also set DE; true denormals set UE for sine. If UE is unmasked, return
     * the original input scaled by 2^24576. result_finish suppresses writes
     * for unmasked IE or DE, which take priority over UE and PE. Unmasked UE
     * and PE allow the write. C1 records whether final rounding increased
     * the magnitude, independently of PE. */
    result.exceptions = x87t_internal_trig_flags(x, result.completion == X87T_RANGE_RETURN, 1);
    x87t_internal_wrap_trig_underflow(x, &result, control);
    x87t_internal_result_finish(&result, control);
    *out = result;
    return X87T_OK;
}
