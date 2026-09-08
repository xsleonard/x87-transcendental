/* FYL2X computes y*log2(x), with y = ST(1) and x = ST(0).
 * The shared implementation handles negative x, zeros, infinities, NaNs
 * and unsupported raw80 encodings before doing the finite arithmetic.
 * The caller must supply valid stack entries with no pending exception.
 *
 * Let L = 1/ln(2). For 7/8 <= x <= 9/8, use
 *     log2(x) = 2*L*atanh((x-1)/(x+1)).
 * This avoids subtracting table values to obtain a logarithm close to zero.
 * For other positive finite inputs, write x = m*2^E with 1 <= m < 2,
 * approximate log2(m/a) about a table midpoint a, then add log2(a) and E.
 * The table stores log2(a) in two parts that are added separately.
 *
 * x87t_internal_evaluate_log uses 67-bit truncation and selected 64-bit
 * nearest-even operations to approximate the logarithm. It multiplies this
 * value by y exactly, then rounds to raw80 using the guest rounding mode.
 * Guest PC does not change the intermediate widths. The result includes
 * C1, exception flags, and whether to write ST(1) and pop the stack; the
 * exception masks determine whether those stack changes are allowed.
 */
/* fyl2x entry; the shared logarithm program owns the finite-domain policy. */
#include "internal/binary.h"
x87t_error x87t_fyl2x(const x87t_context *context,
                      x87t_raw80 y,
                      x87t_raw80 x,
                      const x87t_control *control,
                      x87t_result *out)
{
    return x87t_internal_evaluate_log(context, 0, y, x, control, out);
}
