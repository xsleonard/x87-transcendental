/* FSINCOS computes sin(x) and cos(x) for finite x with |x| < 2^63.
 * At |x| >= 2^63, it sets C2 without replacing or pushing a value. Zero,
 * NaNs, infinity and unsupported encodings have separate paths. The caller
 * checks the stack and delivers any pending exception.
 *
 * Writing x = k*pi/2 + t reduces both functions to signed sin(t) or cos(t).
 * The reducer uses the stored constant M66 in place of pi/2. Tiny results
 * and table evaluation share the standalone helpers; the polynomial uses
 * a separate sequence of operations to compute both functions. Phases k
 * and k+1 select the final sine and cosine. Each result gets its sign before
 * rounding to 64 significant bits using guest RC. Each kernel fixes the
 * order of its 67-bit magnitude truncations and 64-bit nearest/even rounding
 * steps. PC24 and PC53 do not change these widths.
 * C1 comes from rounding the final cosine result.
 */
/* FSINCOS API and exception handling. The numerical algorithm starts at
 * x87t_internal_sincos_evaluate in trig/sincos.c, alongside its distinct
 * paired polynomial. C1 comes from the final cosine result. */
#include "internal/numeric.h"
x87t_error x87t_fsincos(const x87t_context *context,
                        x87t_raw80 x,
                        const x87t_control *control,
                        x87t_result *out)
{
    x87t_error error = x87t_internal_validate_call(context, control, out);
    if (error)
        return error;
    x87t_result result;
    x87t_internal_result_begin(&result, X87T_REPLACE_ST0_PUSH);
    numerical_metadata meta = {0};
    if (x87t_internal_sincos_evaluate(x, &result.primary, &result.pushed, (sf_rc_t)control->rounding, &meta) ==
        TRIG_RANGE) {
        x87t_internal_result_range(&result);
    } else {
        /* primary replaces the old ST(0) with sine. The caller then pushes
         * pushed, the cosine result, which becomes the new ST(0). */
        result.values |= X87T_PUSHED;
        result.cc_known = X87T_C2 | (meta.c1_known ? X87T_C1 : 0);
        result.cc = meta.c1 ? X87T_C1 : 0;
        /* The arithmetic core's special path has no rounding event. The
         * masked instruction clears C1, as retained H1401 A008-A013 confirm. */
        /* Those H1401 A008-A013 tests start with C1=0 and finish with C1=0;
         * they do not test whether these instructions clear an incoming
         * C1=1. Here meta starts at zero and stays zero when the core
         * returns a special result without rounding. */
        result.cc_known |= X87T_C1;
    }
    /* Every nonzero finite input in range sets PE. Denormals and
     * pseudo-denormals also set DE; true denormals set UE for sine. If UE
     * is unmasked, primary becomes the original input scaled by 2^24576.
     * result_finish suppresses both writes for unmasked IE or DE, which
     * take priority over UE and PE. Unmasked UE and PE allow both writes. */
    result.exceptions = x87t_internal_trig_flags(x, result.completion == X87T_RANGE_RETURN, 1);
    x87t_internal_wrap_trig_underflow(x, &result, control);
    x87t_internal_result_finish(&result, control);
    *out = result;
    return X87T_OK;
}
