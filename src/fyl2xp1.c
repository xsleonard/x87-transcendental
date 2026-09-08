/* FYL2XP1 computes y*log2(1+x), with y = ST(1) and x = ST(0).
 * Finite x must satisfy |x| <= 1-sqrt(1/2); the largest accepted raw80
 * magnitude is 3ffd:95f619980c4336f7. Larger magnitudes and infinite x
 * return OUTSIDE_SCOPE. NaNs and unsupported encodings are handled first.
 * The caller must supply valid stack entries with no pending exception.
 *
 * Let L = 1/ln(2). For |x| <= 1/8, use
 *     log2(1+x) = 2*L*atanh(x/(x+2)).
 * This lets an odd polynomial approximate the logarithm without first
 * adding 1 to x. For 0 < |x| < 2^-69, use the linear approximation L*x.
 * For |x| > 1/8 within the supported interval, add 1 to x, truncate the
 * sum to 67 bits, and use FYL2X's table reduction and reconstruction.
 *
 * x87t_internal_evaluate_log handles special cases first, then uses 67-bit
 * truncation and selected 64-bit nearest-even operations to approximate the
 * logarithm. It multiplies this value by y exactly, then rounds to raw80
 * using the guest rounding mode. Guest PC does not change the intermediate
 * widths. The result includes C1, exception flags, and whether to write
 * ST(1) and pop the stack; exception masks can suppress those stack changes.
 */
/* fyl2xp1 entry; the shared logarithm program owns the finite-domain policy. */
#include "internal/binary.h"
x87t_error x87t_fyl2xp1(const x87t_context *context,
                        x87t_raw80 y,
                        x87t_raw80 x,
                        const x87t_control *control,
                        x87t_result *out)
{
    return x87t_internal_evaluate_log(context, 1, y, x, control, out);
}
